"""Engagement Bot (Phase 8, #12) — policy-eligible inbound engagement only.

Eligible kinds: reply (comments on owned content), answer (inbound questions),
follow_up (launch/listing thread), update (clarification), route (lead/support).
Prohibited (hard-coded, fail-closed): like, upvote, vote, review, mass_dm,
mass_comment, amplify.

Pipeline per event: consent/policy gate -> claim+disclosure+similarity check ->
rate-limit check -> auto execution record / quarantine. No LLM calls here;
response text is assembled from thread context + verified product facts.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional

from .content_core import jaccard_similarity, verify_claims

ELIGIBLE_KINDS = frozenset({"reply", "answer", "follow_up", "update", "route"})

PROHIBITED_KINDS = frozenset({
    "like", "upvote", "vote", "review", "mass_dm", "dm_blast",
    "mass_comment", "amplify", "brigade",
})


@dataclass
class EngagementEvent:
    kind: str
    thread_id: str
    account_id: str
    thread_context: str = ""
    opted_in: bool = False
    is_owned_content: bool = False
    recent_texts: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class GateDecision:
    allowed: bool
    reason: str


class RateLimiter:
    """Sliding-window per (account, thread) limiter (in-memory prototype)."""

    def __init__(self, *, max_actions: int = 3, window_seconds: int = 3600) -> None:
        self.max_actions = max_actions
        self.window_seconds = window_seconds
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)

    def check_and_record(self, account_id: str, thread_id: str, *, now: Optional[float] = None) -> bool:
        """True if allowed (and recorded), False if rate-limited."""
        ts = now if now is not None else time.time()
        key = f"{account_id}:{thread_id}"
        window = self._hits[key]
        while window and ts - window[0] > self.window_seconds:
            window.popleft()
        if len(window) >= self.max_actions:
            return False
        window.append(ts)
        return True


def gate_event(event: EngagementEvent) -> GateDecision:
    """Consent/policy gate. Prohibited kinds and missing consent fail closed."""
    if event.kind in PROHIBITED_KINDS:
        return GateDecision(False, f"prohibited_kind:{event.kind}")
    if event.kind not in ELIGIBLE_KINDS:
        return GateDecision(False, f"unknown_kind:{event.kind}")
    if event.kind in ("reply", "answer", "follow_up", "update") and not event.is_owned_content:
        return GateDecision(False, "not_owned_content")
    if event.kind == "route" and not event.opted_in:
        return GateDecision(False, "missing_opt_in")
    return GateDecision(True, "eligible")


def draft_reply(
    event: EngagementEvent,
    profile: Dict[str, Any],
    *,
    answer: str,
    max_similarity: float = 0.20,
) -> str:
    """Assemble a reply from thread context + verified facts. Raises on violation."""
    text = f"{answer}".strip()
    if not text:
        raise ValueError("empty reply")
    violations = verify_claims(text, profile)
    if violations:
        raise ValueError(f"claim violations: {violations}")
    for existing in event.recent_texts:
        if jaccard_similarity(text, existing) > max_similarity:
            raise ValueError(f"similarity above threshold {max_similarity}")
    # Disclosure: replies on owned brand content carry #ad by default policy.
    if "#ad" not in text:
        text = f"{text} #ad"
    return text


@dataclass
class EngagementOutcome:
    executed: bool
    reason: str
    reply: str = ""
    audit: Dict[str, Any] = field(default_factory=dict)


def handle_event(
    event: EngagementEvent,
    profile: Dict[str, Any],
    *,
    answer: str,
    limiter: Optional[RateLimiter] = None,
    max_similarity: float = 0.20,
) -> EngagementOutcome:
    """Full pipeline: gate -> draft/validate -> rate-limit -> execute/quarantine."""
    gate = gate_event(event)
    if not gate.allowed:
        return EngagementOutcome(False, gate.reason, audit={"gate": gate.reason})
    try:
        reply = draft_reply(event, profile, answer=answer, max_similarity=max_similarity)
    except ValueError as e:
        return EngagementOutcome(False, f"validation:{e}", audit={"gate": "validation_failed"})
    if limiter is not None and not limiter.check_and_record(event.account_id, event.thread_id):
        return EngagementOutcome(False, "rate_limited", audit={"gate": "rate_limited"})
    return EngagementOutcome(True, "executed", reply=reply,
                             audit={"gate": "executed", "thread": event.thread_id})
