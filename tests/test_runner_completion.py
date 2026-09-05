"""#18 P0: runner fail-closed completion + same-session assertions (feat-scoped only)."""
import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_marketing_agent.runner import AutonomousRunner, RunnerConfig  # noqa: E402


class FakeLocator:
    def __init__(self, page, selector, fail_fill=False):
        self.page = page
        self.selector = selector
        self.fail_fill = fail_fill

    async def click(self):
        return None

    async def fill(self, value):
        if self.fail_fill:
            raise RuntimeError("fill exploded")
        self.page.filled[self.selector] = value

    async def count(self):
        return 1 if self.selector in self.page.present_selectors else 0


class FakePage:
    def __init__(self, url="https://x.test/form", content="<html>is live</html>", present_selectors=None, fail_fields=()):
        self.url = url
        self._content = content
        self.present_selectors = set(present_selectors or [])
        self.fail_fields = set(fail_fields)
        self.filled = {}

    async def goto(self, url, wait_until=None):
        self.url = url

    async def content(self):
        return self._content

    def get_by_role(self, role, name=None):
        raise RuntimeError("no role locators in fake")

    def get_by_label(self, name):
        raise RuntimeError("no label locators in fake")

    def get_by_placeholder(self, value):
        raise RuntimeError("no placeholder locators in fake")

    def locator(self, selector):
        if selector not in self.present_selectors:
            raise RuntimeError(f"selector not present: {selector}")
        return FakeLocator(self, selector, fail_fill=selector in self.fail_fields)


def make_runner(**cfg_overrides):
    cfg = RunnerConfig(captcha_policy="abort_and_notify", biometric_enabled=False, **cfg_overrides)
    decision = MagicMock()
    auth = MagicMock()
    return AutonomousRunner(config=cfg, decision=decision, authorization=auth)


def flow_with(fields, success, entry_url="https://x.test/form", submit_selector="#submit"):
    return {
        "entryUrl": entry_url,
        "fields": fields,
        "submit": {"locator": {"kind": "css", "value": submit_selector}},
        "success": success,
    }


REQ_FIELD = {"valueFrom": "product.name", "required": True, "locators": [{"kind": "css", "value": "#name"}]}


class RunnerCompletionTests(unittest.TestCase):
    def run_flow(self, runner, page, flow, adapter=None, values=None):
        return asyncio.run(runner.run_browser_flow(page, flow, adapter or {}, values=values))

    def test_required_field_missing_value_fails(self):
        page = FakePage(present_selectors={"#name", "#submit"})
        r = self.run_flow(make_runner(), page, flow_with([REQ_FIELD], [{"kind": "text", "matches": "is live"}]), values={})
        self.assertEqual(r.status, "failed")
        self.assertIn("missing_value", r.detail["reason"])

    def test_required_locator_not_found_fails(self):
        page = FakePage(present_selectors={"#submit"})
        r = self.run_flow(
            make_runner(), page, flow_with([REQ_FIELD], [{"kind": "text", "matches": "is live"}]),
            values={"product.name": "Acme"},
        )
        self.assertEqual(r.status, "failed")
        self.assertIn("locator_not_found", r.detail["reason"])

    def test_required_fill_failure_fails(self):
        page = FakePage(present_selectors={"#name", "#submit"}, fail_fields={"#name"})
        r = self.run_flow(
            make_runner(), page, flow_with([REQ_FIELD], [{"kind": "text", "matches": "is live"}]),
            values={"product.name": "Acme"},
        )
        self.assertEqual(r.status, "failed")
        self.assertIn("fill_failed", r.detail["reason"])

    def test_optional_unresolved_field_skipped_still_done(self):
        opt = {"valueFrom": "product.tagline", "required": False, "locators": [{"kind": "css", "value": "#tag"}]}
        page = FakePage(present_selectors={"#name", "#submit"})
        r = self.run_flow(
            make_runner(), page, flow_with([REQ_FIELD, opt], [{"kind": "text", "matches": "is live"}]),
            values={"product.name": "Acme"},
        )
        self.assertEqual(r.status, "done")
        self.assertEqual(page.filled.get("#name"), "Acme")
        self.assertNotIn("#tag", page.filled)

    def test_no_success_signals_never_done(self):
        page = FakePage(present_selectors={"#name", "#submit"})
        r = self.run_flow(
            make_runner(), page, flow_with([REQ_FIELD], []),
            values={"product.name": "Acme"},
        )
        self.assertEqual(r.status, "failed")
        self.assertEqual(r.detail["reason"], "no_success_signals")

    def test_failed_signals_not_done(self):
        page = FakePage(url="https://x.test/form", content="<html>error</html>", present_selectors={"#name", "#submit"})
        r = self.run_flow(
            make_runner(), page,
            flow_with([REQ_FIELD], [{"kind": "url", "matches": "/listing/"}, {"kind": "text", "matches": "is live"}]),
            values={"product.name": "Acme"},
        )
        self.assertEqual(r.status, "failed")
        self.assertEqual(r.detail["reason"], "success_assertion_failed")

    def test_verdict_uses_same_page(self):
        seen = {}

        class SpyPage(FakePage):
            async def content(self):
                seen["content_called"] = True
                return await super().content()

        page = SpyPage(present_selectors={"#name", "#submit"})
        # semantic enabled but no semantic package assertion path: verdict must still come from page
        runner = make_runner(semantic_enabled=False)
        r = self.run_flow(
            runner, page, flow_with([REQ_FIELD], [{"kind": "text", "matches": "is live"}]),
            values={"product.name": "Acme"},
        )
        self.assertEqual(r.status, "done")
        self.assertTrue(seen.get("content_called"), "success text must be read from the submitting page")

    def test_no_placeholder_fill_in_prod_path(self):
        page = FakePage(present_selectors={"#name", "#submit"})
        self.run_flow(
            make_runner(), page, flow_with([REQ_FIELD], [{"kind": "text", "matches": "is live"}]),
            values={"product.name": "Acme"},
        )
        self.assertNotIn("test-value", list(page.filled.values()))


if __name__ == "__main__":
    unittest.main()
