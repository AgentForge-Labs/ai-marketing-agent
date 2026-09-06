"""#37 mail wiring + golden-rule identity (feat-scoped, fake transports, no secrets)."""
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_marketing_agent.email_verification import (  # noqa: E402
    BridgeMailbox,
    _bridge_provider_of,
    _get_mailbox,
)
from ai_marketing_agent.identity import (  # noqa: E402
    IdentityBinding,
    IdentityViolation,
    check_identity,
    ensure_identity_tables,
)

FAKE_MAILS = [
    {"id": "m1", "subject": "Verify 112233", "from_addr": "n@x.test",
     "body_text": "code 112233", "body_html": ""},
]


class FakeBox:
    def __init__(self, *a, **k):
        self.connected = False
        self.marked = []

    def connect(self):
        self.connected = True

    def close(self):
        self.connected = False

    def fetch_recent(self, **kw):
        m = MagicMock()
        m.id, m.subject, m.from_addr = "m1", "Verify 112233", "n@x.test"
        m.body_text, m.body_html = "code 112233", ""
        return [m]

    def mark_processed(self, mid):
        self.marked.append(mid)


class BridgeWiringTests(unittest.TestCase):
    def test_provider_detection(self):
        self.assertEqual(_bridge_provider_of("vault://mail/disroot/brand"), "disroot")
        self.assertEqual(_bridge_provider_of("vault://mail/mailfence/a"), "mailfence")
        self.assertEqual(_bridge_provider_of("vault://mail/custom/a"), "custom")
        self.assertEqual(_bridge_provider_of("vault://mail/proton/a"), "proton")
        self.assertEqual(_bridge_provider_of("vault://mail/outlook/a"), "outlook")
        self.assertEqual(_bridge_provider_of("vault://mail/hotmail/a"), "hotmail")
        self.assertEqual(_bridge_provider_of("vault://mail/tuta/a"), "tuta")
        self.assertIsNone(_bridge_provider_of("vault://mail/gmail/oauth"))
        self.assertIsNone(_bridge_provider_of("vault://mail/imap/acme"))

    def test_outlook_hotmail_dispatch(self):
        self.assertIsInstance(_get_mailbox("vault://mail/outlook/acme"), BridgeMailbox)
        self.assertIsInstance(_get_mailbox("vault://mail/hotmail/acme"), BridgeMailbox)

    def test_vendored_bridge_v2_present(self):
        import mail_bridge
        for name in ["CachedToken", "OutlookGraphProvider", "build_authorize_url",
                     "refresh_access_token"]:
            self.assertTrue(hasattr(mail_bridge, name), name)

    def test_get_mailbox_dispatch(self):
        self.assertIsInstance(_get_mailbox("vault://mail/disroot/brand"), BridgeMailbox)
        from ai_marketing_agent.email_verification import GmailApiMailbox, ImapMailbox
        self.assertIsInstance(_get_mailbox("vault://mail/gmail/oauth"), GmailApiMailbox)
        self.assertIsInstance(_get_mailbox("vault://mail/imap/acme"), ImapMailbox)

    def test_bridge_fetch_adapts_shape(self):
        import ai_marketing_agent.email_verification as ev
        real_bridge = None
        try:
            from mail_bridge import MailBridge as _MB
            real_bridge = _MB
        except ImportError:
            self.skipTest("vendored mail_bridge missing")
        box = BridgeMailbox("vault://mail/disroot/brand")
        box._box = FakeBox()
        mails = box.fetch_recent(since_minutes=60)
        self.assertEqual(mails[0]["subject"], "Verify 112233")
        self.assertEqual(mails[0]["from"], "n@x.test")
        box.mark_processed("m1")
        self.assertEqual(box._box.marked, ["m1"])

    def test_tuta_fails_loudly(self):
        from mail_bridge import MailBridge, NotSupportedError
        b = MailBridge(lambda r: "x")
        with self.assertRaises(NotSupportedError):
            b.open("vault://mail/tuta/brand")


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_identity_tables(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_first_binding_ok(self):
        b = check_identity(self.conn, "t1", "x.test", "p1", "a@x.test", "1.2.3.4")
        self.assertIsInstance(b, IdentityBinding)

    def test_same_binding_replay_ok(self):
        check_identity(self.conn, "t1", "x.test", "p1", "a@x.test", "1.2.3.4")
        check_identity(self.conn, "t1", "x.test", "p1", "a@x.test", "1.2.3.4")

    def test_profile_rebind_violation(self):
        check_identity(self.conn, "t1", "x.test", "p1", "a@x.test", "1.2.3.4")
        with self.assertRaises(IdentityViolation):
            check_identity(self.conn, "t1", "x.test", "p1", "b@x.test", "1.2.3.4")
        with self.assertRaises(IdentityViolation):
            check_identity(self.conn, "t1", "x.test", "p1", "a@x.test", "9.9.9.9")

    def test_second_profile_needs_own_mail_and_ip(self):
        check_identity(self.conn, "t1", "x.test", "p1", "a@x.test", "1.2.3.4")
        with self.assertRaises(IdentityViolation):  # same mail
            check_identity(self.conn, "t1", "x.test", "p2", "a@x.test", "5.6.7.8")
        with self.assertRaises(IdentityViolation):  # same ip
            check_identity(self.conn, "t1", "x.test", "p2", "b@x.test", "1.2.3.4")
        check_identity(self.conn, "t1", "x.test", "p2", "b@x.test", "5.6.7.8")

    def test_cross_domain_mail_reuse_allowed(self):
        check_identity(self.conn, "t1", "x.test", "p1", "a@x.test", "1.2.3.4")
        check_identity(self.conn, "t1", "y.test", "p1", "a@x.test", "1.2.3.4")

    def test_empty_fields_violation(self):
        with self.assertRaises(IdentityViolation):
            check_identity(self.conn, "t1", "x.test", "p1", "", "1.2.3.4")
        with self.assertRaises(IdentityViolation):
            check_identity(self.conn, "t1", "x.test", "p1", "a@x.test", "")


class WorkerIdentityGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        from ai_marketing_agent.queue import ensure_queue_tables
        ensure_queue_tables(self.conn)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()
        for k in ["SITES_X_USER", "SITES_X_IP"]:
            os.environ.pop(k, None)

    def adapter(self, identity):
        return {"siteId": "t", "domains": ["g2.com"],
                "policy": {"allowedActions": ["submitListing"]},
                "flows": {"submitListing": {"entryUrl": "https://g2.com/x", "fields": [],
                                            "success": [{"kind": "text", "matches": "never"}]}},
                "identity": identity}

    def test_violation_quarantines_before_browser(self):
        from types import SimpleNamespace
        from ai_marketing_agent.queue import enqueue, get_job
        from ai_marketing_agent.worker import run_once
        os.environ["SITES_X_USER"] = "a@x.test"
        os.environ["SITES_X_IP"] = "1.2.3.4"
        (self.dir / "s1.json").write_text(json.dumps(self.adapter(
            {"profileId": "p1", "emailRef": "vault://sites/x/user", "ipRef": "vault://sites/x/ip"})), encoding="utf-8")
        enqueue(self.conn, tenant_id="t1", site_id="s1", operation="submitListing",
                key_parts=["t1", "s1", "v-first"])
        calls = []

        def fake_run(*a):
            calls.append(1)
            return SimpleNamespace(status="done", detail={})

        self.assertEqual(run_once(self.conn, "w1", run_fn=fake_run, adapters_dir=self.dir), "done")
        self.assertEqual(calls, [1])
        # Second profile on the SAME domain reusing mail+IP must quarantine pre-launch.
        (self.dir / "s2.json").write_text(json.dumps(self.adapter(
            {"profileId": "p2", "emailRef": "vault://sites/x/user", "ipRef": "vault://sites/x/ip"})), encoding="utf-8")
        jid2 = enqueue(self.conn, tenant_id="t1", site_id="s2", operation="submitListing",
                       key_parts=["t1", "s2", "v-second"])
        self.assertEqual(run_once(self.conn, "w1", run_fn=fake_run, adapters_dir=self.dir),
                         "quarantined")
        self.assertEqual(calls, [1])  # browser never launched for the violator
        job = get_job(self.conn, jid2)
        self.assertEqual(job["status"], "auto_quarantine")
        self.assertIn("identity", job["last_error_code"])


if __name__ == "__main__":
    unittest.main()
