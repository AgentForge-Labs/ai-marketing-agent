"""Worker loop (#29) — queue lease -> adapter -> route -> values -> execute -> settle.

The system is now a runnable service, not just a library: `run_once` leases one
job and drives it to a terminal queue state; `serve_forever` loops. No secrets
in the queue: adapters are files under adapters/<site_id>.json, credentials
resolve at run time via values_fn (#30). Execution fns are injectable so the
loop is testable without a browser; the default run_fn is the real browser path.
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from .catalogue import ChannelCatalogue
from .queue import complete_job, fail_job, lease_next_job, quarantine_job, recover_stalled
from .risk_router import API_MEDIA, PlatformRiskRouter

ADAPTERS_DIR = Path(__file__).resolve().parents[2] / "adapters"

# Adapter operation -> canonical matrix action (#33 adds register/login cells).
OPERATION_ACTION_MAP = {
    "submitListing": "own_content_submit_post",
    "post": "own_content_submit_post",
    "comment": "comment_reply",
    "register": "register",
    "login": "login",
}

RunFn = Callable[[Dict[str, Any], Any, Dict[str, Any], Dict[str, Any]], Any]
ValuesFn = Callable[[Dict[str, Any], Any], Dict[str, Any]]


def load_adapter(site_id: str, *, adapters_dir: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(((adapters_dir or ADAPTERS_DIR) / f"{site_id}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _default_run_fn(adapter: Dict[str, Any], decision: Any, flow: Dict[str, Any],
                    values: Dict[str, Any]) -> Any:
    """Real browser path. Raises RuntimeError when browser deps are unavailable."""
    try:
        from .runner import AutonomousRunner
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(f"browser_unavailable: {e}")
    runner = AutonomousRunner.from_adapter_and_decision(adapter, decision)
    return asyncio.run(runner.run_with_browser_provider(flow, adapter, values=values))


def run_once(
    conn: sqlite3.Connection,
    worker_id: str,
    *,
    run_fn: Optional[RunFn] = None,
    api_fn: Optional[RunFn] = None,
    values_fn: Optional[ValuesFn] = None,
    adapters_dir: Optional[Path] = None,
    catalogue: Optional[ChannelCatalogue] = None,
) -> str:
    """Lease one job and settle it. Returns idle|done|failed|quarantined."""
    job = lease_next_job(conn, worker_id, lease_seconds=600)
    if job is None:
        return "idle"

    adapter = load_adapter(job.site_id, adapters_dir=adapters_dir)
    if adapter is None:
        quarantine_job(conn, job.id, f"no_adapter:{job.site_id}")
        return "quarantined"
    allowed = ((adapter.get("policy") or {}).get("allowedActions")) or []
    if job.operation not in allowed:
        quarantine_job(conn, job.id, f"operation_denied:{job.operation}")
        return "quarantined"
    flow = (adapter.get("flows") or {}).get(job.operation)
    if not isinstance(flow, dict):
        quarantine_job(conn, job.id, f"no_flow:{job.operation}")
        return "quarantined"

    # Route through the canonical matrix (fail-closed on unknown action).
    try:
        cat = catalogue or ChannelCatalogue.load()
        domains = adapter.get("domains") or []
        channel = cat.require_unique_domain(domains[0])
        action = OPERATION_ACTION_MAP.get(job.operation, job.operation)
        decision = PlatformRiskRouter().route(channel, action)
    except (KeyError, ValueError) as e:
        quarantine_job(conn, job.id, f"route_failed:{str(e)[:120]}")
        return "quarantined"
    if not decision.should_execute:
        quarantine_job(conn, job.id, f"router_quarantine:{decision.reason if hasattr(decision, 'reason') else ''}"[:200])
        return "quarantined"

    try:
        values = (values_fn or (lambda _a, _j: {}))(adapter, job)
    except Exception as e:
        fail_job(conn, job.id, f"values_failed:{str(e)[:120]}")
        return "failed"

    try:
        if decision.selected_medium in API_MEDIA or decision.execution_mode == "api_auto":
            if api_fn is None:
                fail_job(conn, job.id, "api_not_wired")
                return "failed"
            result = api_fn(adapter, decision, flow, values)
        else:
            result = (run_fn or _default_run_fn)(adapter, decision, flow, values)
    except Exception as e:
        fail_job(conn, job.id, f"worker_exception:{type(e).__name__}:{str(e)[:120]}")
        return "failed"

    status = getattr(result, "status", "failed")
    if status == "done":
        complete_job(conn, job.id)
        return "done"
    if status == "auto_quarantine":
        quarantine_job(conn, job.id, str(getattr(result, "detail", ""))[:200])
        return "quarantined"
    fail_job(conn, job.id, f"{status}:{str(getattr(result, 'detail', ''))[:150]}")
    return "failed"


def serve_forever(conn_factory: Callable[[], sqlite3.Connection], worker_id: str, *,
                  poll_seconds: float = 5.0, stop: Optional[threading.Event] = None,
                  **run_kwargs: Any) -> int:
    """Loop run_once until stop is set. Returns jobs settled (excl. idle polls)."""
    stop = stop or threading.Event()
    settled = 0
    while not stop.is_set():
        conn = conn_factory()
        try:
            recover_stalled(conn)
            outcome = run_once(conn, worker_id, **run_kwargs)
        finally:
            conn.close()
        if outcome != "idle":
            settled += 1
        else:
            stop.wait(poll_seconds)
    return settled
