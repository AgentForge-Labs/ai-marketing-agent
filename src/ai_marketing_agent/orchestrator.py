"""Distribution Orchestrator (Phase 9, #13) — next-best-action, not blind iteration.

Score (docs/02 §3):
    channel_score = buyer_intent x product_fit x audience_fit x policy_confidence
                    x automation_reliability x historical_conversion x freshness
                    / expected_cost
Scheduling respects timezone windows, quotas, cooldowns, session health and
content freshness. Tenant kill switch stops everything. Parallel workers share
per-channel/account concurrency caps.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _utc_now() -> float:
    return datetime.now(timezone.utc).timestamp()


@dataclass
class Campaign:
    campaign_id: str
    tenant_id: str
    paused: bool = False
    budget: float = 0.0
    spent: float = 0.0
    weights: Dict[str, float] = field(default_factory=dict)


@dataclass
class ChannelCandidate:
    channel_id: str
    buyer_intent: float = 0.0
    product_fit: float = 0.0
    audience_fit: float = 0.0
    policy_confidence: float = 0.0
    automation_reliability: float = 0.0
    historical_conversion: float = 0.0
    freshness: float = 1.0
    expected_cost: float = 1.0
    cooldown_until: float = 0.0
    session_healthy: bool = True
    quota_remaining: int = 1
    scheduled_at: float = 0.0


def score_channel(candidate: ChannelCandidate, campaign: Optional[Campaign] = None) -> float:
    """Expected-value score. Zero-clamped inputs; non-positive cost -> 0 (fail-closed)."""
    if candidate.expected_cost <= 0:
        return 0.0
    w = (campaign.weights if campaign else {}) or {}
    def weighted(value: float, name: str) -> float:
        return max(0.0, value) ** w.get(name, 1.0)
    score = (
        weighted(candidate.buyer_intent, "buyer_intent")
        * weighted(candidate.product_fit, "product_fit")
        * weighted(candidate.audience_fit, "audience_fit")
        * weighted(candidate.policy_confidence, "policy_confidence")
        * weighted(candidate.automation_reliability, "automation_reliability")
        * weighted(candidate.historical_conversion, "historical_conversion")
        * weighted(candidate.freshness, "freshness")
        / candidate.expected_cost
    )
    return max(0.0, score)


@dataclass
class OrchestratorState:
    in_flight_per_channel: Dict[str, int] = field(default_factory=dict)
    in_flight_per_account: Dict[str, int] = field(default_factory=dict)
    max_per_channel: int = 1
    max_per_account: int = 1


def next_best_action(
    campaign: Campaign,
    candidates: List[ChannelCandidate],
    *,
    state: Optional[OrchestratorState] = None,
    account_id: str = "",
    now: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """Pick the highest-score eligible candidate. None means: do nothing (fail-closed).

    Eligibility: campaign not paused/kill-switched, budget left, session healthy,
    quota left, cooldown passed, scheduled time reached, concurrency caps free.
    """
    ts = now if now is not None else _utc_now()
    state = state or OrchestratorState()
    if campaign.paused:
        return None
    if campaign.budget > 0 and campaign.spent >= campaign.budget:
        return None
    ranked = sorted(
        ((score_channel(c, campaign), c) for c in candidates),
        key=lambda pair: pair[0], reverse=True,
    )
    for score, cand in ranked:
        if score <= 0:
            continue
        if not cand.session_healthy or cand.quota_remaining <= 0:
            continue
        if cand.cooldown_until > ts or cand.scheduled_at > ts:
            continue
        if state.in_flight_per_channel.get(cand.channel_id, 0) >= state.max_per_channel:
            continue
        if account_id and state.in_flight_per_account.get(account_id, 0) >= state.max_per_account:
            continue
        state.in_flight_per_channel[cand.channel_id] = state.in_flight_per_channel.get(cand.channel_id, 0) + 1
        if account_id:
            state.in_flight_per_account[account_id] = state.in_flight_per_account.get(account_id, 0) + 1
        return {"channel_id": cand.channel_id, "score": score, "at": ts}
    return None


def release(state: OrchestratorState, channel_id: str, account_id: str = "") -> None:
    """Worker calls on completion so caps free up."""
    if state.in_flight_per_channel.get(channel_id, 0) > 0:
        state.in_flight_per_channel[channel_id] -= 1
    if account_id and state.in_flight_per_account.get(account_id, 0) > 0:
        state.in_flight_per_account[account_id] -= 1
