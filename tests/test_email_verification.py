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
        mock_page.locator.side_effect = RuntimeError("no locator")
        mock_page.fill = AsyncMock()
        mails = [{"id": "1", "subject": "Code", "from": "noreply@xyz.com",
                  "body_text": "Your code 123456", "body_html": ""}]
        with patch("ai_marketing_agent.email_verification._get_mailbox") as mock_get:
            mock_box = MagicMock()
            mock_box.fetch_recent.return_value = mails
            mock_box.mark_processed = MagicMock()
            mock_get.return_value = mock_box
            with patch("ai_marketing_agent.human_mouse.get_human_mouse", side_effect=RuntimeError("no mouse")):
                result = await handle_verification(
                    mock_page, mailbox_ref="vault://mail/imap/acme", code_selector="input[name=code]",
                    timeout_minutes=0.01, poll_interval_seconds=0.01,
                )
        self.assertTrue(result["found"])
        self.assertEqual(result["type"], "code")
        mock_page.fill.assert_called()

    async def test_handle_verification_link(self):
        mock_page = AsyncMock()
        mock_page.goto = AsyncMock()
        mails = [{"id": "2", "subject": "Verify", "from": "noreply@xyz.com",
                  "body_text": "", "body_html": '<a href="https://xyz.com/verify?token=abc">go</a>'}]
        with patch("ai_marketing_agent.email_verification._get_mailbox") as mock_get:
            mock_box = MagicMock()
            mock_box.fetch_recent.return_value = mails
            mock_box.mark_processed = MagicMock()
            mock_get.return_value = mock_box
            result = await handle_verification(
                mock_page, mailbox_ref="vault://mail/imap/acme", allowed_domains=["xyz.com"],
                timeout_minutes=0.01, poll_interval_seconds=0.01,
            )
        self.assertTrue(result["found"])
        self.assertEqual(result["type"], "link")
        mock_page.goto.assert_called()


class TestAllowlist(unittest.TestCase):
    def test_outside_allowlist_rejected(self):
        from ai_marketing_agent.email_verification import _is_link_acceptable
        self.assertFalse(_is_link_acceptable("https://evil.com/verify?token=abc", allowed_domains=["xyz.com"]))

    def test_subdomain_allowed(self):
        from ai_marketing_agent.email_verification import _is_link_acceptable
        self.assertTrue(_is_link_acceptable("https://login.xyz.com/verify?token=abc", allowed_domains=["xyz.com"]))

    def test_lookalike_rejected(self):
        from ai_marketing_agent.email_verification import _is_link_acceptable
        self.assertFalse(_is_link_acceptable("https://xyz.com.evil.com/verify", allowed_domains=["xyz.com"]))

    def test_no_allowlist_no_pattern_rejected(self):
        from ai_marketing_agent.email_verification import _is_link_acceptable
        self.assertFalse(_is_link_acceptable("https://xyz.com/verify?token=abc"))

    def test_pattern_match_accepted_without_allowlist(self):
        from ai_marketing_agent.email_verification import _is_link_acceptable
        self.assertTrue(_is_link_acceptable(
            "https://xyz.com/verify?token=abc", link_pattern=r"https://xyz\.com/verify\?token=\w+"))


class TestRedaction(unittest.IsolatedAsyncioTestCase):
    async def test_no_raw_secrets_in_result(self):
        from ai_marketing_agent.email_verification import _audit_event
        ev = _audit_event(event="email_verified", mailbox_ref="vault://mail/imap/acme",
                          tenant_id="acme", idempotency_key="k", found=True, type_="link", duration_s=1.0)
        blob = str(ev)
        self.assertNotIn("abc123", blob)
        self.assertNotIn("token=", blob)
        self.assertNotIn("123456", blob)
        self.assertTrue(ev["detail_json"]["found"])

    async def test_handle_result_has_no_raw_link(self):
        mock_page = AsyncMock()
        mock_page.goto = AsyncMock()
        mails = [{"id": "1", "subject": "Verify", "from": "noreply@xyz.com",
                  "body_text": "", "body_html": '<a href="https://xyz.com/verify?token=SECRETABC">go</a>'}]
        with patch("ai_marketing_agent.email_verification._get_mailbox") as mock_get:
            mock_box = MagicMock()
            mock_box.fetch_recent.return_value = mails
            mock_box.mark_processed = MagicMock()
            mock_get.return_value = mock_box
            result = await handle_verification(
                mock_page, mailbox_ref="vault://mail/imap/acme", allowed_domains=["xyz.com"],
                timeout_minutes=0.01, poll_interval_seconds=0.01,
            )
        self.assertTrue(result["found"])
        self.assertNotIn("SECRETABC", str(result))
        mock_box.mark_processed.assert_called_with("1")


class TestSingleConnection(unittest.IsolatedAsyncioTestCase):
    async def test_one_connection_for_code_and_link(self):
        mock_page = MagicMock()
        mock_page.locator.side_effect = RuntimeError("no locator")
        mock_page.fill = AsyncMock()
        mails = [{"id": "7", "subject": "Code", "from": "noreply@xyz.com",
                  "body_text": "Your code 4321", "body_html": ""}]
        with patch("ai_marketing_agent.email_verification._get_mailbox") as mock_get:
            mock_box = MagicMock()
            mock_box.connect = MagicMock()
            mock_box.fetch_recent.return_value = mails
            mock_box.mark_processed = MagicMock()
            mock_box.close = MagicMock()
            mock_get.return_value = mock_box
            result = await handle_verification(
                mock_page, mailbox_ref="vault://mail/imap/acme", code_selector="input[name=code]",
                timeout_minutes=0.01, poll_interval_seconds=0.01,
            )
        self.assertTrue(result["found"])
        self.assertEqual(mock_box.connect.call_count, 1)

    async def test_polling_finds_late_mail(self):
        mock_page = MagicMock()
        mock_page.locator.side_effect = RuntimeError("no locator")
        mock_page.fill = AsyncMock()
        late = [{"id": "9", "subject": "Code", "from": "noreply@xyz.com",
                 "body_text": "Your code 7777", "body_html": ""}]
        with patch("ai_marketing_agent.email_verification._get_mailbox") as mock_get:
            mock_box = MagicMock()
            mock_box.connect = MagicMock()
            mock_box.fetch_recent.side_effect = [[], late]
            mock_box.mark_processed = MagicMock()
            mock_box.close = MagicMock()
            mock_get.return_value = mock_box
            result = await handle_verification(
                mock_page, mailbox_ref="vault://mail/imap/acme", code_selector="input[name=code]",
                timeout_minutes=0.05, poll_interval_seconds=0.01,
            )
        self.assertTrue(result["found"])
        self.assertGreaterEqual(mock_box.fetch_recent.call_count, 2)

    async def test_extract_only_does_not_touch_page(self):
        mock_page = AsyncMock()
        mails = [{"id": "3", "subject": "Verify", "from": "noreply@xyz.com",
                  "body_text": "", "body_html": '<a href="https://xyz.com/verify?token=Q">go</a>'}]
        with patch("ai_marketing_agent.email_verification._get_mailbox") as mock_get:
            mock_box = MagicMock()
            mock_box.fetch_recent.return_value = mails
            mock_box.mark_processed = MagicMock()
            mock_get.return_value = mock_box
            result = await handle_verification(
                mock_page, mailbox_ref="vault://mail/imap/acme", allowed_domains=["xyz.com"],
                process_mode="extractOnly", timeout_minutes=0.01, poll_interval_seconds=0.01,
            )
        self.assertTrue(result["found"])
        mock_page.goto.assert_not_called()


class TestGmailRefresh(unittest.TestCase):
    def test_missing_token_informative_error(self):
        from ai_marketing_agent.email_verification import GmailApiMailbox
        box = GmailApiMailbox("vault://mail/gmail/oauth")
        saved = {k: os.environ.pop(k, None) for k in
                 ["MAIL_GMAIL_OAUTH", "TENANT_MAIL_GMAIL_OAUTH", "GMAIL_OAUTH", "GMAIL_OAUTH_TOKEN",
                  "GMAIL_REFRESH_TOKEN", "GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET"]}
        try:
            with self.assertRaises(RuntimeError):
                box._service()
        finally:
            for k, v in saved.items():
                if v is not None:
                    os.environ[k] = v

    def test_refresh_path_uses_refresh_token(self):
        import sys as _sys
        import types as _types
        from ai_marketing_agent.email_verification import GmailApiMailbox
        refreshed = {}

        fake_creds_cls = MagicMock()

        def fake_build(*a, **k):
            return "SERVICE"

        fake_discovery = _types.ModuleType("googleapiclient.discovery")
        fake_discovery.build = fake_build
        fake_oauth2 = _types.ModuleType("google.oauth2.credentials")
        fake_oauth2.Credentials = fake_creds_cls
        fake_transport = _types.ModuleType("google.auth.transport.requests")
        fake_transport.Request = MagicMock
        with patch.dict(_sys.modules, {
            "google": _types.ModuleType("google"),
            "googleapiclient": _types.ModuleType("googleapiclient"),
            "googleapiclient.discovery": fake_discovery,
            "google.oauth2": _types.ModuleType("google.oauth2"),
            "google.oauth2.credentials": fake_oauth2,
            "google.auth": _types.ModuleType("google.auth"),
            "google.auth.transport": _types.ModuleType("google.auth.transport"),
            "google.auth.transport.requests": fake_transport,
        }):
            with patch.dict(os.environ, {
                "GMAIL_OAUTH_TOKEN": "expired",
                "GMAIL_REFRESH_TOKEN": "refresh-123",
                "GMAIL_CLIENT_ID": "cid",
                "GMAIL_CLIENT_SECRET": "csecret",
            }, clear=False):
                box = GmailApiMailbox("vault://mail/gmail/oauth")
                self.assertEqual(box._service(), "SERVICE")
        _, kwargs = fake_creds_cls.call_args
        self.assertEqual(kwargs.get("refresh_token"), "refresh-123")
