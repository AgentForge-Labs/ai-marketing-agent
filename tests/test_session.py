"""#31 session persistence (feat-scoped: fake context, temp dirs, no secrets)."""
import asyncio
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_marketing_agent.session import SessionStore, extract_session  # noqa: E402

STATE = {"cookies": [{"name": "sid", "value": "abc", "domain": "x.test"}],
         "origins": [{"origin": "https://x.test", "localStorage": []}]}


class SessionStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.clock = [1000.0]
        self.store = SessionStore(Path(self.tmp.name), ttl_s=3600.0, now=lambda: self.clock[0])

    def tearDown(self):
        self.tmp.cleanup()

    def test_roundtrip(self):
        self.store.save("t1", "x.test", STATE)
        loaded = self.store.load("t1", "x.test")
        self.assertEqual(loaded, STATE)

    def test_missing_is_none(self):
        self.assertIsNone(self.store.load("t1", "nope.test"))

    def test_expiry(self):
        self.store.save("t1", "x.test", STATE)
        self.clock[0] += 3600.0 + 1
        self.assertIsNone(self.store.load("t1", "x.test"))

    def test_empty_state_refused(self):
        with self.assertRaises(ValueError):
            self.store.save("t1", "x.test", {"cookies": []})
        with self.assertRaises(ValueError):
            self.store.save("t1", "x.test", {})

    def test_corrupt_is_none(self):
        (Path(self.tmp.name) / "t1__x.test.json").write_text("not-json{", encoding="utf-8")
        self.assertIsNone(self.store.load("t1", "x.test"))

    def test_clear(self):
        self.store.save("t1", "x.test", STATE)
        self.assertTrue(self.store.clear("t1", "x.test"))
        self.assertIsNone(self.store.load("t1", "x.test"))
        self.assertFalse(self.store.clear("t1", "x.test"))

    def test_tenant_isolation(self):
        self.store.save("t1", "x.test", STATE)
        self.assertIsNone(self.store.load("t2", "x.test"))

    def test_extract_session(self):
        class FakeCtx:
            async def storage_state(self):
                return STATE
        self.assertEqual(asyncio.run(extract_session(FakeCtx())), STATE)


class RunnerSessionWiringTests(unittest.TestCase):
    def test_restore_and_save(self):
        import asyncio
        from unittest.mock import MagicMock, patch

        from ai_marketing_agent.runner import AutonomousRunner, RunnerConfig

        saved = {}

        class FakeCtx:
            async def storage_state(self):
                return STATE

            async def close(self):
                return None

        class FakeLoc:
            def __init__(self, page, sel):
                self.page = page
                self.sel = sel

            async def click(self):
                return None

            async def fill(self, v):
                self.page.filled[self.sel] = v

        class FakePage:
            def __init__(self):
                self.filled = {}

            async def goto(self, url, wait_until=None):
                return None

            async def content(self):
                return "<html>is live</html>"

            def get_by_role(self, r, name=None):
                raise RuntimeError("x")

            def get_by_label(self, n):
                raise RuntimeError("x")

            def get_by_placeholder(self, v):
                raise RuntimeError("x")

            def get_by_test_id(self, v):
                raise RuntimeError("x")

            def locator(self, sel):
                return FakeLoc(self, sel)

        seen = {}

        class FakeProvider:
            async def launch(self, **kw):
                seen.update(kw)
                ns = MagicMock()
                ns.page = FakePage()
                ns.context = FakeCtx()
                ns.mode = "headed"
                ns.proxy_used = None
                return ns

            async def close(self, launched):
                await launched.context.close()

        class FakeStore:
            def load(self, tenant, domain):
                seen["loaded"] = (tenant, domain)
                return STATE

            def save(self, tenant, domain, state):
                saved.update({"tenant": tenant, "domain": domain, "state": state})

        cfg = RunnerConfig(captcha_policy="abort_and_notify", biometric_enabled=False)
        decision = MagicMock()
        decision.domain = "x.test"
        runner = AutonomousRunner(config=cfg, decision=decision, authorization=MagicMock())
        flow = {"entryUrl": "https://x.test/form",
                "fields": [{"valueFrom": "product.name", "required": True,
                            "locators": [{"kind": "css", "value": "#n"}]}],
                "submit": {"locator": {"kind": "css", "value": "#s"}},
                "success": [{"kind": "text", "matches": "is live"}]}
        with patch("ai_marketing_agent.runner.BrowserProvider", FakeProvider):
            res = asyncio.run(runner.run_with_browser_provider(
                flow, {}, tenant_id="t1", values={"product.name": "Acme"},
                session_store=FakeStore()))
        self.assertEqual(res.status, "done")
        self.assertEqual(seen["loaded"], ("t1", "x.test"))
        self.assertEqual(seen["session_state"], STATE)
        self.assertEqual(saved["state"], STATE)
        self.assertTrue(any(e["event"] == "session_saved" for e in runner.audit))


if __name__ == "__main__":
    unittest.main()
