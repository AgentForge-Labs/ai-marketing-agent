"""#24 P1: pacing, metrics endpoint, consent/retention (feat-scoped only, no live calls)."""
import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_marketing_agent.metrics import Metrics  # noqa: E402
from ai_marketing_agent.orchestrator import (  # noqa: E402
    AccountPacer,
    Campaign,
    ChannelCandidate,
    OrchestratorState,
    PacingRule,
    next_best_action,
    release,
)
from ai_marketing_agent.privacy import (  # noqa: E402
    ConsentRegistry,
    erase_subject,
    partition_expired,
    retention_cutoff,
)
from ai_marketing_agent.saas import SaaSStore  # noqa: E402
from ai_marketing_agent.storage import apply_migrations  # noqa: E402


def cand(cid="ch1"):
    return ChannelCandidate(channel_id=cid, buyer_intent=0.9, product_fit=0.9,
                            audience_fit=0.9, policy_confidence=0.9,
                            automation_reliability=0.9, historical_conversion=0.5)


def mem_store():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    apply_migrations(conn, ROOT / "database" / "migrations")
    return conn, SaaSStore(conn)


class PacingTests(unittest.TestCase):
    def test_min_interval_blocks_burst(self):
        pacer = AccountPacer(PacingRule(min_interval_s=300.0, max_per_day=50))
        camp, state = Campaign("c", "t"), OrchestratorState()
        first = next_best_action(camp, [cand()], state=state, account_id="a1", now=1000.0, pacer=pacer)
        self.assertIsNotNone(first)
        release(state, "ch1", "a1")
        self.assertIsNone(next_best_action(camp, [cand()], state=state, account_id="a1", now=1100.0, pacer=pacer))
        ok = next_best_action(camp, [cand()], state=state, account_id="a1", now=1400.0, pacer=pacer)
        self.assertIsNotNone(ok)

    def test_daily_cap(self):
        pacer = AccountPacer(PacingRule(min_interval_s=0.0, max_per_day=2))
        camp = Campaign("c", "t")
        ts = 1_700_000_000.0
        for i in range(2):
            state = OrchestratorState()
            self.assertIsNotNone(next_best_action(camp, [cand()], state=state, account_id="a2", now=ts + i, pacer=pacer))
        state = OrchestratorState()
        self.assertIsNone(next_best_action(camp, [cand()], state=state, account_id="a2", now=ts + 10, pacer=pacer))

    def test_no_pacer_backward_compatible(self):
        camp = Campaign("c", "t")
        self.assertIsNotNone(next_best_action(camp, [cand()], account_id="a9", now=1000.0))


class MetricsTests(unittest.TestCase):
    def test_prometheus_render(self):
        m = Metrics()
        m.inc("orchestrator_actions_total", channel_id="ch1")
        m.inc("orchestrator_actions_total", channel_id="ch1")
        m.inc("runs_total", status="done")
        text = m.render_prometheus()
        self.assertIn('orchestrator_actions_total{channel_id="ch1"} 2', text)
        self.assertIn("runs_total{status=\"done\"} 1", text)
        self.assertIn("# TYPE orchestrator_actions_total counter", text)

    def test_wired_into_orchestrator(self):
        from ai_marketing_agent.metrics import get_metrics
        get_metrics().reset()
        next_best_action(Campaign("c", "t"), [cand("wired")], account_id="m1", now=2000.0)
        self.assertIn("orchestrator_actions_total{channel_id=\"wired\"}", get_metrics().snapshot())
        get_metrics().reset()


class ConsentTests(unittest.TestCase):
    def test_registry_fail_closed(self):
        reg = ConsentRegistry()
        self.assertFalse(reg.has_consent("t", "s1", "marketing"))
        reg.grant("t", "s1", "marketing")
        self.assertTrue(reg.has_consent("t", "s1", "marketing"))
        reg.withdraw("t", "s1", "marketing")
        self.assertFalse(reg.has_consent("t", "s1", "marketing"))

    def test_store_consent_roundtrip(self):
        conn, store = mem_store()
        t = store.create_tenant("acme")
        self.assertFalse(store.has_consent(t, "s1", "marketing"))
        store.grant_consent(t, "s1", "marketing")
        self.assertTrue(store.has_consent(t, "s1", "marketing"))
        store.withdraw_consent(t, "s1", "marketing")
        self.assertFalse(store.has_consent(t, "s1", "marketing"))
        n = store.purge_consents_before("2999-01-01T00:00:00")
        self.assertEqual(n, 1)
        conn.close()

    def test_retention_and_erasure(self):
        cutoff = retention_cutoff(30, now=1_700_000_000.0)
        self.assertEqual(cutoff, 1_700_000_000.0 - 30 * 86400.0)
        with self.assertRaises(ValueError):
            retention_cutoff(0)
        items = [{"ts": cutoff - 1, "sub": "a"}, {"ts": cutoff + 1, "sub": "a"}, {"ts": cutoff + 2, "sub": "b"}]
        keep, purged = partition_expired(items, lambda i: i["ts"], cutoff)
        self.assertEqual(len(keep), 2)
        self.assertEqual(len(purged), 1)
        kept, n = erase_subject(keep, lambda i: i["sub"], "a")
        self.assertEqual((len(kept), n), (1, 1))


if __name__ == "__main__":
    unittest.main()
