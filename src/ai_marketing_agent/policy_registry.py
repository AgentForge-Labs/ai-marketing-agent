"""Versioned Policy Registry — deterministic policy records + freshness gate.

Each policy record is immutable (append-only); updates insert a new version.
Stale, contradictory, or unknown policy -> auto_quarantine (fail-closed).
Canonical reference: docs/04 Phase 1, docs/03 §3.2.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

DEFAULT_MAX_AGE_DAYS = 30


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _stable_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class PolicyRecord:
    domain: str
    version: int
    source_url: str = ""
    execution: str = "auto_quarantine"
    allowed_actions: List[str] = field(default_factory=list)
    denied_actions: List[str] = field(default_factory=list)
    captcha_policy: str = "abort_and_notify"
    account_rules: Dict[str, Any] = field(default_factory=dict)
    quotas: Dict[str, Any] = field(default_factory=dict)
    disclosure_rules: Dict[str, Any] = field(default_factory=dict)
    crawler_hash: str = ""
    checked_at: str = ""


class PolicyRegistry:
    """Read/write versioned policy records on a sqlite3 connection."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def upsert_policy(self, record: PolicyRecord) -> int:
        """Insert a new immutable version; returns the version number."""
        row = self.conn.execute(
            "SELECT COALESCE(MAX(version), 0) FROM policy_versions WHERE domain = ? COLLATE NOCASE",
            (record.domain,),
        ).fetchone()
        version = int(row[0]) + 1
        checked_at = record.checked_at or _utc_now()
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO policy_versions(
                    domain, version, source_url, execution, allowed_actions_json,
                    denied_actions_json, captcha_policy, account_rules_json, quotas_json,
                    disclosure_rules_json, crawler_hash, checked_at, created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    record.domain, version, record.source_url, record.execution,
                    _stable_json(record.allowed_actions), _stable_json(record.denied_actions),
                    record.captcha_policy, _stable_json(record.account_rules),
                    _stable_json(record.quotas), _stable_json(record.disclosure_rules),
                    record.crawler_hash, checked_at, _utc_now(),
                ),
            )
        return version

    def get_current(self, domain: str) -> Optional[PolicyRecord]:
        row = self.conn.execute(
            """
            SELECT domain, version, source_url, execution, allowed_actions_json,
                   denied_actions_json, captcha_policy, account_rules_json, quotas_json,
                   disclosure_rules_json, crawler_hash, checked_at
            FROM policy_versions WHERE domain = ? COLLATE NOCASE
            ORDER BY version DESC LIMIT 1
            """,
            (domain,),
        ).fetchone()
        if not row:
            return None
        return PolicyRecord(
            domain=row["domain"], version=row["version"], source_url=row["source_url"],
            execution=row["execution"], allowed_actions=json.loads(row["allowed_actions_json"]),
            denied_actions=json.loads(row["denied_actions_json"]), captcha_policy=row["captcha_policy"],
            account_rules=json.loads(row["account_rules_json"]), quotas=json.loads(row["quotas_json"]),
            disclosure_rules=json.loads(row["disclosure_rules_json"]),
            crawler_hash=row["crawler_hash"], checked_at=row["checked_at"],
        )

    def is_fresh(self, domain: str, *, max_age_days: int = DEFAULT_MAX_AGE_DAYS, now: Optional[datetime] = None) -> bool:
        """Unknown domain counts as stale (fail-closed)."""
        rec = self.get_current(domain)
        if rec is None or not rec.checked_at:
            return False
        try:
            checked = datetime.fromisoformat(rec.checked_at)
        except ValueError:
            return False
        ref = now or datetime.now(timezone.utc)
        if checked.tzinfo is None:
            checked = checked.replace(tzinfo=timezone.utc)
        return (ref - checked).days <= max_age_days

    def list_stale(self, *, max_age_days: int = DEFAULT_MAX_AGE_DAYS) -> List[str]:
        domains = [r[0] for r in self.conn.execute("SELECT DISTINCT domain FROM policy_versions").fetchall()]
        return [d for d in domains if not self.is_fresh(d, max_age_days=max_age_days)]

    def append_check(self, domain: str, *, execution: str, result: str, source_url: str = "", crawler_hash: str = "") -> str:
        check_id = uuid.uuid4().hex
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO policy_checks(check_id, domain, source_url, execution, result, crawler_hash, checked_at)
                VALUES(?,?,?,?,?,?,?)
                """,
                (check_id, domain, source_url, execution, result, crawler_hash, _utc_now()),
            )
        return check_id


def evaluate_policy_gate(
    registry: PolicyRegistry,
    domains: List[str],
    *,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
) -> Dict[str, Any]:
    """Fail-closed gate for runner/discovery: every adapter domain must be fresh.

    Returns {"proceed": bool, "stale": [...], "reason": str}. Unknown == stale.
    """
    stale = [d for d in domains if not registry.is_fresh(d, max_age_days=max_age_days)]
    if stale:
        return {"proceed": False, "stale": stale, "reason": f"stale_policy:{','.join(stale)}"}
    return {"proceed": True, "stale": [], "reason": "policy_fresh"}
