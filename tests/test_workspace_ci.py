"""#3 Phase 0: workspace/CI disiplini (feat-scoped only)."""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


class WorkspaceTests(unittest.TestCase):
    def test_requirements_files_exist_and_parse(self):
        req = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        self.assertIn("requests", req)
        lock = (ROOT / "requirements.lock").read_text(encoding="utf-8")
        pinned = [l for l in lock.splitlines() if l and not l.startswith("#") and "==" in l]
        self.assertGreaterEqual(len(pinned), 1)
        for line in pinned:
            self.assertRegex(line.strip(), r"^[A-Za-z0-9_.\-]+==[A-Za-z0-9_.\-]+$")

    def test_lock_covers_floor_pins(self):
        req_names = set()
        for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            req_names.add(re.split(r"[<>=!~\s\[]", line, 1)[0])
        lock_names = {l.split("==")[0].strip().lower().replace("-", "_") for l in
                      (ROOT / "requirements.lock").read_text(encoding="utf-8").splitlines()
                      if l and not l.startswith("#")}
        for name in req_names:
            self.assertIn(name.lower().replace("-", "_"), lock_names, f"{name} missing in lock")

    def test_ci_workflow_has_required_steps(self):
        ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        for needle in ["check_policy_contract.py", "unittest discover", "validate_schemas.py",
                       "compileall", "scan_secrets.py", "requirements.lock"]:
            self.assertIn(needle, ci, f"ci.yml missing: {needle}")

    def test_schemas_and_examples_parse(self):
        checked = 0
        for path in sorted((ROOT / "schemas").glob("*.json")) + sorted((ROOT / "examples").glob("*.json")):
            json.loads(path.read_text(encoding="utf-8"))
            checked += 1
        self.assertGreater(checked, 0)

    def test_contributing_states_test_rule(self):
        text = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
        self.assertIn("vault://", text)
        self.assertIn("FINAL", text)


if __name__ == "__main__":
    unittest.main()
