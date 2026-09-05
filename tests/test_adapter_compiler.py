"""#8 Phase 5: Adapter compiler + dry-run (feat-scoped only)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_marketing_agent.adapter_compiler import (  # noqa: E402
    BROWSER_OPS,
    CompileError,
    PromotionGates,
    compile_api_flow,
    compile_flow,
    detect_drift,
    fingerprint_form,
    gate_promotion,
)


def web_flow(**over):
    flow = {
        "entryUrl": "https://x.test/submit",
        "fields": [
            {"valueFrom": "product.name", "fieldType": "text",
             "locators": [{"kind": "label", "name": "Product"}]},
            {"valueFrom": "product.category", "fieldType": "select",
             "optionsValueFrom": "taxonomy.cats",
             "locators": [{"kind": "label", "name": "Category"}]},
        ],
        "submit": {"locator": {"kind": "role", "role": "button", "name": "Submit"}, "requiresApproval": False},
        "success": [{"kind": "url", "matches": "/listing/"}],
    }
    flow.update(over)
    return flow


class CompilerTests(unittest.TestCase):
    def test_compiles_bounded_ops_only(self):
        plan = compile_flow(web_flow())
        self.assertTrue(plan)
        for step in plan:
            self.assertIn(step["op"], BROWSER_OPS)
        self.assertEqual(plan[0], {"op": "goto", "url": "https://x.test/submit"})
        self.assertIn({"op": "assertUrl", "matches": "/listing/"}, plan)

    def test_dry_run_skips_submit(self):
        plan = compile_flow(web_flow(), dry_run=True)
        self.assertFalse(any(s["op"] == "click" for s in plan))
        self.assertTrue(any(s["op"] == "assertText" and "dry-run" in s.get("note", "") for s in plan))

    def test_eval_rejected(self):
        bad = web_flow()
        bad["fields"][0]["locators"] = [{"kind": "css", "value": "x'); eval('1"}]
        with self.assertRaises(CompileError):
            compile_flow(bad)
        with self.assertRaises(CompileError):
            compile_flow({"entryUrl": "https://x.test/", "note": "javascript:alert(1)"})

    def test_missing_valuefrom_rejected(self):
        bad = web_flow()
        del bad["fields"][0]["valueFrom"]
        with self.assertRaises(CompileError):
            compile_flow(bad)

    def test_unknown_locator_rejected(self):
        bad = web_flow()
        bad["fields"][0]["locators"] = [{"kind": "xpath"}]
        with self.assertRaises(CompileError):
            compile_flow(bad)

    def test_api_flow_vault_headers_enforced(self):
        good = {"baseUrl": "https://api.x.test", "requests": [{
            "name": "create", "method": "POST", "path": "/v1/items",
            "payloadFrom": {"name": "product.name"},
            "headersFrom": {"Authorization": "vault://api/x/token"},
            "expectStatus": 201, "successExtract": {"id": "$.id"}}]}
        plan = compile_api_flow(good)
        self.assertEqual(plan[0]["op"], "api_request")
        bad = {"baseUrl": "https://api.x.test", "requests": [{
            "name": "create", "method": "POST", "path": "/v1/items",
            "payloadFrom": {}, "headersFrom": {"Authorization": "Bearer PLAIN"}}]}
        with self.assertRaises(CompileError):
            compile_api_flow(bad)


class FingerprintTests(unittest.TestCase):
    def form(self, **over):
        base = {"form": {"action": "/submit", "method": "post"},
                "fields": [{"name": "n", "type": "text", "accessName": "Name", "required": True}],
                "submit": {"locator": {"kind": "role"}}}
        base.update(over)
        return base

    def test_stable_and_prefixed(self):
        fp = fingerprint_form(self.form())
        self.assertTrue(fp.startswith("sha256:") and len(fp) == 71)
        self.assertEqual(fp, fingerprint_form(self.form()))

    def test_drift_detected(self):
        a = fingerprint_form(self.form())
        changed = self.form()
        changed["fields"][0]["required"] = False
        b = fingerprint_form(changed)
        self.assertTrue(detect_drift(a, b))
        self.assertFalse(detect_drift(a, a))


class PromotionTests(unittest.TestCase):
    def test_all_gates_required(self):
        self.assertTrue(gate_promotion(PromotionGates(True, True, 0.9, 0.85, True))["promote"])
        self.assertFalse(gate_promotion(PromotionGates(True, True, 0.5, 0.85, True))["promote"])
        self.assertFalse(gate_promotion(PromotionGates(True, True, 0.9, 0.85, False))["promote"])
        self.assertEqual(gate_promotion(PromotionGates(False, False, 0.0))["next"], "quarantine")


if __name__ == "__main__":
    unittest.main()
