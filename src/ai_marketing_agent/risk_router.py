"""Deterministic action × execution-medium risk routing.

The canonical CSV declares one cell per action. Each cell starts with the action's
main risk and then preserves the risk of every execution medium. This module does
not trust the declared aggregate: it parses and recomputes the minimum supported
medium risk before routing.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

RISK_ORDER: dict[str, int] = {
    "Low": 1,
    "Moderate": 2,
    "High": 3,
    "Very High": 4,
    "Critical": 5,
}

MEDIA_PRIORITY: tuple[str, ...] = (
    "official_api",
    "cli_sdk",
    "webhook_bot",
    "unified_api",
    "public_http",
    "local_browser_agent",
    "browser_extension",
)

MEDIA = frozenset(MEDIA_PRIORITY)

ACTION_COLUMNS: dict[str, str] = {
    "public_browse": "Public Browse Action Risk",
    "authenticated_browse": "Authenticated Browse Action Risk",
    "data_collection": "Data Collection Action Risk",
    "own_content_submit_post": "Own Content Submit/Post Action Risk",
    "comment_reply": "Comment/Reply Action Risk",
    "dm_outreach": "DM/Outreach Action Risk",
    "vote_like_follow": "Vote/Like/Follow Action Risk",
    "review_rating": "Review/Rating Action Risk",
}

ACTION_ALIASES: dict[str, str] = {
    "browse": "public_browse",
    "public": "public_browse",
    "public_browse": "public_browse",
    "authenticated": "authenticated_browse",
    "authenticated_browse": "authenticated_browse",
    "auth_browse": "authenticated_browse",
    "collect": "data_collection",
    "data": "data_collection",
    "data_collection": "data_collection",
    "post": "own_content_submit_post",
    "publish": "own_content_submit_post",
    "submit": "own_content_submit_post",
    "own_content_submit_post": "own_content_submit_post",
    "comment": "comment_reply",
    "reply": "comment_reply",
    "comment_reply": "comment_reply",
    "dm": "dm_outreach",
    "outreach": "dm_outreach",
    "dm_outreach": "dm_outreach",
    "vote": "vote_like_follow",
    "like": "vote_like_follow",
    "follow": "vote_like_follow",
    "vote_like_follow": "vote_like_follow",
    "review": "review_rating",
    "rating": "review_rating",
    "review_rating": "review_rating",
    # Account-lifecycle actions (#33): known names; cells arrive via pilot
    # overrides until the canonical CSV carries Register/Login columns.
    "register": "register",
    "signup": "register",
    "sign_up": "register",
    "login": "login",
    "signin": "login",
    "sign_in": "login",
    "log_in": "login",
}

# Known actions without canonical CSV columns yet: recognized by the router
# but quarantined unless a reviewed pilot override supplies the cell.
ACTIONS_WITHOUT_COLUMNS = frozenset({"register", "login"})

API_MEDIA = frozenset({"official_api", "cli_sdk", "webhook_bot", "unified_api"})
BROWSER_MEDIA = frozenset({"local_browser_agent", "browser_extension"})
class RiskCellError(ValueError):
    """Raised when a canonical action-risk cell is malformed or inconsistent."""


@dataclass(frozen=True, slots=True)
class ActionRisk:
    declared_main_risk: str
    medium_risks: Mapping[str, str]
    best_medium: str
    note: str

    @property
    def main_risk(self) -> str:
        """Validated/recomputed main risk (equal to declared_main_risk)."""
        return self.declared_main_risk


@dataclass(frozen=True, slots=True)
class RouteDecision:
    channel_rank: int | None
    site: str
    domain: str
    action: str
    main_risk: str
    selected_medium: str
    execution_mode: str
    should_execute: bool
    reason: str
    medium_risks: Mapping[str, str]
    note: str = ""
    decision_mode: str = "auto_quarantine"

    def to_dict(self) -> dict[str, object]:
        return {
            "channel_rank": self.channel_rank,
            "site": self.site,
            "domain": self.domain,
            "action": self.action,
            "main_risk": self.main_risk,
            "selected_medium": self.selected_medium,
            "execution_mode": self.execution_mode,
            "should_execute": self.should_execute,
            "reason": self.reason,
            "medium_risks": dict(self.medium_risks),
            "note": self.note,
            "decision_mode": self.decision_mode,
        }


def _best_supported_medium(medium_risks: Mapping[str, str]) -> tuple[str, str]:
    supported = {k: v for k, v in medium_risks.items() if v != "N/A"}
    if not supported:
        return "N/A", "none"
    floor = min(RISK_ORDER[v] for v in supported.values())
    main = next(name for name, score in RISK_ORDER.items() if score == floor)
    best = next(
        medium
        for medium in MEDIA_PRIORITY
        if medium in supported and RISK_ORDER[supported[medium]] == floor
    )
    return main, best


def parse_action_risk(value: str) -> ActionRisk:
    """Parse and validate one canonical action-risk cell.

    Fail-closed invariants:
    * every known medium must occur exactly once;
    * no unknown medium/risk is accepted;
    * N/A media do not participate in the aggregate;
    * declared main risk must equal the recomputed minimum;
    * declared best medium must equal deterministic priority among minimum-risk media.
    """

    if not isinstance(value, str) or not value.strip():
        raise RiskCellError("action-risk cell is empty")

    parts = [part.strip() for part in value.split(" | ")]
    if len(parts) < 3:
        raise RiskCellError("action-risk cell must contain main risk, media, and best medium")

    declared_main = parts[0]
    if declared_main not in {*RISK_ORDER, "N/A"}:
        raise RiskCellError(f"unknown main risk: {declared_main!r}")

    medium_parts = [piece.strip() for piece in parts[1].split(";") if piece.strip()]
    medium_risks: dict[str, str] = {}
    for piece in medium_parts:
        if "=" not in piece:
            raise RiskCellError(f"invalid medium declaration: {piece!r}")
        medium, risk = (p.strip() for p in piece.split("=", 1))
        if medium not in MEDIA:
            raise RiskCellError(f"unknown execution medium: {medium!r}")
        if medium in medium_risks:
            raise RiskCellError(f"duplicate execution medium: {medium!r}")
        if risk not in {*RISK_ORDER, "N/A"}:
            raise RiskCellError(f"unknown medium risk for {medium}: {risk!r}")
        medium_risks[medium] = risk

    missing = MEDIA.difference(medium_risks)
    if missing:
        raise RiskCellError(f"missing execution media: {', '.join(sorted(missing))}")

    if not parts[2].startswith("best="):
        raise RiskCellError("missing best=<medium> declaration")
    declared_best = parts[2][5:].strip()
    if declared_best != "none" and declared_best not in MEDIA:
        raise RiskCellError(f"unknown best execution medium: {declared_best!r}")

    note = ""
    for extra in parts[3:]:
        if extra.startswith("note="):
            if note:
                raise RiskCellError("duplicate note field")
            note = extra[5:].strip()
        else:
            raise RiskCellError(f"unknown action-risk cell field: {extra!r}")

    recomputed_main, recomputed_best = _best_supported_medium(medium_risks)
    if declared_main != recomputed_main:
        raise RiskCellError(
            f"declared main risk {declared_main!r} does not match supported-medium minimum {recomputed_main!r}"
        )
    if declared_best != recomputed_best:
        raise RiskCellError(
            f"declared best medium {declared_best!r} does not match deterministic best {recomputed_best!r}"
        )

    return ActionRisk(
        declared_main_risk=declared_main,
        medium_risks=MappingProxyType(dict(medium_risks)),
        best_medium=declared_best,
        note=note,
    )


def normalize_action(action: str) -> str | None:
    if not isinstance(action, str):
        return None
    key = action.strip().lower().replace("-", "_").replace("/", "_").replace(" ", "_")
    while "__" in key:
        key = key.replace("__", "_")
    return ACTION_ALIASES.get(key)


def execution_mode_for(medium: str) -> str:
    if medium in API_MEDIA:
        return "api_auto"
    if medium in BROWSER_MEDIA:
        return "browser_auto"
    if medium == "public_http":
        return "auto_full"
    return "auto_quarantine"


class PlatformRiskRouter:
    """Select the lowest-risk supported route for a requested channel action."""

    def __init__(self, *, max_autonomous_risk: str = "High") -> None:
        if max_autonomous_risk not in {"Low", "Moderate", "High"}:
            raise ValueError(
                "max autonomous risk may only be 'Low', 'Moderate' or 'High'; "
                "Very High/Critical routes are always fail-closed"
            )
        self.max_autonomous_risk = max_autonomous_risk
        self.max_autonomous_risk_score = RISK_ORDER[max_autonomous_risk]

    @staticmethod
    def _quarantine(
        *,
        channel_rank: int | None,
        site: str,
        domain: str,
        action: str,
        reason: str,
        main_risk: str = "N/A",
        medium_risks: Mapping[str, str] | None = None,
        note: str = "",
    ) -> RouteDecision:
        return RouteDecision(
            channel_rank=channel_rank,
            site=site,
            domain=domain,
            action=action,
            main_risk=main_risk,
            selected_medium="none",
            execution_mode="auto_quarantine",
            should_execute=False,
            reason=reason,
            medium_risks=medium_risks or {},
            note=note,
            decision_mode="auto_quarantine",
        )

    def route(self, channel: object, action: str) -> RouteDecision:
        """Route a requested action.

        `channel` is intentionally structural: ChannelCatalogue.Channel provides rank,
        site, domain, and action_risks, but keeping this method decoupled avoids a
        circular import and makes it easy to test with immutable records.
        """

        rank = getattr(channel, "rank", None)
        site = str(getattr(channel, "site", ""))
        domain = str(getattr(channel, "domain", ""))
        action_risks = getattr(channel, "action_risks", {})

        normalized = normalize_action(action)
        if normalized is None:
            return self._quarantine(
                channel_rank=rank,
                site=site,
                domain=domain,
                action=str(action),
                reason="unknown action; fail closed",
            )

        risk = action_risks.get(normalized)
        if not isinstance(risk, ActionRisk):
            reason = (
                f"no matrix cell for {normalized!r} yet; fail closed"
                if normalized in ACTIONS_WITHOUT_COLUMNS
                else "action risk is unavailable or invalid; fail closed"
            )
            return self._quarantine(
                channel_rank=rank,
                site=site,
                domain=domain,
                action=normalized,
                reason=reason,
            )

        if risk.main_risk == "N/A" or risk.best_medium == "none":
            return self._quarantine(
                channel_rank=rank,
                site=site,
                domain=domain,
                action=normalized,
                reason="no supported execution medium for requested action",
                main_risk=risk.main_risk,
                medium_risks=risk.medium_risks,
                note=risk.note,
            )

        score = RISK_ORDER[risk.main_risk]
        if score > self.max_autonomous_risk_score:
            return self._quarantine(
                channel_rank=rank,
                site=site,
                domain=domain,
                action=normalized,
                reason=(
                    f"minimum supported-medium risk {risk.main_risk} exceeds autonomous threshold "
                    f"{self.max_autonomous_risk}"
                ),
                main_risk=risk.main_risk,
                medium_risks=risk.medium_risks,
                note=risk.note,
            )

        mode = execution_mode_for(risk.best_medium)
        if mode == "auto_quarantine":
            return self._quarantine(
                channel_rank=rank,
                site=site,
                domain=domain,
                action=normalized,
                reason="selected medium has no executable runtime mapping; fail closed",
                main_risk=risk.main_risk,
                medium_risks=risk.medium_risks,
                note=risk.note,
            )

        decision_mode = "auto_full" if risk.main_risk == "Low" else "auto_with_verification"
        return RouteDecision(
            channel_rank=rank,
            site=site,
            domain=domain,
            action=normalized,
            main_risk=risk.main_risk,
            selected_medium=risk.best_medium,
            execution_mode=mode,
            should_execute=True,
            reason="selected minimum-risk supported execution medium for requested action",
            medium_risks=risk.medium_risks,
            note=risk.note,
            decision_mode=decision_mode,
        )
