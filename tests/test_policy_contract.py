from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


class PolicyContractTests(unittest.TestCase):
    def test_contract_pins_high_and_ensemble(self):
        contract = json.loads((ROOT / "schemas" / "policy-contract.json").read_text(encoding="utf-8"))
        self.assertEqual(contract["policyContractVersion"], "1.0.0")
        self.assertEqual(contract["maxAutonomousRisk"], "High")
        self.assertEqual(contract["executableRisks"], ["Low", "Moderate", "High"])
        self.assertEqual(contract["captcha"]["defaultPolicy"], "auto_ensemble")
        self.assertTrue(contract["captcha"]["thirdPartySolversAllowed"])
        self.assertEqual(contract["captcha"]["solvers"], ["capsolver", "2captcha", "ai_lmm", "buster"])
        self.assertTrue(contract["captcha"]["solverOrder"].startswith("capsolver -> 2captcha"))

    def test_check_script_passes(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "check_policy_contract.py")],
            cwd=ROOT, text=True, capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
