from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_marketing_agent.captcha_ensemble import (  # noqa: E402
    CaptchaResult,
    CaptchaTask,
    _capsolver_task_payload,
    _get_vault_secret,
    solve_captcha,
)


class CapsolverPayloadTests(unittest.TestCase):
    def test_recaptcha_v2_proxyless(self):
        p = _capsolver_task_payload(CaptchaTask(type="recaptcha_v2", sitekey="k", url="https://x.test/"), None)
        self.assertEqual(p, {"type": "ReCaptchaV2TaskProxyless", "websiteURL": "https://x.test/", "websiteKey": "k"})

    def test_recaptcha_v2_with_proxy(self):
        p = _capsolver_task_payload(CaptchaTask(type="recaptcha_v2", sitekey="k", url="https://x.test/"), "http://u:p@1.2.3.4:8080")
        self.assertEqual(p["type"], "ReCaptchaV2Task")
        self.assertEqual(p["proxy"], "http://u:p@1.2.3.4:8080")

    def test_turnstile_proxyless(self):
        p = _capsolver_task_payload(CaptchaTask(type="turnstile", sitekey="k", url="https://x.test/"), None)
        self.assertEqual(p["type"], "AntiTurnstileTaskProxyLess")

    def test_geetest_needs_gt_challenge(self):
        self.assertIsNone(_capsolver_task_payload(CaptchaTask(type="geetest", url="https://x.test/"), None))
        p = _capsolver_task_payload(CaptchaTask(type="geetest", url="https://x.test/", gt="g", challenge="c"), None)
        self.assertEqual(p["type"], "GeeTestTaskProxyless")

    def test_datadome_needs_proxy(self):
        self.assertIsNone(
            _capsolver_task_payload(CaptchaTask(type="datadome", url="https://x.test/", captcha_url="https://c.test/"), None)
        )
        p = _capsolver_task_payload(
            CaptchaTask(type="datadome", url="https://x.test/", captcha_url="https://c.test/"), "http://u:p@1.2.3.4:8080"
        )
        self.assertEqual(p["type"], "DatadomeSliderTask")

    def test_unsupported_type(self):
        self.assertIsNone(_capsolver_task_payload(CaptchaTask(type="puzzle"), None))
        self.assertIsNone(_capsolver_task_payload(CaptchaTask(type="audio"), None))

    def test_vault_mapping_capsolver(self):
        import os

        os.environ["CAPSOLVER_API_KEY"] = "test-key"
        try:
            self.assertEqual(_get_vault_secret("vault://captcha/capsolver/apiKey"), "test-key")
        finally:
            del os.environ["CAPSOLVER_API_KEY"]


class EnsembleOrderTests(unittest.TestCase):
    def test_capsolver_first_then_2captcha(self):
        calls: list[str] = []

        async def fake_capsolver(task, api_key, timeout_s=120):
            calls.append("capsolver")
            return CaptchaResult(solver="capsolver", success=False, error="nope")

        async def fake_2captcha(task, api_key):
            calls.append("2captcha")
            return CaptchaResult(solver="2captcha", success=True, token="tok123")

        with (
            patch.dict("os.environ", {"CAPSOLVER_API_KEY": "k", "CAPTCHA_2CAPTCHA_KEY": "k2"}),
            patch("ai_marketing_agent.captcha_ensemble._solve_with_capsolver", new=fake_capsolver),
            patch("ai_marketing_agent.captcha_ensemble._solve_with_2captcha", new=fake_2captcha),
        ):
            result = asyncio.run(solve_captcha(CaptchaTask(type="recaptcha_v2", sitekey="k", url="https://x.test/")))
        self.assertEqual(calls, ["capsolver", "2captcha"])
        self.assertTrue(result.success)
        self.assertEqual(result.solver, "2captcha")
        self.assertEqual(result.token, "tok123")

    def test_capsolver_success_short_circuits(self):
        async def fake_capsolver(task, api_key, timeout_s=120):
            return CaptchaResult(solver="capsolver", success=True, token="cap-tok")

        with (
            patch.dict("os.environ", {"CAPSOLVER_API_KEY": "k"}),
            patch("ai_marketing_agent.captcha_ensemble._solve_with_capsolver", new=fake_capsolver),
            patch(
                "ai_marketing_agent.captcha_ensemble._solve_with_2captcha",
                new=AsyncMock(side_effect=AssertionError("must not be called")),
            ),
        ):
            result = asyncio.run(solve_captcha(CaptchaTask(type="turnstile", sitekey="k", url="https://x.test/")))
        self.assertTrue(result.success)
        self.assertEqual(result.solver, "capsolver")

    def test_non_ensemble_mode_quarantines_without_solving(self):
        import types

        auth = types.SimpleNamespace(challenge_mode="none", permits_platform_challenge=False, main_risk="Low")
        with patch(
            "ai_marketing_agent.captcha_ensemble._solve_with_capsolver",
            new=AsyncMock(side_effect=AssertionError("must not be called")),
        ):
            result = asyncio.run(
                solve_captcha(CaptchaTask(type="recaptcha_v2", sitekey="k", url="https://x.test/"), authorization=auth)
            )
        self.assertFalse(result.success)
        self.assertEqual(result.solver, "quarantine")

    def test_missing_keys_falls_through_to_quarantine(self):
        with patch.dict("os.environ", {}, clear=False):
            import os

            os.environ.pop("CAPSOLVER_API_KEY", None)
            os.environ.pop("CAPTCHA_CAPSOLVER_KEY", None)
            os.environ.pop("CAPTCHA_2CAPTCHA_KEY", None)
            os.environ.pop("TWOCAPTCHA_API_KEY", None)
            with (
                patch("ai_marketing_agent.captcha_ensemble._solve_with_lmm", new=AsyncMock(return_value=CaptchaResult(solver="ai_lmm", success=False, error="x"))),
                patch("ai_marketing_agent.captcha_ensemble._solve_with_buster", new=AsyncMock(return_value=CaptchaResult(solver="buster", success=False, error="y"))),
            ):
                result = asyncio.run(solve_captcha(CaptchaTask(type="recaptcha_v2", sitekey="k", url="https://x.test/")))
        self.assertFalse(result.success)
        self.assertEqual(result.solver, "quarantine")


class CapsolverBlockingTests(unittest.TestCase):
    def _fake_response(self, payload):
        class R:
            def json(self):
                return payload

        return R()

    def test_ready_token_extraction(self):
        from ai_marketing_agent import captcha_ensemble as ce

        calls = {"n": 0}

        def fake_post(url, json=None, timeout=None):
            calls["n"] += 1
            if url.endswith("/createTask"):
                self.assertEqual(json["task"]["type"], "ReCaptchaV2TaskProxyless")
                return self._fake_response({"errorId": 0, "taskId": "t1"})
            return self._fake_response({"errorId": 0, "status": "ready", "solution": {"gRecaptchaResponse": "tok"}})

        import sys as _sys
        import types

        fake_requests = types.ModuleType("requests")
        fake_requests.post = fake_post  # type: ignore
        with patch.dict(_sys.modules, {"requests": fake_requests}):
            with patch("time.sleep", return_value=None):
                res = ce._capsolver_solve_blocking({"type": "ReCaptchaV2TaskProxyless"}, "key", timeout_s=30, poll_interval_s=1)
        self.assertTrue(res.success)
        self.assertEqual(res.token, "tok")

    def test_create_rejected_falls_through(self):
        from ai_marketing_agent import captcha_ensemble as ce

        def fake_post(url, json=None, timeout=None):
            return self._fake_response({"errorId": 1, "errorCode": "ERROR_KEY_DOES_NOT_EXIST", "errorDescription": "bad key"})

        import sys as _sys
        import types

        fake_requests = types.ModuleType("requests")
        fake_requests.post = fake_post  # type: ignore
        with patch.dict(_sys.modules, {"requests": fake_requests}):
            res = ce._capsolver_solve_blocking({"type": "ReCaptchaV2TaskProxyless"}, "bad", timeout_s=30)
        self.assertFalse(res.success)
        self.assertIn("ERROR_KEY_DOES_NOT_EXIST", res.error or "")


if __name__ == "__main__":
    unittest.main()
