"""#20 P0: verified entitlement gate — ban/accountReuse matrix (feat-scoped only)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ai_marketing_agent.account_reuse import (  # noqa: E402
    BanState,
    PlatformPolicy,
    assert_reopen_allowed,
    audit_record,
)


def allow(**kw):
    args = dict(fresh_profile=True, fresh_ip=True, reuses_ip=False, reuses_profile=False)
    args.update(kw)
    return assert_reopen_allowed(
        PlatformPolicy(multi_account_allowed=True), BanState(), **args
    )


class AccountReuseTests(unittest.TestCase):
    def test_allowed_fresh_pair_permitted_platform(self):
        self.assertIsNone(allow())

    def test_banned_denied_even_with_fresh_pair(self):
        with self.assertRaises(PermissionError):
            assert_reopen_allowed(
                PlatformPolicy(multi_account_allowed=True),
                BanState(banned=True, reason="spam"),
                fresh_profile=True, fresh_ip=True,
            )

    def test_suspended_denied_even_with_fresh_pair(self):
        with self.assertRaises(PermissionError):
            assert_reopen_allowed(
                PlatformPolicy(multi_account_allowed=True),
                BanState(suspended=True),
                fresh_profile=True, fresh_ip=True,
            )

    def test_reused_ip_alone_denied(self):
        with self.assertRaises(PermissionError):
            allow(reuses_ip=True, fresh_ip=False)

    def test_reused_profile_alone_denied(self):
        with self.assertRaises(PermissionError):
            allow(reuses_profile=True, fresh_profile=False)

    def test_only_one_fresh_denied(self):
        with self.assertRaises(PermissionError):
            allow(fresh_ip=False)
        with self.assertRaises(PermissionError):
            allow(fresh_profile=False)

    def test_platform_forbids_multi_account_denied(self):
        with self.assertRaises(PermissionError):
            assert_reopen_allowed(
                PlatformPolicy(multi_account_allowed=False),
                BanState(),
                fresh_profile=True, fresh_ip=True,
            )

    def test_audit_record_has_no_secrets(self):
        rec = audit_record(tenant_id="acme", platform="x.test", allowed=False, reason="banned")
        blob = str(rec)
        self.assertNotIn("1.2.3.4", blob)
        self.assertIn("account_reopen_denied", blob)
        self.assertEqual(rec["detail_json"]["allowed"], False)


if __name__ == "__main__":
    unittest.main()
