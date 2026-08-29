"""Action-scoped execution authorization — biometric her zaman, CAPTCHA ensemble per-action.

Risk site çapında değil, sitede yapılacak eyleme göre belirlenir (Siteler ve riskler dokümanı).
Coarse site/category risk is informational and cannot grant execution.
- Biometric mouse (wassim-sayah/biometric-mouse) HER ZAMAN kullanılır for Low/Moderate/High browser actions (even if site is risky, per-action Very High/Critical değilse).
- CAPTCHA/security challenge for Low/Moderate/High may use auto_ensemble (2captcha/2captcha-python → aydinnyunus/ai-captcha-bypass → teal33t/captcha_bypass) with vault:// keys and biometric mouse; Very High/Critical always quarantine.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .risk_router import BROWSER_MEDIA, RISK_ORDER, RouteDecision

_AUTH_TOKEN = object()
_CHALLENGE_MODES = frozenset({"none", "first_party", "sandbox", "auto_ensemble"})


@dataclass(frozen=True, slots=True, init=False)
class ExecutionAuthorization:
    channel_rank: int | None
    domain: str
    action: str
    main_risk: str
    selected_medium: str
    decision_mode: str
    capabilities: frozenset[str]
    challenge_mode: str

    def __init__(
        self,
        *,
        _token: object,
        channel_rank: int | None,
        domain: str,
        action: str,
        main_risk: str,
        selected_medium: str,
        decision_mode: str,
        capabilities: frozenset[str],
        challenge_mode: str,
    ) -> None:
        if _token is not _AUTH_TOKEN:
            raise PermissionError("ExecutionAuthorization must be minted by authorize_execution")
        object.__setattr__(self, "channel_rank", channel_rank)
        object.__setattr__(self, "domain", domain)
        object.__setattr__(self, "action", action)
        object.__setattr__(self, "main_risk", main_risk)
        object.__setattr__(self, "selected_medium", selected_medium)
        object.__setattr__(self, "decision_mode", decision_mode)
        object.__setattr__(self, "capabilities", capabilities)
        object.__setattr__(self, "challenge_mode", challenge_mode)

    @property
    def permits_browser_input(self) -> bool:
        # Biometric mouse her zaman — per-action Low/Moderate/High, site riskine bakılmaksızın
        return (
            self.selected_medium in BROWSER_MEDIA
            and self.main_risk in RISK_ORDER
            and RISK_ORDER[self.main_risk] <= RISK_ORDER["High"]
        )

    @property
    def permits_platform_challenge(self) -> bool:
        # auto_ensemble: 2captcha → ai-captcha-bypass → buster for Low/Moderate/High per-action (High riskli grupta olsa bile, Very High değilse)
        if self.challenge_mode == "auto_ensemble":
            return (
                self.main_risk in RISK_ORDER
                and RISK_ORDER[self.main_risk] <= RISK_ORDER["High"]
            )
        return self.challenge_mode in {"first_party", "sandbox"} and "platform_challenge" in self.capabilities

    def require_browser_input(self) -> None:
        if not self.permits_browser_input:
            raise PermissionError("action-scoped authorization does not permit browser input")

    def require_platform_challenge(self) -> None:
        if not self.permits_platform_challenge:
            raise PermissionError("action-scoped authorization does not permit a platform challenge mechanism")


def authorize_execution(
    decision: RouteDecision,
    *,
    policy_capabilities: Iterable[str] = (),
    challenge_mode: str = "none",
) -> ExecutionAuthorization:
    """Mint an authorization from a canonical action decision plus Policy Registry capabilities.

    - `challenge_mode=auto_ensemble` uses vault-backed libraries 2captcha/2captcha-python (primary),
      aydinnyunus/ai-captcha-bypass (LMM fallback, GPT-4o/Gemini), teal33t/captcha_bypass (buster + B-spline)
      for Low/Moderate/High per-action (High riskli grupta olsa bile, Very High/Critical değilse). Site geneli risk değil, eylem riski belirler.
    - `biometric` (wassim-sayah/biometric-mouse) her zaman Low/Moderate/High için kullanılır, Very High/Critical hariç.
    - `first_party`/`sandbox` still require `platform_challenge` capability and documented first-party mechanism.
    """
    if not decision.should_execute or decision.decision_mode == "auto_quarantine":
        raise PermissionError("quarantined action cannot receive execution authorization")
    if decision.main_risk not in RISK_ORDER or RISK_ORDER[decision.main_risk] > RISK_ORDER["High"]:
        raise PermissionError("Very High/Critical actions cannot receive autonomous authorization")
    if challenge_mode not in _CHALLENGE_MODES:
        raise ValueError(f"unsupported challenge mode: {challenge_mode!r}")

    caps = frozenset(policy_capabilities)
    if challenge_mode != "none" and challenge_mode != "auto_ensemble" and "platform_challenge" not in caps:
        raise PermissionError("challenge mode requires Policy Registry capability 'platform_challenge'")
    # auto_ensemble for Low/Moderate/High does not require site-wide platform_challenge; per-action High dahil

    return ExecutionAuthorization(
        _token=_AUTH_TOKEN,
        channel_rank=decision.channel_rank,
        domain=decision.domain,
        action=decision.action,
        main_risk=decision.main_risk,
        selected_medium=decision.selected_medium,
        decision_mode=decision.decision_mode,
        capabilities=caps,
        challenge_mode=challenge_mode,
    )
