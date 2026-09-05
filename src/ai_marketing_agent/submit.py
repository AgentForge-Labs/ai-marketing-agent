"""Submit pilot logic (Phase 6, #10) — idempotency first, ambiguous never blind-retried.

Rules:
  - Pre-submit idempotency check: same key -> return existing, never resubmit.
  - Ambiguous outcome -> remote lookup first (injected finder, e.g. site search);
    found -> adopt existing; not found -> new job with a NEW content version.
  - Listing/post IDs + URLs recorded on success.
  - Live submit itself stays in runner.py; this module is the decision layer
    (fully unit-testable, no browser/network).
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from .queue import idempotency_key


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class SubmitPlan:
    tenant_id: str
    site_id: str
    operation: str
    content_version: str
    canonical_target: str = ""
    content_semantic_key: str = ""

    def key(self) -> str:
        return idempotency_key(
            self.tenant_id, self.site_id, self.operation,
            self.canonical_target, self.content_semantic_key or self.content_version,
        )


@dataclass
class AmbiguousOutcome:
    plan: SubmitPlan
    reason: str = "uncertain"
    finder: Optional[Callable[[SubmitPlan], Optional[Dict[str, Any]]]] = None
    audit: List[Dict[str, Any]] = field(default_factory=list)


def ensure_submit_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS submissions (
            idempotency_key TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            site_id TEXT NOT NULL,
            operation TEXT NOT NULL,
            listing_url TEXT NOT NULL DEFAULT '',
            external_id TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'submitted',
            created_at TEXT NOT NULL
        );
        """
    )
    conn.commit()


def pre_submit_check(conn: sqlite3.Connection, plan: SubmitPlan) -> Optional[Dict[str, Any]]:
    """Return existing submission if this exact action already ran, else None."""
    row = conn.execute(
        "SELECT idempotency_key, listing_url, external_id, status FROM submissions WHERE idempotency_key=?",
        (plan.key(),),
    ).fetchone()
    return dict(row) if row else None


def record_submission(
    conn: sqlite3.Connection, plan: SubmitPlan, *,
    listing_url: str = "", external_id: str = "", status: str = "submitted",
) -> None:
    with conn:
        conn.execute(
            """INSERT INTO submissions(idempotency_key, tenant_id, site_id, operation,
                                      listing_url, external_id, status, created_at)
               VALUES(?,?,?,?,?,?,?,?)
               ON CONFLICT(idempotency_key) DO UPDATE SET
                 listing_url=excluded.listing_url, external_id=excluded.external_id,
                 status=excluded.status""",
            (plan.key(), plan.tenant_id, plan.site_id, plan.operation,
             listing_url, external_id, status, _utc_now()),
        )


def resolve_ambiguous(outcome: AmbiguousOutcome) -> Dict[str, Any]:
    """Ambiguous submit -> remote lookup BEFORE any retry. Never blind-retry.

    Returns {"action": "adopt_existing"|"queue_new"|"quarantine", ...}.
    No finder configured -> quarantine (fail-closed).
    """
    if outcome.finder is None:
        outcome.audit.append({"event": "ambiguous_no_finder", "action": "quarantine"})
        return {"action": "quarantine", "reason": "no remote lookup configured", "audit": outcome.audit}
    try:
        found = outcome.finder(outcome.plan)
    except Exception as e:
        outcome.audit.append({"event": "lookup_failed", "action": "quarantine", "error": str(e)[:200]})
        return {"action": "quarantine", "reason": "lookup_failed", "audit": outcome.audit}
    if found:
        outcome.audit.append({"event": "adopted_existing", "action": "adopt_existing"})
        return {"action": "adopt_existing", "remote": found, "audit": outcome.audit}
    outcome.audit.append({"event": "not_found_queue_new", "action": "queue_new"})
    return {"action": "queue_new", "reason": "remote object absent; new content version required",
            "audit": outcome.audit}


def pilot_checklist(*, adapter_ok: bool, idempotency_ok: bool, assertion_ok: bool,
                    runs: int = 0, required_runs: int = 3) -> Dict[str, Any]:
    """Phase 6 pilot gate: 5 channels x required_runs clean runs (tracked per channel)."""
    passed = bool(adapter_ok and idempotency_ok and assertion_ok and runs >= required_runs)
    return {"pilot_pass": passed, "runs": runs, "required_runs": required_runs,
            "checks": {"adapter": adapter_ok, "idempotency": idempotency_ok, "assertion": assertion_ok}}
