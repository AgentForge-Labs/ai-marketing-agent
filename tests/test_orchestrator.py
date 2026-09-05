"""#13 Phase 9: Distribution Orchestrator (feat-scoped only, mock data)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_marketing_agent.orchestrator import (  # noqa: E402
    Campaign,
    ChannelCandidate,
    OrchestratorState,
    next_best_action,
    release,
    score_channel,
)


def cand(channel_id="c1", **over):
    base = dict(buyer_intent=0.8, product_fit=0.9, audience_fit=0.7, policy_confidence=0.9,
                automation_reliability=0.8, historical_conversion=0.5, freshness=1.0, expected_cost=2.0)
    base.update(over)
    return ChannelCandidate(channel_id=channel_id, **base)


class OrchestratorTests(unittest.TestCase):
    def test_score_multiplies_and_divides(self):
        s = score_channel(cand())
        self.assertAlmostEqual(s, 0.8 * 0.9 * 0.7 * 0.9 * 0.8 * 0.5 / 2.0)
        self.assertEqual(score_channel(cand(expected_cost=0)), 0.0)
        self.assertEqual(score_channel(cand(buyer_intent=-1)), 0.0)

    def test_picks_highest_score(self):
        camp = Campaign(campaign_id="k", tenant_id="t")
        pick = next_best_action(camp, [cand("low", buyer_intent=0.1), cand("high", buyer_intent=0.9)])
        assert pick is not None
        self.assertEqual(pick["channel_id"], "high")

    def test_kill_switch_and_budget(self):
        self.assertIsNone(next_best_action(Campaign("k", "t", paused=True), [cand()]))
        self.assertIsNone(next_best_action(Campaign("k", "t", budget=10, spent=10), [cand()]))

    def test_skips_unhealthy_no_quota_cooldown_future(self):
        camp = Campaign("k", "t")
        self.assertIsNone(next_best_action(camp, [cand(session_healthy=False)]))
        self.assertIsNone(next_best_action(camp, [cand(quota_remaining=0)]))
        self.assertIsNone(next_best_action(camp, [cand(cooldown_until=9999999999.0)]))
        self.assertIsNone(next_best_action(camp, [cand(scheduled_at=9999999999.0)]))

    def test_concurrency_caps_and_release(self):
        camp = Campaign("k", "t")
        state = OrchestratorState(max_per_channel=1)
        first = next_best_action(camp, [cand("c1")], state=state)
        self.assertIsNotNone(first)
        self.assertIsNone(next_best_action(camp, [cand("c1")], state=state))
        release(state, "c1")
        self.assertIsNotNone(next_best_action(camp, [cand("c1")], state=state))

    def test_empty_candidates(self):
        self.assertIsNone(next_best_action(Campaign("k", "t"), []))


if __name__ == "__main__":
    unittest.main()
