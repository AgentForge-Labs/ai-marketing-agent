"""Bounded policy crawler — read-only discovery of API/OAuth availability and policy facts.

Design constraints (same as url_preflight): public-network only, no login, no form
submit, no cookies/sessions, bounded time. The crawler never invents policy: every
field is either observed (preflight/API probe) or inherited from the canonical
risk decision, and the whole observation is hashed into crawler_hash.

Stale/contradictory results must route to auto_quarantine, never to silent execution.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from .policy_registry import PolicyRecord, _utc_now
from .risk_router import RouteDecision

API_HINT_PATHS = ("/.well-known/oauth-authorization-server", "/api", "/api/docs", "/openapi.json")


@dataclass(frozen=True)
class CrawlSignals:
    domain: str
    reachable: bool = False
    final_url: str = ""
    api_hint_paths: List[str] = None  # type: ignore[assignment]
    notes: List[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        object.__setattr__(self, "api_hint_paths", list(self.api_hint_paths or []))
        object.__setattr__(self, "notes", list(self.notes or []))


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def crawl_policy(
    *,
    domain: str,
    source_url: str,
    decision: Optional[RouteDecision] = None,
    preflight: Optional[Dict[str, Any]] = None,
    api_probe: Optional[Callable[[str], bool]] = None,
) -> PolicyRecord:
    """Build a PolicyRecord draft from bounded observations + canonical risk decision.

    - `decision`: risk_router output for the intended action (drives execution +
      allowed/denied actions; None -> auto_quarantine).
    - `preflight`: url_preflight result dict (reachability evidence).
    - `api_probe`: optional bounded callable(path) -> bool for API hint paths;
      default: no probing (all hints recorded as unobserved, never assumed).
    """
    allowed: List[str] = []
    denied: List[str] = []
    execution = "auto_quarantine"
    api_hints: List[str] = []
    notes: List[str] = []

    if preflight is not None:
        if preflight.get("status") not in ("reachable", "redirected"):
            notes.append(f"preflight:{preflight.get('status')}")
        final_url = str(preflight.get("final_url") or preflight.get("normalized_url") or "")
    else:
        final_url = ""

    if api_probe is not None:
        for path in API_HINT_PATHS:
            try:
                if api_probe(path):
                    api_hints.append(path)
            except Exception:
                notes.append(f"api_probe_failed:{path}")

    if decision is not None and decision.should_execute:
        execution = decision.execution_mode
        allowed.append(decision.action)
        notes.append(f"risk:{decision.main_risk}/{decision.selected_medium}")
    else:
        denied.append(decision.action if decision is not None else "all")
        notes.append("no-executable-decision")

    if final_url:
        notes.append(f"final:{final_url}")

    record = PolicyRecord(
        domain=domain,
        version=0,  # assigned by PolicyRegistry.upsert_policy
        source_url=source_url,
        execution=execution,
        allowed_actions=allowed,
        denied_actions=denied,
        captcha_policy="auto_ensemble" if execution != "auto_quarantine" else "abort_and_notify",
        account_rules={},
        quotas={},
        disclosure_rules={},
        crawler_hash="",
        checked_at=_utc_now(),
    )
    blob = json.dumps(
        {"domain": domain, "source_url": source_url, "execution": execution, "allowed": allowed,
         "denied": denied, "api_hints": api_hints, "notes": notes, "final_url": final_url},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    )
    return PolicyRecord(
        domain=record.domain, version=record.version, source_url=record.source_url,
        execution=record.execution, allowed_actions=record.allowed_actions,
        denied_actions=record.denied_actions, captcha_policy=record.captcha_policy,
        account_rules=record.account_rules, quotas=record.quotas,
        disclosure_rules=record.disclosure_rules,
        crawler_hash=_sha256_text(blob), checked_at=record.checked_at,
    )
