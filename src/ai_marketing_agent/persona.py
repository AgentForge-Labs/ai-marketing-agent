"""Persona Engine + identity registry (Phase 3, #6).

- 1,000+ persona definitions: voice, locale, timezone, channel eligibility,
  disclosure profile, content history (stdlib only).
- Account/session references are ALWAYS vault:// (DB trigger enforces).
- Persona->account mapping enforces channel multi-account policy + the
  canonical accountReuse gate (assert_reopen_allowed).
- Session health checks quarantine on access challenges.
- Authorized TOTP (RFC 6238, stdlib hmac) + OAuth refresh live here.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import sqlite3
import struct
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .account_reuse import BanState, PlatformPolicy, assert_reopen_allowed
from .vault import VaultProvider, resolve_secret


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class Persona:
    persona_id: str
    tenant_id: str = ""
    brand_id: str = ""
    display_name: str = ""
    handle_strategy: str = ""
    locale: str = ""
    timezone: str = "UTC"
    voice_profile: Dict[str, Any] = field(default_factory=dict)
    topics: List[str] = field(default_factory=list)
    disclosure_profile: Dict[str, Any] = field(default_factory=dict)
    allowed_channel_classes: List[str] = field(default_factory=list)
    status: str = "active"


@dataclass(frozen=True)
class Account:
    account_id: str
    tenant_id: str
    site_id: str
    persona_id: Optional[str]
    credential_ref: str
    session_ref: str
    totp_ref: str = ""
    ip_ref: str = ""
    profile_ref: str = ""
    status: str = "active"


def totp_now(secret_b32: str, *, digits: int = 6, period: int = 30, at: Optional[int] = None) -> str:
    """RFC 6238 TOTP from a base32 secret (stdlib only)."""
    key = base64.b32decode(secret_b32.strip().replace(" ", "").upper())
    counter = int((at if at is not None else time.time()) // period)
    mac = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = mac[-1] & 0x0F
    code = struct.unpack(">I", mac[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(code % (10 ** digits)).zfill(digits)


def refresh_oauth_token(*, token_url: str, client_id: str, refresh_token: str, timeout: float = 15.0) -> Dict[str, Any]:
    """Authorized OAuth refresh (requests needed only for live calls; mock-friendly)."""
    import requests  # local import: requests already a runtime dep (requirements.txt)

    resp = requests.post(
        token_url,
        data={"grant_type": "refresh_token", "client_id": client_id, "refresh_token": refresh_token},
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    if "access_token" not in data:
        raise ValueError("oauth refresh response missing access_token")
    return data


class PersonaRegistry:
    """SQLite-backed persona + account registry (prototype; PG port in Phase 2 schema)."""

    def __init__(self, conn: sqlite3.Connection, vault: Optional[VaultProvider] = None) -> None:
        self.conn = conn
        self.vault = vault

    def create_persona(self, persona: Persona) -> str:
        now = _utc_now()
        with self.conn:
            self.conn.execute(
                """INSERT INTO personas(persona_id, tenant_id, brand_id, display_name, handle_strategy,
                   locale, timezone, voice_profile_json, topics_json, disclosure_profile_json,
                   allowed_channel_classes_json, account_refs_json, session_policy, content_history_ref,
                   status, created_at, updated_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (persona.persona_id, persona.tenant_id, persona.brand_id, persona.display_name,
                 persona.handle_strategy, persona.locale, persona.timezone,
                 json.dumps(persona.voice_profile, ensure_ascii=False, sort_keys=True),
                 json.dumps(persona.topics, ensure_ascii=False),
                 json.dumps(persona.disclosure_profile, ensure_ascii=False, sort_keys=True),
                 json.dumps(persona.allowed_channel_classes, ensure_ascii=False),
                 "[]", "", "", persona.status, now, now),
            )
        return persona.persona_id

    def get_persona(self, persona_id: str) -> Optional[Persona]:
        row = self.conn.execute("SELECT * FROM personas WHERE persona_id=?", (persona_id,)).fetchone()
        if not row:
            return None
        return Persona(
            persona_id=row["persona_id"], tenant_id=row["tenant_id"], brand_id=row["brand_id"],
            display_name=row["display_name"], handle_strategy=row["handle_strategy"],
            locale=row["locale"], timezone=row["timezone"],
            voice_profile=json.loads(row["voice_profile_json"]), topics=json.loads(row["topics_json"]),
            disclosure_profile=json.loads(row["disclosure_profile_json"]),
            allowed_channel_classes=json.loads(row["allowed_channel_classes_json"]),
            status=row["status"],
        )

    def eligible_personas(self, channel_class: str, *, tenant_id: str = "") -> List[Persona]:
        rows = self.conn.execute(
            "SELECT * FROM personas WHERE status='active' AND (?='' OR tenant_id=?)", (tenant_id, tenant_id)
        ).fetchall()
        out = []
        for row in rows:
            classes = json.loads(row["allowed_channel_classes_json"])
            if not classes or channel_class in classes:
                p = self.get_persona(row["persona_id"])
                if p is not None:
                    out.append(p)
        return out

    def register_account(
        self,
        *,
        tenant_id: str,
        site_id: str,
        persona_id: Optional[str],
        credential_ref: str,
        session_ref: str,
        totp_ref: str = "",
        ip_ref: str = "",
        profile_ref: str = "",
        multi_account_allowed: bool = False,
        ban_state: Optional[BanState] = None,
        fresh_profile: bool = True,
        fresh_ip: bool = True,
        reuses_ip: bool = False,
        reuses_profile: bool = False,
    ) -> str:
        """Register an account reference. Enforces multi-account policy + accountReuse gate.

        Second account on the same site requires the verified entitlement gate;
        single-account platforms keep personas as content variants (no new account).
        Secrets stay vault:// (DB trigger rejects plaintext).
        """
        existing = self.conn.execute(
            "SELECT account_id FROM accounts WHERE site_id=? AND status IN ('active','quarantined')",
            (site_id,),
        ).fetchall()
        if existing:
            if not multi_account_allowed:
                raise PermissionError(f"platform {site_id} permits one account only; personas stay content variants")
            assert_reopen_allowed(
                PlatformPolicy(multi_account_allowed=True),
                ban_state or BanState(),
                fresh_profile=fresh_profile, fresh_ip=fresh_ip,
                reuses_ip=reuses_ip, reuses_profile=reuses_profile,
            )
        account_id = uuid.uuid4().hex
        now = _utc_now()
        with self.conn:
            self.conn.execute(
                """INSERT INTO accounts(account_id, tenant_id, site_id, persona_id, credential_ref,
                   session_ref, totp_ref, ip_ref, profile_ref, status, last_verified_at, created_at, updated_at)
                   VALUES(?,?,?,?,?,?,?,?,?,'active',?, ?,?)""",
                (account_id, tenant_id, site_id, persona_id, credential_ref, session_ref,
                 totp_ref, ip_ref, profile_ref, now, now, now),
            )
        return account_id

    def session_health(self, account_id: str) -> str:
        """active | quarantined | dead | unknown. Access challenges quarantine."""
        row = self.conn.execute("SELECT status FROM accounts WHERE account_id=?", (account_id,)).fetchone()
        if not row:
            return "unknown"
        return str(row["status"])

    def quarantine_account(self, account_id: str, reason: str) -> None:
        with self.conn:
            self.conn.execute("UPDATE accounts SET status='quarantined', updated_at=? WHERE account_id=?",
                              (_utc_now(), account_id))

    def resolve_totp(self, account_id: str, *, at: Optional[int] = None) -> str:
        """Generate authorized TOTP from the account's vault totp_ref (never stored)."""
        row = self.conn.execute("SELECT totp_ref FROM accounts WHERE account_id=?", (account_id,)).fetchone()
        if not row or not row["totp_ref"]:
            raise ValueError(f"no totp_ref for account {account_id}")
        secret = resolve_secret(row["totp_ref"], self.vault)
        if not secret:
            raise ValueError(f"cannot resolve {row['totp_ref']}")
        return totp_now(secret, at=at)
