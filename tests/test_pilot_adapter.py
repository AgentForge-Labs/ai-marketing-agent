"""#34 first real pilot adapter: saashub (rank 16, Low browser submit, draft)."""
import asyncio
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from ai_marketing_agent.adapter_compiler import compile_flow  # noqa: E402
from ai_marketing_agent.catalogue import ChannelCatalogue  # noqa: E402
from ai_marketing_agent.risk_router import PlatformRiskRouter  # noqa: E402
from test_runner_completion import FakePage, make_runner  # noqa: E402

ADAPTER_PATH = ROOT / "adapters" / "saashub.json"


class PilotAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.adapter = json.loads(ADAPTER_PATH.read_text(encoding="utf-8"))
        cls.catalogue = ChannelCatalogue.load()

    def test_adapter_structure(self):
        for key in ["schemaVersion", "siteId", "version", "lastVerifiedAt", "persona",
                    "domains", "policy", "auth", "flows"]:
            self.assertIn(key, self.adapter)
        self.assertEqual(self.adapter["domains"], ["saashub.com"])
        self.assertIn("submitListing", self.adapter["policy"]["allowedActions"])
        flow = self.adapter["flows"]["submitListing"]
        self.assertEqual(flow["entryUrl"], "https://www.saashub.com/submit")

    def test_matches_canonical_matrix(self):
        ch = self.catalogue.require_unique_domain("saashub.com")
        self.assertEqual(ch.rank, 16)
        d = PlatformRiskRouter().route(ch, "own_content_submit_post")
        self.assertTrue(d.should_execute)
        self.assertEqual((d.main_risk, d.selected_medium), ("Low", "local_browser_agent"))

    def test_compiles(self):
        plan = compile_flow(self.adapter["flows"]["submitListing"])
        self.assertIn({"op": "goto", "url": "https://www.saashub.com/submit"}, plan)
        dry = compile_flow(self.adapter["flows"]["submitListing"], dry_run=True)
        self.assertTrue(all(step["op"] in
                            {"goto", "fill", "select", "check", "upload", "click", "waitFor",
                             "assertText", "assertUrl", "extract", "captureScreenshot"} for step in dry))

    def test_no_fabricated_locators_or_secrets(self):
        text = ADAPTER_PATH.read_text(encoding="utf-8")
        self.assertNotRegex(text, r"sk-live-[A-Za-z0-9]{10,}")
        self.assertNotRegex(text, r"ak_[A-Za-z0-9_-]{10,}")
        for m in re.finditer(r'"(\w*Ref)"\s*:\s*"([^"]+)"', text):
            self.assertTrue(m.group(2).startswith("vault://"), f"non-vault {m.group(1)}")
        # Honest draft: no fields/success invented from an auth-gated page.
        flow = self.adapter["flows"]["submitListing"]
        self.assertEqual(flow["fields"], [])
        self.assertEqual(flow["success"], [])

    def test_runner_fails_closed_no_false_success(self):
        page = FakePage(url="https://www.saashub.com/submit",
                        content="<html>SaaSHub Submit - Top Submitted</html>",
                        present_selectors=set())
        flow = dict(self.adapter["flows"]["submitListing"])
        res = asyncio.run(make_runner().run_browser_flow(page, flow, self.adapter, values={}))
        self.assertEqual(res.status, "failed")
        self.assertEqual(res.detail["reason"], "no_success_signals")

    def test_dom_snapshot_committed(self):
        snap = ROOT / "data" / "dom_snapshots" / "saashub_rendered.html"
        self.assertTrue(snap.exists())
        self.assertGreater(snap.stat().st_size, 50000)

if __name__ == "__main__":
    unittest.main()
