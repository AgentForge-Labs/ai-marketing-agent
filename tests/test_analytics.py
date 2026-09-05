"""#14 Phase 10: Analytics + learning loop (feat-scoped only)."""
import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_marketing_agent.analytics import (  # noqa: E402
    AnalyticsStore,
    compute_score,
)
from ai_marketing_agent.storage import apply_migrations  # noqa: E402


def mem_store():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    apply_migrations(conn, ROOT / "database" / "migrations")
    return conn, AnalyticsStore(conn)


class AnalyticsTests(unittest.TestCase):
    def test_no_data_no_rank(self):
        self.assertEqual(compute_score(0, 0, 0, 0.0, 0.0), 0.0)
        conn, store = mem_store()
        self.assertIsNone(store.get_score("c1"))
        conn.close()

    def test_reliability_beats_raw_volume(self):
        reliable = compute_score(9, 10, 1, 1.0, 5.0)
        flaky = compute_score(2, 10, 1, 1.0, 5.0)
        self.assertGreater(reliable, flaky)

    def test_conversion_and_roi_raise_score(self):
        base = compute_score(5, 10, 0, 2.0, 0.0)
        conv = compute_score(5, 10, 4, 2.0, 20.0)
        self.assertGreater(conv, base)

    def test_record_attempt_and_conversion_flow(self):
        conn, store = mem_store()
        store.record_attempt("c1", success=True, cost=1.0)
        store.record_attempt("c1", success=False, cost=1.0)
        store.record_conversion("c1", value=10.0, campaign_id="k", kind="signup")
        score = store.get_score("c1")
        assert score is not None
        self.assertEqual((score.attempts, score.successes, score.conversions), (2, 1, 1))
        self.assertAlmostEqual(score.reliability, 0.5)
        self.assertAlmostEqual(score.roi, (10.0 - 2.0) / 2.0)
        conn.close()

    def test_ranking_orders_by_score(self):
        conn, store = mem_store()
        store.record_attempt("bad", success=False)
        store.record_attempt("good", success=True)
        ranking = store.ranking()
        self.assertEqual(ranking[0].channel_id, "good")
        conn.close()

    def test_next_best_input_feeds_orchestrator(self):
        conn, store = mem_store()
        self.assertEqual(store.to_next_best_input("new"), {"historical_conversion": 0.0})
        store.record_attempt("c1", success=True)
        store.record_conversion("c1", value=5.0)
        self.assertEqual(store.to_next_best_input("c1"), {"historical_conversion": 1.0})
        conn.close()


if __name__ == "__main__":
    unittest.main()
