"""Evasion Layer / anomaly controller (Phase 7, #11) — defensive only.

Detects anomalies and responds with throttle/cooldown/pause/refresh/quarantine.
It NEVER implements ban evasion (no identity/IP rotation, no blocked-endpoint
submission). Dead-pool records banned accounts/IPs/profiles permanently.

Signals in: rate-limit headers/statuses, repeated failures, account restrictions,
CAPTCHA/challenge, session/auth drift, form drift, redirect loops, content
similarity, duplicate submits, adapter-family error bursts.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class AnomalySignals:
    rate_limited: bool = False
    failure_burst: int = 0  # consecutive failures
    failure_burst_threshold: int = 3
    account_restricted: bool = False
    banned: bool = False
    challenge: bool = False
    session_drift: bool = False
    form_drift: bool = False
    redirect_loop: bool = False
    duplicate_risk: bool = False
    family_errors: int = 0
    family_error_threshold: int = 5


@dataclass
class EvasionDecision:
    action: str  # proceed | throttle | cooldown | pause_family | refresh_policy | quarantine | dead_pool
    reason: str
    cooldown_minutes: int = 0
    audit: Dict[str, Any] = field(default_factory=dict)


def evaluate(signals: AnomalySignals) -> EvasionDecision:
    """Deterministic signal -> response mapping. Ban always wins (dead_pool)."""
    if signals.banned or signals.account_restricted:
        return EvasionDecision(
            action="dead_pool",
            reason="ban_or_restriction: quarantine + dead-pool, never rotate identity/IP",
            audit={"at": _utc_now()},
        )
    if signals.redirect_loop or signals.session_drift:
        return EvasionDecision(action="refresh_policy", reason="session_or_redirect_drift",
                               audit={"at": _utc_now()})
    if signals.form_drift:
        return EvasionDecision(action="refresh_policy", reason="form_drift: remap adapter",
                               audit={"at": _utc_now()})
    if signals.family_errors >= signals.family_error_threshold:
        return EvasionDecision(action="pause_family", reason="adapter_family_burst",
                               audit={"at": _utc_now()})
    if signals.failure_burst >= signals.failure_burst_threshold:
        return EvasionDecision(action="cooldown", reason="failure_burst",
                               cooldown_minutes=60, audit={"at": _utc_now()})
    if signals.rate_limited:
        return EvasionDecision(action="throttle", reason="rate_limited",
                               cooldown_minutes=15, audit={"at": _utc_now()})
    if signals.challenge or signals.duplicate_risk:
        return EvasionDecision(action="quarantine", reason="challenge_or_duplicate_risk",
                               audit={"at": _utc_now()})
    return EvasionDecision(action="proceed", reason="no_anomaly", audit={"at": _utc_now()})


@dataclass
class DeadPool:
    """Banned accounts/IPs/profiles. Append-only in spirit: entries are never
    removed or reused (reuse would be ban evasion)."""
    entries: List[Dict[str, Any]] = field(default_factory=list)

    def add(self, *, kind: str, value_hash: str, reason: str, tenant_id: str = "") -> Dict[str, Any]:
        """Store ONLY a hash of the identifier, never the raw IP/profile/account."""
        if kind not in ("account", "ip", "profile"):
            raise ValueError(f"unknown dead-pool kind: {kind!r}")
        entry = {"kind": kind, "value_hash": value_hash, "reason": reason,
                 "tenant": tenant_id, "at": _utc_now()}
        self.entries.append(entry)
        return entry

    def is_dead(self, kind: str, value_hash: str) -> bool:
        return any(e["kind"] == kind and e["value_hash"] == value_hash for e in self.entries)


def check_dead_pool(pool: DeadPool, *, kind: str, value_hash: str) -> Optional[Dict[str, Any]]:
    """Fail-closed lookup: dead entries must never be reused."""
    for entry in pool.entries:
        if entry["kind"] == kind and entry["value_hash"] == value_hash:
            return {"allowed": False, "reason": "dead_pool_hit", "entry": entry}
    return None
