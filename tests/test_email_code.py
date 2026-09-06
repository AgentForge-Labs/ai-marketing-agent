"""#35 emailCode step: compiler bounds + pre-success fail-closed execution."""
import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from ai_marketing_agent.adapter_compiler import CompileError, compile_flow  # noqa: E402
from test_runner_completion import FakePage, make_runner  # noqa: E402

EC = {"codeSelector": "input[name=code]", "timeoutS": 120}
FLOW = {"entryUrl": "https://x.test/register",
        "fields": [],
        "success": [{"kind": "text", "matches": "welcome"}]}


class EmailCodeCompilerTests(unittest.TestCase):
    def test_accepts_code_and_link(self):
        compile_flow({**FLOW, "emailCode": dict(EC)})
        compile_flow({**FLOW, "emailCode": {"linkPattern": "verify", "allowedDomains": ["x.test"]}})

    def test_rejects_empty(self):
        with self.assertRaises(CompileError):
            compile_flow({**FLOW, "emailCode": {}})

    def test_rejects_bad_timeout(self):
        for bad in [0, 601, "soon"]:
            with self.assertRaises(CompileError):
                compile_flow({**FLOW, "emailCode": {**EC, "timeoutS": bad}})

    def test_rejects_plaintext_mailbox(self):
        with self.assertRaises(CompileError):
            compile_flow({**FLOW, "emailCode": {**EC, "mailboxRef": "user:pass@imap"}})


class EmailCodeRunnerTests(unittest.TestCase):
    def run_flow(self, flow, page, stub):
        with patch("ai_marketing_agent.runner.handle_verification", stub):
            return asyncio.run(make_runner().run_browser_flow(page, flow, {}, values={}))

    def test_found_proceeds_to_success(self):
        stub = AsyncMock(return_value={"found": True, "type": "code"})
        page = FakePage(url="https://x.test/register", content="<html>welcome</html>",
                        present_selectors=set())
        res = self.run_flow({**FLOW, "emailCode": dict(EC)}, page, stub)
        self.assertEqual(res.status, "done")
        stub.assert_awaited_once()
        _, kw = stub.call_args
        self.assertEqual(kw["code_selector"], "input[name=code]")

    def test_not_found_fails_before_success(self):
        stub = AsyncMock(return_value={"found": False, "type": "none"})
        page = FakePage(url="https://x.test/register", content="<html>welcome</html>",
                        present_selectors=set())
        res = self.run_flow({**FLOW, "emailCode": dict(EC)}, page, stub)
        self.assertEqual(res.status, "failed")
        self.assertEqual(res.detail["reason"], "email_code_not_found")

    def test_exception_fails(self):
        async def boom(*a, **k):
            raise RuntimeError("imap down")
        page = FakePage(url="https://x.test/register", content="<html>welcome</html>",
                        present_selectors=set())
        res = self.run_flow({**FLOW, "emailCode": dict(EC)}, page, boom)
        self.assertEqual(res.status, "failed")
        self.assertEqual(res.detail["reason"], "email_code_failed")

    def test_absent_block_not_called(self):
        stub = AsyncMock(return_value={"found": True, "type": "code"})
        page = FakePage(url="https://x.test/register", content="<html>welcome</html>",
                        present_selectors=set())
        res = self.run_flow(dict(FLOW), page, stub)
        self.assertEqual(res.status, "done")
        stub.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
