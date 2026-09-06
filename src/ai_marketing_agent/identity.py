"""Identity isolation — the golden rule (#37).

One site-profile = 1 mail + 1 browser profile + 1 IP, always. A second profile
on the SAME site requires a different mail AND a different IP AND a different
browser profile. Any violation quarantines the job before any browser launches.

Bindings persist in sqlite (same conn as the queue). Checked on every run.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


class IdentityViolation(ValueError):
    """Golden-rule breach: fail closed, never launch."""


@dataclass(frozen=True)
class IdentityBinding:
    tenant_id: str
    domain: str
    profile_id: str
    email: str
    ip: str


def ensure_identity_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS identity_bindings (
            tenant_id TEXT NOT NULL,
            domain TEXT NOT NULL,
            profile_id TEXT NOT NULL,
            email TEXT NOT NULL,
            ip TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (tenant_id, domain, profile_id)
        );
        """
    )
    conn.commit()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def check_identity(
    conn: sqlite3.Connection,
    tenant_id: str,
    domain: str,
    profile_id: str,
    email: str,
    ip: str,
) -> IdentityBinding:
    """Assert the golden rule. Returns the binding (existing or newly stored).

    Raises IdentityViolation on:
    - profile triple rebound to a different email/ip (cross-contamination);
    - second profile on the same domain reusing the first profile's email or ip;
    - empty email/ip/profile (fail-closed: anonymous profiles don't exist).
    """
    tenant_id = (tenant_id or "").strip().lower()
    domain = (domain or "").strip().lower().rstrip(".")
    profile_id = (profile_id or "").strip()
    email = (email or "").strip().lower()
    ip = (ip or "").strip()
    if not tenant_id or not domain or not profile_id:
        raise IdentityViolation("tenant/domain/profile required")
    if not email or not ip:
        raise IdentityViolation(f"golden rule: {domain}/{profile_id} needs 1 mail + 1 IP, got none")
    ensure_identity_tables(conn)
    row = conn.execute(
        "SELECT email, ip FROM identity_bindings WHERE tenant_id=? AND domain=? AND profile_id=?",
        (tenant_id, domain, profile_id),
    ).fetchone()
    if row:
        old_email = row["email"] if isinstance(row, sqlite3.Row) else row[0]
        old_ip = row["ip"] if isinstance(row, sqlite3.Row) else row[1]
        if old_email != email or old_ip != ip:
            raise IdentityViolation(
                f"golden rule: {domain}/{profile_id} already bound to another mail/IP — "
                "profiles never share or swap identities")
        return IdentityBinding(tenant_id, domain, profile_id, email, ip)
    siblings = conn.execute(
        "SELECT profile_id, email, ip FROM identity_bindings WHERE tenant_id=? AND domain=?",
        (tenant_id, domain),
    ).fetchall()
    for sib in siblings:
        s_prof = sib["profile_id"] if isinstance(sib, sqlite3.Row) else sib[0]
        s_email = sib["email"] if isinstance(sib, sqlite3.Row) else sib[1]
        s_ip = sib["ip"] if isinstance(sib, sqlite3.Row) else sib[2]
        if s_email == email:
            raise IdentityViolation(
                f"golden rule: mail {email} already used by {domain}/{s_prof} — "
                "a second profile needs its own mail")
        if s_ip == ip:
            raise IdentityViolation(
                f"golden rule: IP {ip} already used by {domain}/{s_prof} — "
                "a second profile needs its own IP")
    with conn:
        conn.execute(
            "INSERT INTO identity_bindings(tenant_id, domain, profile_id, email, ip, created_at)"
            " VALUES(?,?,?,?,?,?)",
            (tenant_id, domain, profile_id, email, ip, _now()),
        )
    return IdentityBinding(tenant_id, domain, profile_id, email, ip)



