"""#6 Phase 3: Persona Engine + identity registry (feat-scoped only)."""
import os
import sqlite3
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_marketing_agent.account_reuse import BanState  # noqa: E402
from ai_marketing_agent.persona import (  # noqa: E402
    Persona,
    PersonaRegistry,
    refresh_oauth_token,
    totp_now,
)
from ai_marketing_agent.storage import apply_migrations  # noqa: E402


def mem_registry():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    apply_migrations(conn, ROOT / "database" / "migrations")
    return conn, PersonaRegistry(conn)


class PersonaTests(unittest.TestCase):
    def test_create_and_get_persona(self):
        conn, reg = mem_registry()
        pid = reg.create_persona(Persona(persona_id="p1", tenant_id="t", display_name="Ada",
                                         allowed_channel_classes=["directory"]))
        got = reg.get_persona(pid)
        assert got is not None
        self.assertEqual(got.display_name, "Ada")
        self.assertEqual(got.allowed_channel_classes, ["directory"])
        conn.close()

    def test_eligibility_filters_channel_class(self):
        conn, reg = mem_registry()
        reg.create_persona(Persona(persona_id="p1", allowed_channel_classes=["directory"]))
        reg.create_persona(Persona(persona_id="p2", allowed_channel_classes=["social"]))
        reg.create_persona(Persona(persona_id="p3"))  # no restriction -> eligible everywhere
        got = {p.persona_id for p in reg.eligible_personas("directory")}
        self.assertEqual(got, {"p1", "p3"})
        conn.close()

    def test_single_account_platform_rejects_second(self):
        conn, reg = mem_registry()
        reg.register_account(tenant_id="t", site_id="s.test", persona_id=None,
                             credential_ref="vault://a/b", session_ref="vault://a/c")
        with self.assertRaises(PermissionError):
            reg.register_account(tenant_id="t", site_id="s.test", persona_id=None,
                                 credential_ref="vault://a/d", session_ref="vault://a/e",
                                 multi_account_allowed=False)
        conn.close()

    def test_second_account_requires_entitlement_gate(self):
        conn, reg = mem_registry()
        reg.register_account(tenant_id="t", site_id="m.test", persona_id=None,
                             credential_ref="vault://a/b", session_ref="vault://a/c")
        # banned -> denied even with fresh pair
        with self.assertRaises(PermissionError):
            reg.register_account(tenant_id="t", site_id="m.test", persona_id=None,
                                 credential_ref="vault://a/d", session_ref="vault://a/e",
                                 multi_account_allowed=True, ban_state=BanState(banned=True))
        # allowed platform + fresh pair -> ok
        aid = reg.register_account(tenant_id="t", site_id="m.test", persona_id=None,
                                   credential_ref="vault://a/d", session_ref="vault://a/e",
                                   multi_account_allowed=True)
        self.assertTrue(aid)
        conn.close()

    def test_plaintext_secret_rejected_by_db(self):
        conn, reg = mem_registry()
        with self.assertRaises(Exception):
            reg.register_account(tenant_id="t", site_id="p.test", persona_id=None,
                                 credential_ref="hunter2-plaintext", session_ref="vault://a/c")
        conn.close()

    def test_session_health_and_quarantine(self):
        conn, reg = mem_registry()
        aid = reg.register_account(tenant_id="t", site_id="h.test", persona_id=None,
                                   credential_ref="vault://a/b", session_ref="vault://a/c")
        self.assertEqual(reg.session_health(aid), "active")
        reg.quarantine_account(aid, "access challenge")
        self.assertEqual(reg.session_health(aid), "quarantined")
        self.assertEqual(reg.session_health("missing"), "unknown")
        conn.close()

    def test_totp_rfc6238_vector(self):
        # RFC 6238 Appendix B, SHA1, T=59 -> 94287082 (8 digits)
        self.assertEqual(totp_now("GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ", digits=8, at=59), "94287082")
        self.assertEqual(len(totp_now("JBSWY3DPEHPK3PXP", at=0)), 6)

    def test_resolve_totp_never_stores_secret(self):
        conn, reg = mem_registry()
        aid = reg.register_account(tenant_id="t", site_id="t.test", persona_id=None,
                                   credential_ref="vault://a/b", session_ref="vault://a/c",
                                   totp_ref="vault://mail/totp/x")
        with patch.dict(os.environ, {"MAIL_TOTP_X": "JBSWY3DPEHPK3PXP"}):
            code = reg.resolve_totp(aid, at=0)
        self.assertEqual(len(code), 6)
        row = conn.execute("SELECT totp_ref FROM accounts WHERE account_id=?", (aid,)).fetchone()
        self.assertEqual(row["totp_ref"], "vault://mail/totp/x")
        conn.close()

    def test_oauth_refresh_posts_grant(self):
        fake = MagicMock()
        fake.json.return_value = {"access_token": "new-at", "expires_in": 3600}
        fake.raise_for_status.return_value = None
        with patch("requests.post", return_value=fake) as mocked:
            data = refresh_oauth_token(token_url="https://x.test/token", client_id="cid", refresh_token="rt")
        self.assertEqual(data["access_token"], "new-at")
        _, kwargs = mocked.call_args
        self.assertEqual(kwargs["data"]["grant_type"], "refresh_token")


if __name__ == "__main__":
    unittest.main()
