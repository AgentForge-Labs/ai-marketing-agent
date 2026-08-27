from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_marketing_agent import (  # noqa: E402
    CatalogueValidationError,
    ChannelCatalogue,
    PlatformRiskRouter,
    RiskCellError,
    parse_action_risk,
)


class CanonicalCatalogueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalogue = ChannelCatalogue.load(ROOT / "data/saas_marketing_1000_channels_ranked - 1000 Channels.csv")
        cls.router = PlatformRiskRouter()

    def route(self, domain: str, action: str):
        return self.router.route(self.catalogue.require_unique_domain(domain), action)

    def test_catalogue_loads_all_1000_rows(self):
        self.assertEqual(len(self.catalogue), 1000)
        self.assertEqual(self.catalogue.channels[0].rank, 1)
        self.assertEqual(self.catalogue.channels[-1].rank, 1000)

    def test_all_8000_action_cells_are_prevalidated(self):
        self.assertEqual(sum(len(channel.action_risks) for channel in self.catalogue), 8000)

    def test_domain_lookup_normalizes_www(self):
        self.assertEqual(self.catalogue.require_unique_domain("www.linkedin.com").site, "LinkedIn")

    def test_linkedin_post_prefers_api_and_is_low(self):
        d = self.route("linkedin.com", "post")
        self.assertTrue(d.should_execute)
        self.assertEqual(d.main_risk, "Low")
        self.assertEqual(d.selected_medium, "official_api")
        self.assertEqual(d.medium_risks["local_browser_agent"], "High")
        self.assertEqual(d.execution_mode, "api_auto")

    def test_linkedin_outreach_is_critical_and_quarantined(self):
        d = self.route("linkedin.com", "dm")
        self.assertFalse(d.should_execute)
        self.assertEqual(d.main_risk, "Critical")
        self.assertEqual(d.execution_mode, "auto_quarantine")
        self.assertEqual(d.selected_medium, "none")

    def test_product_hunt_public_browse_is_low(self):
        d = self.route("producthunt.com", "browse")
        self.assertTrue(d.should_execute)
        self.assertEqual(d.main_risk, "Low")
        self.assertEqual(d.execution_mode, "api_auto")

    def test_product_hunt_submit_is_moderate_and_executable(self):
        d = self.route("producthunt.com", "submit")
        self.assertTrue(d.should_execute)
        self.assertEqual(d.main_risk, "Moderate")
        self.assertEqual(d.execution_mode, "api_auto")

    def test_product_hunt_vote_is_critical_and_quarantined(self):
        d = self.route("producthunt.com", "vote")
        self.assertFalse(d.should_execute)
        self.assertEqual(d.main_risk, "Critical")

    def test_reddit_post_is_low_via_api(self):
        d = self.route("reddit.com", "post")
        self.assertTrue(d.should_execute)
        self.assertEqual((d.main_risk, d.selected_medium, d.execution_mode), ("Low", "official_api", "api_auto"))

    def test_reddit_comment_is_low_via_api(self):
        d = self.route("reddit.com", "comment")
        self.assertTrue(d.should_execute)
        self.assertEqual((d.main_risk, d.selected_medium), ("Low", "official_api"))

    def test_reddit_vote_is_very_high_and_quarantined(self):
        d = self.route("reddit.com", "vote")
        self.assertFalse(d.should_execute)
        self.assertEqual(d.main_risk, "Very High")
        self.assertEqual(d.execution_mode, "auto_quarantine")

    def test_quora_public_research_is_low(self):
        d = self.route("quora.com", "public_browse")
        self.assertTrue(d.should_execute)
        self.assertEqual((d.main_risk, d.selected_medium, d.execution_mode), ("Low", "public_http", "auto_full"))

    def test_quora_post_is_high_and_fail_closed_by_default_threshold(self):
        d = self.route("quora.com", "post")
        self.assertFalse(d.should_execute)
        self.assertEqual(d.main_risk, "High")
        self.assertIn("exceeds autonomous threshold", d.reason)

    def test_generic_directory_owned_submit_uses_browser_when_it_is_lowest_route(self):
        # Find the first directory-style row whose submit route is browser-backed
        # and Low rather than
        # depending on a hard-coded site name.
        for channel in self.catalogue:
            risk = channel.action_risks["own_content_submit_post"]
            if risk.main_risk == "Low" and risk.best_medium in {"local_browser_agent", "browser_extension"}:
                d = self.router.route(channel, "submit")
                self.assertTrue(d.should_execute)
                self.assertEqual(d.execution_mode, "browser_auto")
                return
        self.fail("expected at least one low-risk browser-backed directory submit route")

    def test_unknown_action_is_quarantined(self):
        d = self.route("linkedin.com", "invented_action")
        self.assertFalse(d.should_execute)
        self.assertEqual(d.execution_mode, "auto_quarantine")
        self.assertIn("unknown action", d.reason)

    def test_router_cannot_raise_autonomous_threshold_above_moderate(self):
        with self.assertRaisesRegex(ValueError, "always fail-closed"):
            PlatformRiskRouter(max_autonomous_risk="High")

    def test_na_action_is_quarantined(self):
        d = self.route("linkedin.com", "review")
        self.assertFalse(d.should_execute)
        self.assertEqual(d.main_risk, "N/A")

    def test_catalogue_rejects_inconsistent_action_cell(self):
        source = ROOT / "data/saas_marketing_1000_channels_ranked - 1000 Channels.csv"
        text = source.read_text(encoding="utf-8")
        needle = "Low | public_http=N/A; official_api=Low; cli_sdk=Low; webhook_bot=N/A; unified_api=Low; local_browser_agent=High; browser_extension=Moderate | best=official_api"
        self.assertIn(needle, text)
        corrupted = text.replace(needle, needle.replace("Low |", "Moderate |", 1), 1)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "catalogue.csv"
            path.write_text(corrupted, encoding="utf-8")
            with self.assertRaisesRegex(CatalogueValidationError, "does not match supported-medium minimum"):
                ChannelCatalogue.load(path)


class RiskCellValidationTests(unittest.TestCase):
    BASE = (
        "Low | public_http=Low; official_api=N/A; cli_sdk=N/A; webhook_bot=N/A; "
        "unified_api=N/A; local_browser_agent=Moderate; browser_extension=Moderate | "
        "best=public_http | note=test"
    )

    def test_valid_cell_parses(self):
        parsed = parse_action_risk(self.BASE)
        self.assertEqual(parsed.main_risk, "Low")
        self.assertEqual(parsed.best_medium, "public_http")

    def test_parsed_medium_risks_are_immutable(self):
        parsed = parse_action_risk(self.BASE)
        with self.assertRaises(TypeError):
            parsed.medium_risks["public_http"] = "Critical"

    def test_declared_main_mismatch_is_rejected(self):
        with self.assertRaisesRegex(RiskCellError, "does not match"):
            parse_action_risk(self.BASE.replace("Low |", "Moderate |", 1))

    def test_unknown_medium_risk_is_rejected(self):
        with self.assertRaisesRegex(RiskCellError, "unknown medium risk"):
            parse_action_risk(self.BASE.replace("public_http=Low", "public_http=Riskless"))

    def test_missing_medium_is_rejected(self):
        with self.assertRaisesRegex(RiskCellError, "missing execution media"):
            parse_action_risk(self.BASE.replace("; browser_extension=Moderate", ""))

    def test_best_medium_mismatch_is_rejected(self):
        with self.assertRaisesRegex(RiskCellError, "deterministic best"):
            parse_action_risk(self.BASE.replace("best=public_http", "best=local_browser_agent"))


if __name__ == "__main__":
    unittest.main()


class CliTests(unittest.TestCase):
    def run_cli(self, domain: str, action: str):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "src")
        return subprocess.run(
            [sys.executable, "-m", "ai_marketing_agent.cli", domain, action],
            cwd=ROOT, env=env, text=True, capture_output=True, check=False
        )

    def test_cli_emits_linkedin_post_route_as_json(self):
        result = self.run_cli("linkedin.com", "post")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["selected_medium"], "official_api")
        self.assertEqual(payload["execution_mode"], "api_auto")
        self.assertTrue(payload["should_execute"])

    def test_cli_returns_nonzero_for_quarantine(self):
        result = self.run_cli("producthunt.com", "vote")
        self.assertEqual(result.returncode, 3, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["execution_mode"], "auto_quarantine")
        self.assertFalse(payload["should_execute"])
