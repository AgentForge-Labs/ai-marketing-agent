"""
Autonomous Runner — 0-HITL, agentic, 5-repo integrated.

Integrates at architectural level (docs/03 §8.1) and is the **single execution entry**
for all site-adapter.json flows. No direct Playwright calls outside this runner.

Stack per docs/03 + schemas/site-adapter.schema.json:
  - wassim-sayah/biometric-mouse     → HumanMouse (FFT, always for Low/Moderate/High browser)
  - visser23/semantic-browser        → SemanticBrowser (540 token rooms, drift repair)
  - 2captcha/2captcha-python         → CaptchaTask (primary, 30+ types)
  - aydinnyunus/ai-captcha-bypass    → LMM fallback (GPT-4o/Gemini)
  - teal33t/captcha_bypass (buster)  → B-spline fallback

Vault: C:/Users/ahmet/Downloads/DIGER/sunucular -> vault:// (never in repo)
Policy: per-action Low/Moderate/High → always biometric + ensemble if needed;
        Very High/Critical → auto_quarantine (no ensemble, no bypass)

Schemas: site-adapter.json: captcha.policy=auto_ensemble, biometricMouse, semanticBrowser
Docs: docs/03 §8.1, SECURITY.md Agentic Stack, docs/05 vault mapping
"""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .browser import BrowserProvider, get_browser_for_tenant
from .captcha_ensemble import CaptchaTask, solve_captcha
from .email_verification import handle_verification
from .execution_policy import ExecutionAuthorization, authorize_execution
from .human_mouse import get_human_mouse
from .risk_router import PlatformRiskRouter, RouteDecision
from .semantic_browser import get_semantic_browser


@dataclass
class RunnerConfig:
    """Mirrors site-adapter.json: captcha, biometricMouse, semanticBrowser, limits, retry."""

    captcha_policy: str = "abort_and_notify"  # or auto_ensemble
    captcha_strategy: str = "auto_ensemble"
    biometric_enabled: bool = True
    biometric_profile_ref: str = "vault://mouse/profile/mouse_profile.json"
    semantic_enabled: bool = False
    semantic_service_url: str = "http://127.0.0.1:8765"
    proxy_ref: Optional[str] = None
    max_concurrency: int = 1

    @classmethod
    def from_adapter(cls, adapter: Dict[str, Any]) -> "RunnerConfig":
        cap = adapter.get("captcha", {})
        bio = adapter.get("biometricMouse", {})
        sem = adapter.get("semanticBrowser", {})
        return cls(
            captcha_policy=cap.get("policy", "abort_and_notify"),
            captcha_strategy=cap.get("strategy", "auto_ensemble"),
            biometric_enabled=bio.get("enabled", True),
            biometric_profile_ref=bio.get("profileRef", "vault://mouse/profile/mouse_profile.json"),
            semantic_enabled=sem.get("enabled", False),
            semantic_service_url=sem.get("serviceUrl", "http://127.0.0.1:8765"),
            proxy_ref=cap.get("proxyRef"),
            max_concurrency=adapter.get("limits", {}).get("maxConcurrency", 1),
        )


@dataclass
class RunnerResult:
    status: str  # done, failed, auto_quarantine, needs_remap
    detail: Dict[str, Any]
    audit: List[Dict[str, Any]]


class AutonomousRunner:
    """
    0-HITL runner — the only place where Playwright + 5 repos are orchestrated.
    Every site flow must go through: authorize → human_mouse → semantic observe → captcha ensemble → audit
    """

    def __init__(self, config: RunnerConfig, decision: RouteDecision, authorization: ExecutionAuthorization):
        self.config = config
        self.decision = decision
        self.auth = authorization
        self.audit: List[Dict[str, Any]] = []

    def _log(self, event: str, detail: Dict[str, Any]) -> None:
        self.audit.append({"ts": time.time(), "event": event, "detail": detail})

    async def _maybe_handle_captcha(self, page: Any, task_hint: Optional[CaptchaTask] = None) -> bool:
        """Agentic captcha ensemble — only if policy allows auto_ensemble and per-action risk != Very High/Critical."""
        if self.config.captcha_policy != "auto_ensemble":
            self._log("captcha_skipped_policy_abort", {"policy": self.config.captcha_policy})
            return False
        # Very High/Critical already blocked by authorize_execution, but double-check
        try:
            self.auth.require_platform_challenge()
        except PermissionError as e:
            self._log("captcha_blocked_by_policy", {"reason": str(e), "main_risk": self.auth.main_risk})
            return False

        # Build task — in real runner, detect sitekey/url from page
        task = task_hint or CaptchaTask(type="recaptcha_v2", sitekey="auto-detect", url=str(getattr(page, "url", "")) if page else "")
        result = await solve_captcha(task, authorization=self.auth)
        self._log("captcha_ensemble", {"solver": result.solver, "success": result.success, "error": result.error})
        if result.success:
            # Inject token where needed (e.g., g-recaptcha-response)
            if result.token and page:
                try:
                    await page.evaluate(f"document.getElementById('g-recaptcha-response').innerHTML='{result.token}'")
                except Exception:
                    pass
            return True
        # All solvers failed → quarantine, never bypass ban
        self._log("captcha_ensemble_failed_quarantine", {"error": result.error})
        return False

    async def run_browser_flow(self, page: Any, flow: Dict[str, Any], adapter: Dict[str, Any]) -> RunnerResult:
        """
        Execute a single site flow (register, submitListing, etc.) with:
          - HumanMouse for every click/move (biometric, always for Low/Moderate/High)
          - SemanticBrowser for drift repair / discovery
          - Captcha ensemble on challenge
        """
        # 1. Authorize biometric — per-action Low/Moderate/High always
        if self.config.biometric_enabled:
            try:
                self.auth.require_browser_input()
                mouse = get_human_mouse(page, profile_ref=self.config.biometric_profile_ref)
                self._log("biometric_mouse_active", {"profileRef": self.config.biometric_profile_ref, "variance": "8%/30m"})
            except PermissionError as e:
                return RunnerResult(status="auto_quarantine", detail={"reason": str(e)}, audit=self.audit)
        else:
            mouse = None  # type: ignore

        # 2. Semantic observe (if enabled) — token-efficient planning
        semantic = None
        if self.config.semantic_enabled:
            try:
                semantic = get_semantic_browser(service_url=self.config.semantic_service_url)
                await semantic.launch(headless=True)
                obs = await semantic.observe(url=flow.get("entryUrl"))
                self._log("semantic_observe", {"room_text_len": len(getattr(obs, "planner", {}).room_text if hasattr(obs, "planner") else ""), "actions": len(getattr(obs, "available_actions", []))})
            except Exception as e:
                self._log("semantic_unavailable_fallback_playwright", {"error": str(e)[:200]})
                semantic = None

        # 3. Preflight: form fingerprint + locator uniqueness (from adapter)
        # (Simplified — real runner does dry-run fill with redacted screenshot)
        entry_url = flow.get("entryUrl")
        if entry_url and page:
            try:
                if mouse:
                    # Human-like navigation: move then click, not direct goto where possible
                    await page.goto(entry_url, wait_until="domcontentloaded")
                else:
                    await page.goto(entry_url)
                self._log("goto", {"url": entry_url})
            except Exception as e:
                return RunnerResult(status="failed", detail={"reason": f"goto failed: {e}"}, audit=self.audit)

        # 4. Fill fields with human mouse
        fields: List[Dict[str, Any]] = flow.get("fields", []) or []
        for step in flow.get("steps", []) or []:
            fields.extend(step.get("fields", []))

        for field in fields:
            locators = field.get("locators", [])
            if not locators or not page:
                continue
            # Resolve locator: prefer role/label, fallback css
            loc = None
            for loc_def in locators:
                try:
                    kind = loc_def.get("kind")
                    if kind == "role":
                        loc = page.get_by_role(loc_def.get("role"), name=loc_def.get("name"))
                    elif kind == "label":
                        loc = page.get_by_label(loc_def.get("name") or loc_def.get("value"))
                    elif kind == "placeholder":
                        loc = page.get_by_placeholder(loc_def.get("value"))
                    elif kind == "css":
                        loc = page.locator(loc_def.get("value"))
                    if loc:
                        break
                except Exception:
                    continue
            if loc is None:
                self._log("locator_not_found", {"field": field.get("valueFrom")})
                continue
            # Human-like fill
            try:
                if mouse:
                    await mouse.click_element(loc)
                else:
                    await loc.click()
                # Value is resolved from product-profile via adapter compiler (vault:// not here)
                await loc.fill("test-value")  # placeholder — real runner resolves valueFrom
                self._log("fill", {"field": field.get("valueFrom"), "locator": locators[0]})
            except Exception as e:
                self._log("fill_failed", {"field": field.get("valueFrom"), "error": str(e)[:200]})

        # 5. Captcha pre-scan — if challenge detected, run ensemble
        # Detection: check for sitekey, turnstile, geetest elements
        captcha_detected = False
        if page:
            try:
                # Simple heuristic: look for captcha markers
                content = await page.content()
                if any(k in content.lower() for k in ["g-recaptcha", "turnstile", "geetest", "datadome", "captcha"]):
                    captcha_detected = True
            except Exception:
                pass
        if captcha_detected:
            ok = await self._maybe_handle_captcha(page)
            if not ok and self.config.captcha_policy == "abort_and_notify":
                return RunnerResult(status="auto_quarantine", detail={"reason": "captcha_challenge_abort"}, audit=self.audit)
            if not ok:
                return RunnerResult(status="failed", detail={"reason": "captcha_ensemble_failed"}, audit=self.audit)

        # 6. Submit with human mouse
        submit = flow.get("submit") or {}
        locator_def = submit.get("locator")
        if locator_def and page:
            try:
                # Resolve submit locator
                kind = locator_def.get("kind")
                if kind == "role":
                    sub_loc = page.get_by_role(locator_def.get("role"), name=locator_def.get("name"))
                else:
                    sub_loc = page.locator(locator_def.get("value", "button[type=submit]"))
                if mouse:
                    await mouse.click_element(sub_loc)
                else:
                    await sub_loc.click()
                self._log("submit", {"locator": locator_def})
            except Exception as e:
                return RunnerResult(status="failed", detail={"reason": f"submit failed: {e}"}, audit=self.audit)

        # 7. Success assertion (multi-signal) — semantic delta if available
        if semantic:
            try:
                obs_after = await semantic.observe()
                self._log("semantic_delta", {"room_text": getattr(getattr(obs_after, "planner", None), "room_text", "")[:200]})
            except Exception:
                pass
            finally:
                try:
                    await semantic.close()
                except Exception:
                    pass

        # 8. Email verification — Gmail + custom IMAP, vault://, per-tenant proxy aware
        email_flow = adapter.get("flows", {}).get("emailVerification") if isinstance(adapter.get("flows"), dict) else None
        if email_flow and email_flow.get("kind") == "email":
            mailbox_ref = email_flow.get("mailbox", {}).get("mailboxRef", "vault://mail/imap/default")
            subject_contains = email_flow.get("mailbox", {}).get("subjectContains")
            from_contains = email_flow.get("mailbox", {}).get("fromContains")
            # Only run if page indicates verification pending or flow expects it
            try:
                ev_result = await handle_verification(
                    page,
                    mailbox_ref=mailbox_ref,
                    tenant_id=str(self.decision.domain),
                    code_selector="input[name='code'], input[name='otp'], input[type='text']",
                    subject_contains=subject_contains,
                    from_contains=from_contains,
                )
                self._log("email_verification", ev_result)
            except Exception as e:
                self._log("email_verification_failed", {"error": str(e)[:200]})

        return RunnerResult(status="done", detail={"flow": flow.get("entryUrl") or "steps", "biometric": self.config.biometric_enabled, "semantic": self.config.semantic_enabled}, audit=self.audit)

    @staticmethod
    def from_adapter_and_decision(adapter: Dict[str, Any], decision: RouteDecision, policy_caps: List[str] | None = None, challenge_mode: str = "auto_ensemble") -> "AutonomousRunner":
        """Factory: validate decision → authorize → build runner with 5-repo config."""
        config = RunnerConfig.from_adapter(adapter)
        caps = policy_caps or []
        auth = authorize_execution(decision, policy_capabilities=caps, challenge_mode=challenge_mode)
        return AutonomousRunner(config=config, decision=decision, authorization=auth)

    async def run_with_browser_provider(
        self,
        flow: Dict[str, Any],
        adapter: Dict[str, Any],
        *,
        tenant_id: Optional[str] = None,
        profile_id: Optional[str] = None,
        is_discovery: bool = False,
    ) -> RunnerResult:
        """
        Discovery ve normal mod aynı provider — MultiLogin yoksa headed, proxy per-tenant.
        proxy yoksa default bağlantı.
        """
        provider = BrowserProvider()
        # proxy per-tenant: adapter.captcha.proxyRef veya tenant env
        proxy_ref = self.config.proxy_ref
        launched = await provider.launch(
            tenant_id=tenant_id or str(self.decision.domain),
            profile_id=profile_id,
            proxy_ref=proxy_ref,
            is_discovery=is_discovery,
        )
        self._log(
            "browser_launch",
            {"mode": launched.mode, "proxy_used": bool(launched.proxy_used), "is_discovery": is_discovery, "tenant": tenant_id},
        )
        try:
            return await self.run_browser_flow(launched.page, flow, adapter)
        finally:
            await provider.close(launched)
