"""#33 register/login matrix actions (feat-scoped: real catalogue + temp overrides)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_marketing_agent.catalogue import ChannelCatalogue, CatalogueValidationError  # noqa: E402
from ai_marketing_agent.risk_router import PlatformRiskRouter, normalize_action  # noqa: E402

CELL = ("Moderate | public_http=N/A; official_api=Moderate; cli_sdk=N/A; webhook_bot=N/A; "
        "unified_api=N/A; local_browser_agent=High; browser_extension=N/A | best=official_api | "
        "note=Pilot test cell.")


class MatrixAuthTests(unittest.TestCase):
    def test_aliases_normalize(self):
        for alias, want in [("register", "register"), ("signup", "register"), ("sign_up", "register"),
                            ("login", "login"), ("signin", "login"), ("log_in", "login")]:
            self.assertEqual(normalize_action(alias), want)

    def test_no_cell_quarantines_distinct_reason(self):
        ch = SimpleNamespace(rank=1, site="X", domain="x.test", action_risks={})
        for action in ["register", "login"]:
            d = PlatformRiskRouter().route(ch, action)
            self.assertFalse(d.should_execute)
            self.assertEqual(d.action, action)
            self.assertIn("no matrix cell", d.reason)
        d = PlatformRiskRouter().route(ch, "frobnicate")
        self.assertIn("unknown action", d.reason)

    def test_pilot_cells_route(self):
        cat = ChannelCatalogue.load()
        d = PlatformRiskRouter().route(cat.require_unique_domain("linkedin.com"), "login")
        self.assertTrue(d.should_execute)
        self.assertEqual((d.main_risk, d.selected_medium, d.decision_mode),
                         ("Moderate", "official_api", "auto_with_verification"))
        d = PlatformRiskRouter().route(cat.require_unique_domain("g2.com"), "register")
        self.assertTrue(d.should_execute)
        self.assertEqual(d.main_risk, "Moderate")
        # Non-pilot domain still quarantines.
        d = PlatformRiskRouter().route(cat.require_unique_domain("g2.com"), "login")
        self.assertFalse(d.should_execute)

    def test_bad_override_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "cells.json"
            p.write_text(json.dumps({"x.test": {"register": "bogus"}}), encoding="utf-8")
            with self.assertRaises(CatalogueValidationError):
                ChannelCatalogue.load(overrides_path=p)
            p.write_text(json.dumps({"x.test": {"post": CELL}}), encoding="utf-8")
            with self.assertRaises(CatalogueValidationError):
                ChannelCatalogue.load(overrides_path=p)

    def test_missing_overrides_file_ok(self):
        cat = ChannelCatalogue.load(overrides_path=Path("/nonexistent/cells.json"))
        self.assertEqual(len(cat.channels), 1000)


if __name__ == "__main__":
    unittest.main()
