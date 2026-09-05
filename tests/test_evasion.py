"""#11 Phase 7: Evasion controller matrix (feat-scoped only)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_marketing_agent.evasion import (  # noqa: E402
    AnomalySignals,
    DeadPool,
    check_dead_pool,
    evaluate,
)


class EvasionTests(unittest.TestCase):
    def test_clean_proceeds(self):
        d = evaluate(AnomalySignals())
        self.assertEqual(d.action, "proceed")

    def test_ban_wins_over_everything(self):
        d = evaluate(AnomalySignals(banned=True, rate_limited=True))
        self.assertEqual(d.action, "dead_pool")
        d = evaluate(AnomalySignals(account_restricted=True))
        self.assertEqual(d.action, "dead_pool")

    def test_rate_limit_throttles(self):
        d = evaluate(AnomalySignals(rate_limited=True))
        self.assertEqual(d.action, "throttle")
        self.assertGreater(d.cooldown_minutes, 0)

    def test_failure_burst_cools_down(self):
        d = evaluate(AnomalySignals(failure_burst=3))
        self.assertEqual(d.action, "cooldown")
        d = evaluate(AnomalySignals(failure_burst=2))
        self.assertEqual(d.action, "proceed")

    def test_family_burst_pauses(self):
        d = evaluate(AnomalySignals(family_errors=5))
        self.assertEqual(d.action, "pause_family")

    def test_drift_refreshes_policy(self):
        self.assertEqual(evaluate(AnomalySignals(form_drift=True)).action, "refresh_policy")
        self.assertEqual(evaluate(AnomalySignals(session_drift=True)).action, "refresh_policy")
        self.assertEqual(evaluate(AnomalySignals(redirect_loop=True)).action, "refresh_policy")

    def test_challenge_quarantines(self):
        self.assertEqual(evaluate(AnomalySignals(challenge=True)).action, "quarantine")
        self.assertEqual(evaluate(AnomalySignals(duplicate_risk=True)).action, "quarantine")


class DeadPoolTests(unittest.TestCase):
    def test_add_and_hit(self):
        pool = DeadPool()
        pool.add(kind="ip", value_hash="abc123", reason="ban", tenant_id="t")
        self.assertTrue(pool.is_dead("ip", "abc123"))
        self.assertFalse(pool.is_dead("ip", "other"))
        hit = check_dead_pool(pool, kind="ip", value_hash="abc123")
        assert hit is not None
        self.assertFalse(hit["allowed"])
        self.assertIsNone(check_dead_pool(pool, kind="ip", value_hash="fresh"))

    def test_no_raw_identifiers_stored(self):
        pool = DeadPool()
        entry = pool.add(kind="profile", value_hash="h" * 64, reason="ban")
        self.assertNotIn("1.2.3.4", str(entry))

    def test_unknown_kind_rejected(self):
        with self.assertRaises(ValueError):
            DeadPool().add(kind="email", value_hash="x", reason="y")


if __name__ == "__main__":
    unittest.main()
