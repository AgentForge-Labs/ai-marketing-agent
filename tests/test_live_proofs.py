"""#9 Phase 5B-live: proof artifact checks (feat-scoped only, no live calls)."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import check_live_proofs as clp  # noqa: E402


def good_profile():
    bucket = {"overshoot_rate": 0.1, "jitter_amplitude_px": {"mean": 1.2},
              "velocity_shape": {"peak_mean": 0.4}}
    return {"version": "1.0", "source_segments": 50,
            "global": {"inter_event_delay_ms": {"mean_ms": 16.0}},
            "hardware_click": {"mean_ms": 85.0},
            "buckets": {"short": bucket, "medium": bucket, "long": bucket}}


def fake_root(files: dict) -> Path:
    td = tempfile.TemporaryDirectory()
    root = Path(td.name)
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    import atexit
    atexit.register(td.cleanup)
    return root


class LiveProofTests(unittest.TestCase):
    def test_checklist_runs_without_live_calls(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "check_live_proofs.py")],
            cwd=ROOT, text=True, capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(set(report), {"mouse_profile", "solves_evidence", "vault_refs"})
        for item in report.values():
            self.assertIn(item["status"], ("ready", "missing", "invalid"))

    def test_mouse_profile_valid(self):
        root = fake_root({"services/biometric-mouse/profile/mouse_profile.json": json.dumps(good_profile())})
        res = clp.check_mouse_profile(root)
        self.assertEqual(res["status"], "ready")

    def test_mouse_profile_missing_bucket(self):
        bad = good_profile()
        del bad["buckets"]["long"]
        root = fake_root({"services/biometric-mouse/profile/mouse_profile.json": json.dumps(bad)})
        res = clp.check_mouse_profile(root)
        self.assertEqual(res["status"], "invalid")
        self.assertIn("long", res["detail"])

    def test_mouse_profile_rejects_secrets(self):
        bad = good_profile()
        # NOTE: must NOT match scripts/scan_secrets.py patterns (CI hygiene fails
        # closed otherwise); validator keys off the api_key field name + 16+ chars.
        bad["api_key"] = "FIXTURE-NOT-A-SECRET-0123456789"
        root = fake_root({"services/biometric-mouse/profile/mouse_profile.json": json.dumps(bad)})
        res = clp.check_mouse_profile(root)
        self.assertEqual(res["status"], "invalid")
        self.assertIn("secret", res["detail"].lower())

    def test_solves_evidence_flags_raw_token(self):
        root = fake_root({"services/captcha-ensemble/successful_solves/run1.json":
                          '{"type":"recaptcha","gRecaptchaResponse": "ABCDEFGHIJ1234567890abcdef"}'})
        res = clp.check_solves_evidence(root)
        self.assertEqual(res["status"], "invalid")
        self.assertIn("run1.json", res["detail"])

    def test_solves_evidence_masked_ok(self):
        root = fake_root({"services/captcha-ensemble/successful_solves/run1.json":
                          '{"type":"recaptcha","result":"success","duration_s":12}'})
        res = clp.check_solves_evidence(root)
        self.assertEqual(res["status"], "ready")

    def test_vault_refs_collected(self):
        root = fake_root({"examples/a.json": json.dumps({"k": "vault://captcha/capsolver/apiKey"})})
        res = clp.check_vault_refs(root)
        self.assertIn("vault://captcha/capsolver/apiKey", res["missing"] + res["resolved"])


if __name__ == "__main__":
    unittest.main()
