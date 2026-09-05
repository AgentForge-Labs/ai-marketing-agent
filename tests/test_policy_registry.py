"""#4 Phase 1: Policy Registry + crawler (feat-scoped only)."""
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_marketing_agent.policy_crawler import crawl_policy  # noqa: E402
from ai_marketing_agent.policy_registry import (  # noqa: E402
    PolicyRecord,
    PolicyRegistry,
    evaluate_policy_gate,
)
from ai_marketing_agent.storage import RuntimeStore  # noqa: E402


def fresh_store():
    store = RuntimeStore.open(":memory:")
    return store


class RegistryTests(unittest.TestCase):
    def test_upsert_versions_are_immutable_and_ordered(self):
        store = fresh_store()
        reg = PolicyRegistry(store.conn)
        v1 = reg.upsert_policy(PolicyRecord(domain="x.test", version=0, execution="browser_auto"))
        v2 = reg.upsert_policy(PolicyRecord(domain="x.test", version=0, execution="api_auto"))
        self.assertEqual((v1, v2), (1, 2))
        cur = reg.get_current("x.test")
        assert cur is not None
        self.assertEqual(cur.version, 2)
        self.assertEqual(cur.execution, "api_auto")
        store.close()

    def test_unknown_domain_is_stale_fail_closed(self):
        store = fresh_store()
        reg = PolicyRegistry(store.conn)
        self.assertFalse(reg.is_fresh("nope.test"))
        gate = evaluate_policy_gate(reg, ["nope.test"])
        self.assertFalse(gate["proceed"])
        self.assertIn("nope.test", gate["stale"])
        store.close()

    def test_stale_record_fails_gate(self):
        store = fresh_store()
        reg = PolicyRegistry(store.conn)
        old = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat(timespec="seconds")
        reg.upsert_policy(PolicyRecord(domain="old.test", version=0, execution="browser_auto", checked_at=old))
        self.assertFalse(reg.is_fresh("old.test", max_age_days=30))
        self.assertTrue(reg.is_fresh("old.test", max_age_days=90))
        store.close()

    def test_runner_gate_quarantines_on_stale(self):
        import asyncio

        from ai_marketing_agent.runner import AutonomousRunner, RunnerConfig  # noqa: E402

        store = fresh_store()
        reg = PolicyRegistry(store.conn)
        cfg = RunnerConfig(captcha_policy="abort_and_notify", biometric_enabled=False)
        runner = AutonomousRunner(config=cfg, decision=MagicMock(), authorization=MagicMock())
        adapter = {"domains": ["stale.test"]}
        page = MagicMock()
        result = asyncio.run(runner.run_browser_flow(page, {"entryUrl": "https://stale.test/"}, adapter, policy_registry=reg))
        self.assertEqual(result.status, "auto_quarantine")
        self.assertIn("stale_policy", result.detail["reason"])
        store.close()


class CrawlerTests(unittest.TestCase):
    def test_quarantine_decision_yields_abort_policy(self):
        decision = MagicMock()
        decision.should_execute = False
        decision.action = "own_content_submit_post"
        rec = crawl_policy(domain="q.test", source_url="https://q.test/tos", decision=decision)
        self.assertEqual(rec.execution, "auto_quarantine")
        self.assertEqual(rec.captcha_policy, "abort_and_notify")
        self.assertIn("own_content_submit_post", rec.denied_actions)
        self.assertTrue(rec.crawler_hash)

    def test_executable_decision_yields_ensemble(self):
        decision = MagicMock()
        decision.should_execute = True
        decision.action = "own_content_submit_post"
        decision.execution_mode = "browser_auto"
        decision.main_risk = "Moderate"
        decision.selected_medium = "local_browser_agent"
        rec = crawl_policy(
            domain="g.test", source_url="https://g.test/tos", decision=decision,
            preflight={"status": "reachable", "final_url": "https://g.test/", "normalized_url": "https://g.test/"},
        )
        self.assertEqual(rec.execution, "browser_auto")
        self.assertEqual(rec.captcha_policy, "auto_ensemble")
        self.assertIn("own_content_submit_post", rec.allowed_actions)

    def test_no_observation_invented(self):
        rec = crawl_policy(domain="n.test", source_url="", decision=None)
        self.assertEqual(rec.execution, "auto_quarantine")
        # crawler_hash must differ when signals differ (no silent defaults)
        rec2 = crawl_policy(domain="n.test", source_url="https://n.test/tos", decision=None)
        self.assertNotEqual(rec.crawler_hash, rec2.crawler_hash)


if __name__ == "__main__":
    unittest.main()
