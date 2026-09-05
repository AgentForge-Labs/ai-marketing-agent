"""Rollout gate (Phase 12, #22) — expansion gate per adapter family/channel.

Every gate item must pass before a family/channel expands; rollout proceeds
progressively (verified P0/P1 first, then P2/P3 by measured health).
Fail-closed: any missing evidence blocks expansion (no silent rollout).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

GATE_ITEMS = (
    "policy_current",
    "preflight_current",
    "schema_valid",
    "dry_run_pass",
    "idempotency_ok",
    "assertion_deterministic",
    "security_redaction_pass",
    "pilot_runs_3x",
    "no_duplicate",
    "no_access_control_bypass",
    "business_outcome_captured",
)

PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


@dataclass
class GateEvidence:
    passed: Dict[str, bool] = field(default_factory=dict)

    def missing(self) -> List[str]:
        return [item for item in GATE_ITEMS if not self.passed.get(item, False)]


@dataclass(frozen=True)
class GateVerdict:
    expand: bool
    missing: List[str]
    priority: str


def evaluate_gate(evidence: GateEvidence, *, priority: str = "P3") -> GateVerdict:
    """All 11 items required. Unknown priority fails closed."""
    if priority not in PRIORITY_ORDER:
        return GateVerdict(False, ["unknown_priority"], priority)
    missing = evidence.missing()
    return GateVerdict(not missing, missing, priority)


def rollout_order(families: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Progressive order: verified P0/P1 first, then P2/P3 sorted by health desc.

    Each family: {"family": str, "priority": "P0".."P3", "health": float 0..1,
    "verified": bool}. Unverified or unknown priority go last (fail-closed order).
    """
    def rank(family: Dict[str, Any]) -> tuple:
        prio = PRIORITY_ORDER.get(str(family.get("priority", "")), 9)
        verified = 0 if family.get("verified") else 1
        try:
            health = float(family.get("health", 0.0))
        except (TypeError, ValueError):
            health = 0.0
        return (verified, prio, -health, str(family.get("family", "")))

    return sorted(families, key=rank)
