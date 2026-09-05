"""#5 Phase 2: queue/idempotency + PG migration files (feat-scoped only, sqlite-backed)."""
import datetime
import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_marketing_agent.queue import (  # noqa: E402
    complete_job,
    enqueue,
    fail_job,
    get_job,
    idempotency_key,
    lease_next_job,
    quarantine_job,
    recover_stalled,
    ensure_queue_tables,
)


def memdb():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_queue_tables(conn)
    return conn


class QueueTests(unittest.TestCase):
    def test_idempotent_enqueue_no_duplicates(self):
        conn = memdb()
        a = enqueue(conn, tenant_id="t", site_id="s", operation="post", key_parts=["t", "s", "post", "v1"])
        b = enqueue(conn, tenant_id="t", site_id="s", operation="post", key_parts=["t", "s", "post", "v1"])
        self.assertEqual(a, b)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0], 1)
        conn.close()

    def test_idempotency_key_deterministic(self):
        self.assertEqual(idempotency_key("a", "b"), idempotency_key("a", "b"))
        self.assertNotEqual(idempotency_key("a", "b"), idempotency_key("a", "c"))

    def test_lease_and_complete(self):
        conn = memdb()
        jid = enqueue(conn, tenant_id="t", site_id="s", operation="post", key_parts=["t", "s", "1"])
        job = lease_next_job(conn, "w1")
        assert job is not None
        self.assertEqual(job.id, jid)
        self.assertIsNone(lease_next_job(conn, "w2"))
        complete_job(conn, jid)
        self.assertEqual(get_job(conn, jid)["status"], "done")
        conn.close()

    def test_retry_then_dead_letter(self):
        conn = memdb()
        jid = enqueue(conn, tenant_id="t", site_id="s", operation="post", key_parts=["t", "s", "2"], max_attempts=2)
        lease_next_job(conn, "w1")
        self.assertEqual(fail_job(conn, jid, "timeout"), "queued")
        lease_next_job(conn, "w1")
        self.assertEqual(fail_job(conn, jid, "timeout"), "dead_letter")
        self.assertEqual(get_job(conn, jid)["status"], "dead_letter")
        conn.close()

    def test_recover_stalled(self):
        conn = memdb()
        jid = enqueue(conn, tenant_id="t", site_id="s", operation="post", key_parts=["t", "s", "3"])
        lease_next_job(conn, "crashed", lease_seconds=-1)
        now = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=10)
        n = recover_stalled(conn, now=now)
        self.assertEqual(n, 1)
        self.assertEqual(get_job(conn, jid)["status"], "queued")
        conn.close()

    def test_quarantine(self):
        conn = memdb()
        jid = enqueue(conn, tenant_id="t", site_id="s", operation="dm", key_parts=["t", "s", "4"])
        quarantine_job(conn, jid, "stale_policy")
        self.assertEqual(get_job(conn, jid)["status"], "auto_quarantine")
        conn.close()

    def test_pg_migration_files_present_and_parseable(self):
        files = sorted((ROOT / "database" / "migrations_pg").glob("*.sql"))
        self.assertTrue(files)
        must_have = ["tenants", "personas", "campaigns", "contents", "adapters", "jobs",
                     "submissions", "idempotency_keys", "risk_decisions", "engagement_events",
                     "conversion_events", "audit_log"]
        for path in files:
            sql = path.read_text(encoding="utf-8")
            for table in must_have:
                self.assertIn(table, sql, f"{path.name} missing {table}")


if __name__ == "__main__":
    unittest.main()
