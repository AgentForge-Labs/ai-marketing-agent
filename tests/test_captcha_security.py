"""#23 P1: captcha token/DNS/vault security (feat-scoped only, no live calls)."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_marketing_agent.captcha_ensemble import inject_token  # noqa: E402
from ai_marketing_agent.runner import RunnerConfig  # noqa: E402
from ai_marketing_agent.semantic_browser import _resolve_service_url  # noqa: E402
from ai_marketing_agent.vault import require_vault_ref  # noqa: E402


class InjectTokenTests(unittest.TestCase):
    def test_token_passed_as_arg_not_interpolated(self):
        import asyncio

        page = AsyncMock()
        evil = "x'); alert(1);//"
        asyncio.run(inject_token(page, "g-recaptcha-response", evil))
        page.evaluate.assert_awaited_once()
        args, _ = page.evaluate.call_args
        self.assertNotIn(evil, args[0])
        self.assertEqual(args[1], {"id": "g-recaptcha-response", "token": evil})

    def test_empty_token_rejected(self):
        import asyncio

        with self.assertRaises(ValueError):
            asyncio.run(inject_token(AsyncMock(), "g-recaptcha-response", ""))


class DnsRebindingTests(unittest.TestCase):
    def test_loopback_allowed(self):
        for url in ["http://127.0.0.1:8765", "http://localhost:8765", "http://[::1]:8765"]:
            self.assertEqual(_resolve_service_url(url), url)

    def test_remote_rejected_by_default(self):
        with self.assertRaises(ValueError):
            _resolve_service_url("http://attacker.test:8765")
        with self.assertRaises(ValueError):
            _resolve_service_url("http://127.0.0.1.evil.com:8765")

    def test_remote_allowed_with_explicit_override(self):
        os.environ["SEMANTIC_BROWSER_ALLOW_REMOTE"] = "1"
        try:
            self.assertEqual(
                _resolve_service_url("http://10.0.0.5:8765"), "http://10.0.0.5:8765"
            )
        finally:
            del os.environ["SEMANTIC_BROWSER_ALLOW_REMOTE"]


class VaultRefTests(unittest.TestCase):
    def test_plaintext_rejected(self):
        with self.assertRaises(ValueError):
            require_vault_ref("sk-live-123", field="captcha.capSolver.apiKeyRef")
        self.assertEqual(require_vault_ref("vault://captcha/capsolver/apiKey"), "vault://captcha/capsolver/apiKey")

    def test_adapter_plaintext_ref_rejected(self):
        adapter = {"captcha": {"policy": "auto_ensemble",
                               "capSolver": {"apiKeyRef": "PLAINTEXT"}},
                   "biometricMouse": {"profileRef": "vault://mouse/profile/mouse_profile.json"}}
        with self.assertRaises(ValueError):
            RunnerConfig.from_adapter(adapter)

    def test_adapter_vault_refs_accepted(self):
        adapter = {"captcha": {"policy": "auto_ensemble",
                               "capSolver": {"apiKeyRef": "vault://captcha/capsolver/apiKey"},
                               "twoCaptcha": {"apiKeyRef": "vault://captcha/2captcha/apiKey"}},
                   "biometricMouse": {"profileRef": "vault://mouse/profile/mouse_profile.json"}}
        cfg = RunnerConfig.from_adapter(adapter)
        self.assertEqual(cfg.captcha_policy, "auto_ensemble")


if __name__ == "__main__":
    unittest.main()
