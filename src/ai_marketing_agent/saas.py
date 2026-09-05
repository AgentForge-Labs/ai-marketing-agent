"""SaaS foundation (Phase 11, #15) — tenants, RBAC, isolation, API keys, metering.

UI surfaces (dashboard, wizard) live outside this Python core; this module owns
the enforceable backend rules: tenant isolation, role checks, key auth, quotas,
and the tenant kill switch. Secrets: only key HASHES stored, never raw keys.
"""
from __future__ import annotations

import hashlib
import secrets
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _hash_key(raw: str) -> str:
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


ROLE_RANK = {"viewer": 1, "editor": 2, "admin": 3, "owner": 4}


@dataclass(frozen=True)
class Tenant:
    tenant_id: str
    slug: str
    plan: str = "starter"
    monthly_quota: int = 1000
    paused: bool = False


class SaaSStore:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    # -- tenants --
    def create_tenant(self, slug: str, *, plan: str = "starter", monthly_quota: int = 1000) -> str:
        tenant_id = uuid.uuid4().hex
        with self.conn:
            self.conn.execute(
                "INSERT INTO tenants(tenant_id, slug, plan, monthly_quota, paused, created_at) VALUES(?,?,?,?,0,?)",
                (tenant_id, slug, plan, monthly_quota, _utc_now()),
            )
        return tenant_id

    def set_paused(self, tenant_id: str, paused: bool) -> None:
        with self.conn:
            self.conn.execute("UPDATE tenants SET paused=? WHERE tenant_id=?", (1 if paused else 0, tenant_id))

    def is_paused(self, tenant_id: str) -> bool:
        row = self.conn.execute("SELECT paused FROM tenants WHERE tenant_id=?", (tenant_id,)).fetchone()
        return bool(row and row["paused"])

    # -- users & memberships (RBAC) --
    def create_user(self, email: str) -> str:
        user_id = uuid.uuid4().hex
        with self.conn:
            self.conn.execute("INSERT INTO users(user_id, email, created_at) VALUES(?,?,?)",
                              (user_id, email, _utc_now()))
        return user_id

    def add_member(self, tenant_id: str, user_id: str, role: str) -> None:
        if role not in ROLE_RANK:
            raise ValueError(f"unknown role: {role!r}")
        with self.conn:
            self.conn.execute(
                "INSERT INTO memberships(tenant_id, user_id, role, created_at) VALUES(?,?,?,?) "
                "ON CONFLICT(tenant_id, user_id) DO UPDATE SET role=excluded.role",
                (tenant_id, user_id, role, _utc_now()),
            )

    def require_role(self, tenant_id: str, user_id: str, minimum: str) -> None:
        """Raise PermissionError unless the member's role ranks >= minimum."""
        row = self.conn.execute(
            "SELECT role FROM memberships WHERE tenant_id=? AND user_id=?", (tenant_id, user_id)
        ).fetchone()
        if not row or ROLE_RANK.get(row["role"], 0) < ROLE_RANK[minimum]:
            raise PermissionError(f"role {minimum}+ required in tenant {tenant_id}")

    # -- tenant isolation --
    @staticmethod
    def assert_same_tenant(record_tenant: str, actor_tenant: str) -> None:
        """Every read/write must pass this: cross-tenant access is denied, no exceptions."""
        if not record_tenant or record_tenant != actor_tenant:
            raise PermissionError("cross-tenant access denied")

    # -- API keys (hash-only) --
    def issue_api_key(self, tenant_id: str, name: str = "") -> str:
        raw = "ak_" + secrets.token_urlsafe(32)
        with self.conn:
            self.conn.execute("INSERT INTO api_keys(key_hash, tenant_id, name, revoked, created_at) VALUES(?,?,?,?,?)",
                              (_hash_key(raw), tenant_id, name, 0, _utc_now()))
        return raw

    def authenticate_key(self, raw: str) -> Optional[str]:
        """Return tenant_id for a valid non-revoked key, else None. Timing-safe compare."""
        digest = _hash_key(raw)
        for row in self.conn.execute("SELECT key_hash, tenant_id, revoked FROM api_keys").fetchall():
            if secrets.compare_digest(row["key_hash"], digest):
                return None if row["revoked"] else row["tenant_id"]
        return None

    def revoke_key(self, raw: str) -> None:
        with self.conn:
            self.conn.execute("UPDATE api_keys SET revoked=1 WHERE key_hash=?", (_hash_key(raw),))

    # -- usage metering + quotas --
    def record_usage(self, tenant_id: str, amount: int = 1, *, period: Optional[str] = None) -> None:
        period = period or datetime.now(timezone.utc).strftime("%Y-%m")
        with self.conn:
            self.conn.execute(
                "INSERT INTO usage_meter(tenant_id, period, used) VALUES(?,?,?) "
                "ON CONFLICT(tenant_id, period) DO UPDATE SET used=used+excluded.used",
                (tenant_id, period, amount),
            )

    def quota_remaining(self, tenant_id: str, *, period: Optional[str] = None) -> int:
        period = period or datetime.now(timezone.utc).strftime("%Y-%m")
        row = self.conn.execute("SELECT monthly_quota FROM tenants WHERE tenant_id=?", (tenant_id,)).fetchone()
        if not row:
            raise ValueError(f"unknown tenant: {tenant_id}")
        used = self.conn.execute(
            "SELECT used FROM usage_meter WHERE tenant_id=? AND period=?", (tenant_id, period)
        ).fetchone()
        return int(row["monthly_quota"]) - (int(used["used"]) if used else 0)

    def check_quota(self, tenant_id: str) -> None:
        if self.is_paused(tenant_id):
            raise PermissionError(f"tenant {tenant_id} is paused (kill switch)")
        if self.quota_remaining(tenant_id) <= 0:
            raise PermissionError(f"tenant {tenant_id} quota exhausted")

    # -- consent ledger (GDPR Art.6/7) + retention (Art.5.1.e) --
    def grant_consent(self, tenant_id: str, subject_id: str, purpose: str) -> None:
        """Fail-closed: runner/orchestrator must check has_consent before acting."""
        with self.conn:
            self.conn.execute(
                "INSERT INTO consents(tenant_id, subject_id, purpose, granted, decided_at) VALUES(?,?,?,?,?) "
                "ON CONFLICT(tenant_id, subject_id, purpose) DO UPDATE SET granted=1, decided_at=excluded.decided_at",
                (tenant_id, subject_id, purpose, 1, _utc_now()),
            )

    def withdraw_consent(self, tenant_id: str, subject_id: str, purpose: str) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO consents(tenant_id, subject_id, purpose, granted, decided_at) VALUES(?,?,?,?,?) "
                "ON CONFLICT(tenant_id, subject_id, purpose) DO UPDATE SET granted=0, decided_at=excluded.decided_at",
                (tenant_id, subject_id, purpose, 0, _utc_now()),
            )

    def has_consent(self, tenant_id: str, subject_id: str, purpose: str) -> bool:
        row = self.conn.execute(
            "SELECT granted FROM consents WHERE tenant_id=? AND subject_id=? AND purpose=?",
            (tenant_id, subject_id, purpose),
        ).fetchone()
        return bool(row and row["granted"])

    def purge_consents_before(self, cutoff_iso: str) -> int:
        """Delete consent rows decided before cutoff (storage limitation). Returns rows removed."""
        with self.conn:
            cur = self.conn.execute("DELETE FROM consents WHERE decided_at < ?", (cutoff_iso,))
            return cur.rowcount or 0
