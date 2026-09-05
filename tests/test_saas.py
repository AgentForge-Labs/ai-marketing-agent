"""#15 Phase 11: SaaS isolation/RBAC/metering (feat-scoped only)."""
import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_marketing_agent.saas import SaaSStore  # noqa: E402
from ai_marketing_agent.storage import apply_migrations  # noqa: E402


def mem_store():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    apply_migrations(conn, ROOT / "database" / "migrations")
    return conn, SaaSStore(conn)


class SaaSTests(unittest.TestCase):
    def test_isolation_denied(self):
        from ai_marketing_agent.saas import Tenant  # noqa
        SaaSStore.assert_same_tenant("t1", "t1")
        with self.assertRaises(PermissionError):
            SaaSStore.assert_same_tenant("t1", "t2")
        with self.assertRaises(PermissionError):
            SaaSStore.assert_same_tenant("", "t1")

    def test_rbac_hierarchy(self):
        conn, store = mem_store()
        t = store.create_tenant("acme")
        owner = store.create_user("o@x.test")
        viewer = store.create_user("v@x.test")
        store.add_member(t, owner, "owner")
        store.add_member(t, viewer, "viewer")
        store.require_role(t, owner, "admin")
        store.require_role(t, viewer, "viewer")
        with self.assertRaises(PermissionError):
            store.require_role(t, viewer, "editor")
        with self.assertRaises(PermissionError):
            store.require_role(t, "ghost", "viewer")
        with self.assertRaises(ValueError):
            store.add_member(t, viewer, "superuser")
        conn.close()

    def test_api_key_hash_only_and_revoke(self):
        conn, store = mem_store()
        t = store.create_tenant("acme")
        raw = store.issue_api_key(t, "ci")
        self.assertTrue(raw.startswith("ak_"))
        row = conn.execute("SELECT key_hash FROM api_keys").fetchone()
        self.assertNotIn(raw, row["key_hash"])
        self.assertEqual(store.authenticate_key(raw), t)
        self.assertIsNone(store.authenticate_key("ak_wrong"))
        store.revoke_key(raw)
        self.assertIsNone(store.authenticate_key(raw))
        conn.close()

    def test_quota_and_kill_switch(self):
        conn, store = mem_store()
        t = store.create_tenant("acme", monthly_quota=2)
        store.check_quota(t)
        store.record_usage(t, 2)
        with self.assertRaises(PermissionError):
            store.check_quota(t)
        # kill switch wins even with quota left
        t2 = store.create_tenant("emca", monthly_quota=100)
        store.set_paused(t2, True)
        with self.assertRaises(PermissionError):
            store.check_quota(t2)
        self.assertTrue(store.is_paused(t2))
        conn.close()


if __name__ == "__main__":
    unittest.main()
