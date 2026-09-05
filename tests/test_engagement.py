"""#12 Phase 8: Engagement Bot gates (feat-scoped only)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_marketing_agent.engagement import (  # noqa: E402
    EngagementEvent,
    RateLimiter,
    draft_reply,
    gate_event,
    handle_event,
)

PROFILE = {"id": "product-slug", "name": "Ürün Adı",
           "taglines": {"short60": "x", "medium120": "y"},
           "descriptions": {"short160": "a", "medium300": "b", "long1000": "c"},
           "pricingSummary": "", "categories": [], "useCases": []}


def owned(kind="reply", **over):
    base = dict(kind=kind, thread_id="t1", account_id="a1",
                thread_context="soru", opted_in=True, is_owned_content=True)
    base.update(over)
    return EngagementEvent(**base)


class GateTests(unittest.TestCase):
    def test_eligible_reply(self):
        d = gate_event(owned("reply"))
        self.assertTrue(d.allowed)

    def test_prohibited_kinds_denied(self):
        for kind in ["like", "upvote", "vote", "review", "mass_dm", "mass_comment", "amplify", "brigade"]:
            d = gate_event(owned(kind))
            self.assertFalse(d.allowed, kind)

    def test_unknown_kind_denied(self):
        self.assertFalse(gate_event(owned("poke")).allowed)

    def test_unowned_content_denied(self):
        self.assertFalse(gate_event(owned("reply", is_owned_content=False)).allowed)

    def test_route_needs_opt_in(self):
        self.assertFalse(gate_event(owned("route", opted_in=False)).allowed)
        self.assertTrue(gate_event(owned("route", opted_in=True)).allowed)


class ReplyTests(unittest.TestCase):
    def test_claim_violation_rejected(self):
        with self.assertRaises(ValueError):
            draft_reply(owned(), PROFILE, answer="Artık %95 daha hızlıyız!")

    def test_similar_rejected(self):
        with self.assertRaises(ValueError):
            draft_reply(owned(recent_texts=["Merhaba nasıl yardımcı olabilirim"]),
                        PROFILE, answer="Merhaba nasıl yardımcı olabilirim", max_similarity=0.2)

    def test_disclosure_added(self):
        out = draft_reply(owned(), PROFILE, answer="Teşekkürler, yardımcı olayım")
        self.assertIn("#ad", out)

    def test_empty_rejected(self):
        with self.assertRaises(ValueError):
            draft_reply(owned(), PROFILE, answer="  ")


class PipelineTests(unittest.TestCase):
    def test_full_pipeline_executes(self):
        out = handle_event(owned(), PROFILE, answer="Teşekkürler, yardımcı olayım")
        self.assertTrue(out.executed)
        self.assertIn("#ad", out.reply)

    def test_rate_limit_blocks(self):
        limiter = RateLimiter(max_actions=1, window_seconds=3600)
        first = handle_event(owned(), PROFILE, answer="Yanıt bir", limiter=limiter)
        self.assertTrue(first.executed)
        second = handle_event(owned(), PROFILE, answer="Tamamen farklı ikinci yanıt metni burada",
                              limiter=limiter)
        self.assertFalse(second.executed)
        self.assertEqual(second.reason, "rate_limited")

    def test_quarantine_path(self):
        out = handle_event(owned("like"), PROFILE, answer="x")
        self.assertFalse(out.executed)
        self.assertIn("prohibited", out.reason)


if __name__ == "__main__":
    unittest.main()
