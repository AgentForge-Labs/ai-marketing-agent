"""Privacy primitives (#24) — consent ledger, retention cutoff, erasure.

Pure helpers + an in-memory ConsentRegistry for the runner/orchestrator path;
durable consent lives in SaaSStore.consents (migration 007). No PII is logged:
subject ids are opaque references, never emails or raw secrets.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Tuple


def _utc_now() -> float:
    return datetime.now(timezone.utc).timestamp()


@dataclass
class ConsentRecord:
    tenant_id: str
    subject_id: str
    purpose: str
    granted: bool = True
    decided_at: float = field(default_factory=_utc_now)


class ConsentRegistry:
    """Fail-closed: unknown subject/purpose => no consent."""

    def __init__(self) -> None:
        self._records: Dict[Tuple[str, str, str], ConsentRecord] = {}

    def grant(self, tenant_id: str, subject_id: str, purpose: str, *, now: float | None = None) -> ConsentRecord:
        rec = ConsentRecord(tenant_id, subject_id, purpose, True, now if now is not None else _utc_now())
        self._records[(tenant_id, subject_id, purpose)] = rec
        return rec

    def withdraw(self, tenant_id: str, subject_id: str, purpose: str, *, now: float | None = None) -> ConsentRecord:
        rec = ConsentRecord(tenant_id, subject_id, purpose, False, now if now is not None else _utc_now())
        self._records[(tenant_id, subject_id, purpose)] = rec
        return rec

    def has_consent(self, tenant_id: str, subject_id: str, purpose: str) -> bool:
        rec = self._records.get((tenant_id, subject_id, purpose))
        return bool(rec and rec.granted)


def retention_cutoff(retention_days: int, *, now: float | None = None) -> float:
    """Unix-ts before which records must be purged (storage limitation)."""
    if retention_days <= 0:
        raise ValueError("retention_days must be positive")
    return (now if now is not None else _utc_now()) - retention_days * 86400.0


def partition_expired(
    items: List[Any], get_ts: Callable[[Any], float], cutoff: float
) -> Tuple[List[Any], List[Any]]:
    """Split (keep, purged) at cutoff. Pure — caller deletes/loads durably."""
    keep, purged = [], []
    for item in items:
        (keep if get_ts(item) >= cutoff else purged).append(item)
    return keep, purged


def erase_subject(items: List[Any], get_subject: Callable[[Any], str], subject_id: str) -> Tuple[List[Any], int]:
    """GDPR Art.17: drop every record belonging to subject_id. Returns (kept, erased_count)."""
    kept = [i for i in items if get_subject(i) != subject_id]
    return kept, len(items) - len(kept)
