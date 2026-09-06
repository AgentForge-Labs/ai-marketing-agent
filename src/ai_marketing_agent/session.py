"""Session persistence (#31) — login once, reuse the authenticated context.

Playwright storage_state (cookies + localStorage origins) per (tenant, domain),
JSON files under runtime/sessions (gitignored; cookies are secrets and never
enter the repo). TTL expiry forces periodic re-login. Browser-agnostic: the
store only moves dicts; BrowserProvider.launch(session_state=...) passes them
to new_context, extract_session(context) reads them back.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

DEFAULT_SESSION_DIR = Path(__file__).resolve().parents[2] / "runtime" / "sessions"
DEFAULT_TTL_S = 12 * 3600.0


def _key(tenant_id: str, domain: str) -> str:
    safe = "".join(c if (c.isalnum() or c in "-_.") else "_" for c in f"{tenant_id}__{domain}")
    return (safe[:120] or "default") + ".json"


class SessionStore:
    def __init__(self, session_dir: Optional[Path] = None, *, ttl_s: float = DEFAULT_TTL_S,
                 now: Optional[callable] = None) -> None:  # type: ignore
        self.dir = Path(session_dir) if session_dir else DEFAULT_SESSION_DIR
        self.ttl_s = ttl_s
        self._now = now or time.time

    def _path(self, tenant_id: str, domain: str) -> Path:
        return self.dir / _key(tenant_id, domain)

    def save(self, tenant_id: str, domain: str, state: Dict[str, Any]) -> Path:
        """Persist storage_state dict. Raises ValueError on empty state."""
        if not isinstance(state, dict) or not state.get("cookies"):
            raise ValueError("refusing to persist empty session state")
        self.dir.mkdir(parents=True, exist_ok=True)
        payload = {"saved_at": self._now(), "state": state}
        path = self._path(tenant_id, domain)
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def load(self, tenant_id: str, domain: str) -> Optional[Dict[str, Any]]:
        """Fresh state dict, or None when missing/expired/corrupt (fail-closed)."""
        try:
            payload = json.loads(self._path(tenant_id, domain).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(payload, dict) or not isinstance(payload.get("state"), dict):
            return None
        if self._now() - float(payload.get("saved_at", 0)) > self.ttl_s:
            return None
        state = payload["state"]
        return state if state.get("cookies") else None

    def clear(self, tenant_id: str, domain: str) -> bool:
        try:
            self._path(tenant_id, domain).unlink()
            return True
        except OSError:
            return False


async def extract_session(context: Any) -> Dict[str, Any]:
    """Read playwright storage_state from a live context."""
    return await context.storage_state()
