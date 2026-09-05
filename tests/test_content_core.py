"""#7 Phase 4: Content Core (feat-scoped only)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_marketing_agent.content_core import (  # noqa: E402
    ContentRequest,
    fingerprint,
    generate_content,
    jaccard_similarity,
    load_product_profile,
    verify_claims,
)

PROFILE = str(ROOT / "examples" / "product-profile.example.json")


class ContentCoreTests(unittest.TestCase):
    def setUp(self):
        self.profile = load_product_profile(PROFILE)

    def test_profile_loads_and_validates(self):
        self.assertEqual(self.profile["id"], "product-slug")
        with self.assertRaises(ValueError):
            load_product_profile(__file__)  # not a product profile

    def test_ungrounded_percentage_rejected(self):
        self.assertTrue(any("ungrounded" in v for v in verify_claims("Artık %95 daha hızlıyız!", self.profile)))

    def test_unsupported_testimonial_rejected(self):
        self.assertTrue(verify_claims("Customers said we are the best tool ever!", self.profile))

    def test_grounded_text_passes(self):
        self.assertEqual(verify_claims("SaaS ürününün 60 karakterlik özeti burada.", self.profile), [])

    def test_generate_problem_solution(self):
        art = generate_content(self.profile, ContentRequest(operation="post", template="problem_solution"))
        self.assertIn("Ürün Adı", art.body)
        self.assertIn("#ad", art.body)
        self.assertIn("#ad", art.disclosure_markers)
        self.assertEqual(len(art.fingerprint), 64)
        self.assertEqual(art.utm["utm_medium"], "post")
        self.assertEqual(art.provenance["generator"], "content_core/1.0")
        self.assertEqual(art.policy_class, "auto_valid")

    def test_similarity_gate_rewrites_by_rejecting(self):
        art = generate_content(self.profile, ContentRequest(operation="post"))
        with self.assertRaisesRegex(ValueError, "similarity above threshold"):
            generate_content(self.profile, ContentRequest(operation="post"), corpus=[art.body])

    def test_unknown_template_rejected(self):
        with self.assertRaises(ValueError):
            generate_content(self.profile, ContentRequest(operation="post", template="viral_hack"))

    def test_jaccard_and_fingerprint_stable(self):
        self.assertEqual(jaccard_similarity("abc def", "abc def"), 1.0)
        self.assertEqual(jaccard_similarity("abc", "xyz"), 0.0)
        self.assertEqual(fingerprint("x"), fingerprint("x"))


if __name__ == "__main__":
    unittest.main()
