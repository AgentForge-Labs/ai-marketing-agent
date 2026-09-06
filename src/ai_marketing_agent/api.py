"""Management HTTP API (#26) — stdlib only, zero new dependencies.

Serves the operator surface over real backend objects: SaaSStore (auth,
quota, consent), Metrics (Prometheus + JSON), ChannelCatalogue +
PlatformRiskRouter (routing). Fail-closed: every endpoint except /health
requires X-API-Token (SaaSStore API key); malformed input -> 4xx, never 500
for client errors. Binds loopback by default.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlsplit, parse_qs

from .catalogue import ChannelCatalogue
from .metrics import get_metrics
from .risk_router import PlatformRiskRouter
from .saas import SaaSStore

MAX_BODY = 64 * 1024
MAX_AUTO_RISK = ("Low", "Moderate", "High")


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args: Any) -> None:  # quiet; audit via runner logs
        pass

    # -- helpers --
    def _send(self, status: int, obj: Any, content_type: str = "application/json") -> None:
        body = obj.encode("utf-8") if isinstance(obj, str) else json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return None, "invalid Content-Length"
        if length > MAX_BODY:
            return None, "body too large"
        try:
            raw = self.rfile.read(length) if length else b"{}"
            obj = json.loads(raw.decode("utf-8"))
        except Exception:
            return None, "malformed JSON"
        if not isinstance(obj, dict):
            return None, "JSON object required"
        return obj, None

    def _auth(self) -> Optional[str]:
        token = self.headers.get("X-API-Token") or ""
        if not token:
            return None
        return self.server.store.authenticate_key(token)

    # -- routing --
    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/health":
            self._send(200, {"status": "ok"})
            return
        tenant = self._auth()
        if tenant is None:
            self._send(401, {"error": "missing or invalid X-API-Token"})
            return
        if path == "/metrics":
            self._send(200, get_metrics().render_prometheus(), "text/plain; version=0.0.4")
        elif path == "/stats":
            self._send(200, {"metrics": get_metrics().snapshot(), "tenant_id": tenant})
        elif path == "/quota":
            try:
                remaining = self.server.store.quota_remaining(tenant)
            except ValueError as e:
                self._send(404, {"error": str(e)})
                return
            self._send(200, {"tenant_id": tenant, "quota_remaining": remaining})
        elif path == "/consent":
            qs = parse_qs(urlsplit(self.path).query)
            subject = (qs.get("subject_id") or [""])[0]
            purpose = (qs.get("purpose") or [""])[0]
            if not subject or not purpose:
                self._send(400, {"error": "subject_id and purpose required"})
                return
            self._send(200, {"has_consent": self.server.store.has_consent(tenant, subject, purpose)})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        tenant = self._auth()
        if tenant is None:
            self._send(401, {"error": "missing or invalid X-API-Token"})
            return
        if path == "/route":
            body, err = self._read_json()
            if err:
                self._send(400 if err != "body too large" else 413, {"error": err})
                return
            assert body is not None
            risk = body.get("max_auto_risk", "High")
            if risk not in MAX_AUTO_RISK:
                self._send(400, {"error": f"max_auto_risk must be one of {list(MAX_AUTO_RISK)}"})
                return
            try:
                channel = self.server.catalogue.require_unique_domain(body.get("domain", ""))
            except KeyError as e:
                self._send(200, {"execution_mode": "auto_quarantine", "should_execute": False,
                                 "reason": str(e)})
                return
            decision = PlatformRiskRouter(max_autonomous_risk=risk).route(channel, body.get("action", ""))
            self._send(200, decision.to_dict())
        elif path == "/consent":
            body, err = self._read_json()
            if err:
                self._send(400 if err != "body too large" else 413, {"error": err})
                return
            assert body is not None
            subject, purpose, action = body.get("subject_id", ""), body.get("purpose", ""), body.get("action", "")
            if not subject or not purpose or action not in ("grant", "withdraw"):
                self._send(400, {"error": "subject_id, purpose and action=grant|withdraw required"})
                return
            if action == "grant":
                self.server.store.grant_consent(tenant, subject, purpose)
            else:
                self.server.store.withdraw_consent(tenant, subject, purpose)
            self._send(200, {"ok": True, "action": action})
        else:
            self._send(404, {"error": "not found"})


class ApiServer:
    """Loopback management API. Use start()/stop() or serve_forever()."""

    def __init__(self, store: SaaSStore, catalogue: Optional[ChannelCatalogue] = None,
                 *, host: str = "127.0.0.1", port: int = 0) -> None:
        self.store = store
        self.catalogue = catalogue or ChannelCatalogue.load()
        self._httpd = ThreadingHTTPServer((host, port), _Handler)
        self._httpd.store = store  # type: ignore
        self._httpd.catalogue = self.catalogue  # type: ignore
        self._thread: Optional[threading.Thread] = None

    @property
    def url(self) -> str:
        host, port = self._httpd.server_address[:2]
        return f"http://{host}:{port}"

    def start(self) -> "ApiServer":
        self._thread = threading.Thread(target=self._httpd.serve_forever, kwargs={"poll_interval": 0.05},
                                        daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
        if self._thread:
            self._thread.join(timeout=5)


def serve(store: SaaSStore, *, host: str = "127.0.0.1", port: int = 8791) -> None:
    """Blocking entry for operators."""
    srv = ApiServer(store, host=host, port=port)
    print(f"serving {srv.url} (Ctrl-C to stop)")
    try:
        srv._httpd.serve_forever()
    except KeyboardInterrupt:
        pass


def main() -> int:
    """python -m ai_marketing_agent.api --db FILE [--port N] [--bootstrap-tenant SLUG]."""
    import argparse
    import sqlite3
    from pathlib import Path

    from .storage import apply_migrations

    ap = argparse.ArgumentParser(description="Loopback management API (X-API-Token required)")
    ap.add_argument("--db", required=True, help="sqlite file (created if missing)")
    ap.add_argument("--port", type=int, default=8791)
    ap.add_argument("--bootstrap-tenant", default=None,
                    help="create tenant + issue one API key, print it once, then serve")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[2]
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    apply_migrations(conn, root / "database" / "migrations")
    store = SaaSStore(conn)
    if args.bootstrap_tenant:
        tid = store.create_tenant(args.bootstrap_tenant)
        print(f"tenant_id={tid}")
        print(f"api_key={store.issue_api_key(tid, 'bootstrap')}")
    serve(store, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
