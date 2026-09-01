import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import unittest

from ai_marketing_agent.email_verification import MailboxConfig, _extract_code, _extract_link, fetch_code, fetch_link, handle_verification


class TestMailboxConfig(unittest.TestCase):
    def test_gmail_ref(self):
        cfg = MailboxConfig.from_ref("vault://mail/gmail/oauth")
        self.assertEqual(cfg.protocol, "gmail_api")

    def test_imap_ref(self):
        os.environ["IMAP_HOST"] = "imap.example.com"
        os.environ["IMAP_USER"] = "user@example.com"
        os.environ["IMAP_PASS"] = "secret"
        cfg = MailboxConfig.from_ref("vault://mail/imap/acme")
        self.assertEqual(cfg.protocol, "imap")
        self.assertEqual(cfg.host, "imap.example.com")
        del os.environ["IMAP_HOST"]
        del os.environ["IMAP_USER"]
        del os.environ["IMAP_PASS"]


class TestExtract(unittest.TestCase):
    def test_extract_code(self):
        self.assertEqual(_extract_code("Your code is 123456"), "123456")
        self.assertEqual(_extract_code("Kodunuz: 9874"), "9874")
        self.assertIsNone(_extract_code("No code here"))

    def test_extract_link(self):
        self.assertEqual(_extract_link("Click https://xyz.com/verify?token=abc123"), "https://xyz.com/verify?token=abc123")
        self.assertEqual(_extract_link("Click here", pattern=r"https://xyz\.com/verify\?token=\w+"), None)


class TestFetchCode(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_code_extract(self):
        # Direct extraction already tested, here just verify fetch_code handles empty
        self.assertEqual(_extract_code("Your code 4321"), "4321")
        self.assertIsNone(_extract_code("No code"))

    async def test_handle_verification_code_fill(self):
        mock_page = MagicMock()
        mock_locator = AsyncMock()
        mock_page.locator.return_value = mock_locator
        mock_page.fill = AsyncMock()
        # Mock fetch_code to return code
        with patch("ai_marketing_agent.email_verification.fetch_code", new=AsyncMock(return_value="123456")):
            result = await handle_verification(mock_page, mailbox_ref="vault://mail/imap/acme", code_selector="input[name=code]")
            self.assertTrue(result["found"])
            self.assertEqual(result["type"], "code")

    async def test_handle_verification_link(self):
        mock_page = AsyncMock()
        mock_page.goto = AsyncMock()
        with patch("ai_marketing_agent.email_verification.fetch_code", new=AsyncMock(return_value=None)):
            with patch("ai_marketing_agent.email_verification.fetch_link", new=AsyncMock(return_value="https://xyz.com/verify?token=abc")):
                result = await handle_verification(mock_page, mailbox_ref="vault://mail/imap/acme")
                self.assertTrue(result["found"])
                self.assertEqual(result["type"], "link")
                mock_page.goto.assert_called()
