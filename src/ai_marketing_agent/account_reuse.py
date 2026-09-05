"""Verified entitlement gate for opening a (second) platform account.

Canonical rule: schemas/policy-contract.json:accountReuse
(same-IP-or-same-profile-second-account-forbidden, narrowed):
  - Banned/suspended account -> NEVER reopen (fresh pair included) -> quarantine/appeal only.
  - No ban + platform explicitly permits multi-account -> fresh profile AND fresh IP
    together allowed as a new audited identity.
  - Reusing only IP or only profile alone -> always forbidden (linkable).

Fail-closed: unknown/ambiguous entitlement -> PermissionError.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class BanState:
    banned: bool = False
    suspended: bool = False
    reason: Optional[str] = None

    @property
    def blocked(self) -> bool:
        return self.banned or self.suspended


@dataclass(frozen=True)
class PlatformPolicy:
    multi_account_allowed: bool = False
    source: Optional[str] = None  # e.g. policy URL / registry version for audit


def assert_reopen_allowed(
    platform_policy: PlatformPolicy,
    ban_state: BanState,
    *,
    fresh_profile: bool,
    fresh_ip: bool,
    reuses_ip: bool = False,
    reuses_profile: bool = False,
) -> None:
    """Raise PermissionError unless reopening is explicitly allowed.

    Rules (in order):
      1. Ban/suspension present -> deny (quarantine/appeal only), even with fresh pair.
      2. Same IP alone or same profile alone reused -> deny.
      3. Fresh profile AND fresh IP required together.
      4. Platform must explicitly permit multi-account.
    """
    if ban_state.blocked:
        raise PermissionError(
            f"reopen denied: account is {'banned' if ban_state.banned else 'suspended'} "
            f"({ban_state.reason or 'no reason'}); quarantine/appeal only"
        )
    if reuses_ip or reuses_profile:
        raise PermissionError("reopen denied: must not reuse the previous IP or browser profile alone")
    if not (fresh_profile and fresh_ip):
        raise PermissionError("reopen denied: requires BOTH a fresh browser profile AND a fresh IP")
    if not platform_policy.multi_account_allowed:
        raise PermissionError("reopen denied: platform does not explicitly permit multi-account")


def audit_record(
    *,
    tenant_id: Optional[str],
    platform: str,
    allowed: bool,
    reason: str,
) -> dict:
    """Redacted audit record for a reopen decision (no IPs, profiles, or secrets)."""
    return {
        "event": "account_reopen_allowed" if allowed else "account_reopen_denied",
        "detail_json": {
            "tenant": tenant_id,
            "platform": platform,
            "allowed": allowed,
            "reason": reason,
        },
    }
