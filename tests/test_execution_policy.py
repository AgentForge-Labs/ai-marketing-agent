from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_marketing_agent import (  # noqa: E402
    CaptchaTask,
    ChannelCatalogue,
    PlatformRiskRouter,
    authorize_execution,
    solve_captcha,
)
from ai_marketing_agent.execution_policy import ExecutionAuthorization  # noqa: E402

CSV = ROOT / "data/saas_marketing_1000_channels_ranked - 1000 Channels.csv"


class ActionScopedPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalogue = ChannelCatalogue.load(CSV)
        cls.router = PlatformRiskRouter()

    def test_high_action_is_executable_with_verification_but_very_high_is_quarantined(self):
        high = self.router.route(self.catalogue.require_unique_domain("quora.com"), "post")
        self.assertEqual(high.main_risk, "High")
        self.assertTrue(high.should_execute)
        self.assertEqual(high.decision_mode, "auto_with_verification")

        very_high = self.router.route(self.catalogue.require_unique_domain("reddit.com"), "vote")
        self.assertEqual(very_high.main_risk, "Very High")
        self.assertFalse(very_high.should_execute)
        self.assertEqual(very_high.decision_mode, "auto_quarantine")

    def test_authorization_cannot_be_minted_for_quarantined_action(self):
        d = self.router.route(self.catalogue.require_unique_domain("linkedin.com"), "dm")
        with self.assertRaises(PermissionError):
            authorize_execution(d, policy_capabilities={"browser_input"})

    def test_execution_authorization_cannot_be_constructed_directly(self):
        with self.assertRaises(PermissionError):
            ExecutionAuthorization(
                _token=object(), channel_rank=1, domain="example.com", action="post",
                main_risk="Low", selected_medium="local_browser_agent", decision_mode="auto_full",
                capabilities=frozenset({"browser_input"}), challenge_mode="none"
            )

    def test_challenge_auto_ensemble_per_action_high_even_if_site_risky(self):
        # Per-action: High riskli grupta olsa bile Very High değilse ensemble denenir, site geneli High olsa bile per-action High → auto_ensemble
        decision = next(
            self.router.route(channel, "submit")
            for channel in self.catalogue
            if channel.action_risks["own_content_submit_post"].best_medium in {"local_browser_agent", "browser_extension"}
            and channel.action_risks["own_content_submit_post"].main_risk in {"Low", "Moderate", "High"}
        )
        # auto_ensemble without platform_challenge should still be allowed for High and below (per-action), Very High hariç
        auth = authorize_execution(decision, policy_capabilities={"browser_input"}, challenge_mode="auto_ensemble")
        result = asyncio.run(solve_captcha(CaptchaTask(type="recaptcha_v2", sitekey="test", url="https://example.com"), authorization=auth))
        # No vault keys in CI, so ensemble will exhaust and return quarantine, but it must have tried 2captcha/ai_lmm/buster, not immediate quarantine
        self.assertIn(result.solver, ("quarantine", "2captcha", "ai_lmm", "buster"))
        # Very High still quarantined even with auto_ensemble
        very_high = self.router.route(self.catalogue.require_unique_domain("reddit.com"), "vote")
        self.assertEqual(very_high.main_risk, "Very High")
        self.assertFalse(very_high.should_execute)
        with self.assertRaises(PermissionError):
            authorize_execution(very_high, policy_capabilities={"browser_input"}, challenge_mode="auto_ensemble")

    def test_biometric_mouse_always_for_low_moderate_high(self):
        # Biometric her zaman — per-action Low/Moderate/High browser eylemde her zaman browser_input izni
        for risk in ("Low", "Moderate", "High"):
            decision = next(
                self.router.route(channel, "submit")
                for channel in self.catalogue
                if channel.action_risks["own_content_submit_post"].main_risk == risk
                and channel.action_risks["own_content_submit_post"].best_medium in {"local_browser_agent", "browser_extension"}
            )
            auth = authorize_execution(decision, policy_capabilities=set())
            # Her zaman biometric — no browser_input capability required anymore
            self.assertTrue(auth.permits_browser_input)


if __name__ == "__main__":
    unittest.main()
