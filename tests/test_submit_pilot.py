"""#10 Phase 6: submit pilot logic (feat-scoped only, no live submit)."""
import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_marketing_agent.submit import (  # noqa: E402
    AmbiguousOutcome,
    SubmitPlan,
    ensure_submit_tables,
    pilot_checklist,
    pre_submit_check,
    record_submission,
    resolve_ambiguous,
)


def memdb():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_submit_tables(conn)
    return conn


def plan(**over):
    base = dict(tenant_id="t", site_id="s.test", operation="submitListing",
                content_version="v1", canonical_target="https://s.test/submit",
                content_semantic_key="abc123")
    base.update(over)
    return SubmitPlan(**base)


class SubmitPilotTests(unittest.TestCase):
    def test_idempotency_blocks_resubmit(self):
        conn = memdb()
        p = plan()
        self.assertIsNone(pre_submit_check(conn, p))
        record_submission(conn, p, listing_url="https://s.test/l/1", external_id="ext-1")
        existing = pre_submit_check(conn, p)
        assert existing is not None
        self.assertEqual(existing["listing_url"], "https://s.test/l/1")
        conn.close()

    def test_different_version_is_new_action(self):
        conn = memdb()
        record_submission(conn, plan())
        self.assertIsNone(pre_submit_check(conn, plan(content_version="v2", content_semantic_key="def456")))
        conn.close()

    def test_ambiguous_adopts_existing(self):
        outcome = AmbiguousOutcome(plan=plan(), finder=lambda p: {"url": "https://s.test/l/9"})
        res = resolve_ambiguous(outcome)
        self.assertEqual(res["action"], "adopt_existing")
        self.assertEqual(res["remote"], {"url": "https://s.test/l/9"})

    def test_ambiguous_queues_new_with_new_version(self):
        outcome = AmbiguousOutcome(plan=plan(), finder=lambda p: None)
        res = resolve_ambiguous(outcome)
        self.assertEqual(res["action"], "queue_new")

    def test_ambiguous_without_finder_quarantines(self):
        res = resolve_ambiguous(AmbiguousOutcome(plan=plan()))
        self.assertEqual(res["action"], "quarantine")

    def test_ambiguous_lookup_error_quarantines(self):
        def boom(p):
            raise RuntimeError("network down")
        res = resolve_ambiguous(AmbiguousOutcome(plan=plan(), finder=boom))
        self.assertEqual(res["action"], "quarantine")

    def test_pilot_gate_needs_three_clean_runs(self):
        self.assertFalse(pilot_checklist(adapter_ok=True, idempotency_ok=True, assertion_ok=True, runs=2)["pilot_pass"])
        self.assertTrue(pilot_checklist(adapter_ok=True, idempotency_ok=True, assertion_ok=True, runs=3)["pilot_pass"])
        self.assertFalse(pilot_checklist(adapter_ok=True, idempotency_ok=False, assertion_ok=True, runs=5)["pilot_pass"])


if __name__ == "__main__":
    unittest.main()
