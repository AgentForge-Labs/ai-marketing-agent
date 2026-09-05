"""#22 Phase 12: rollout gate matrix (feat-scoped only)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_marketing_agent.rollout import (  # noqa: E402
    GATE_ITEMS,
    GateEvidence,
    evaluate_gate,
    rollout_order,
)


def full_evidence(**over):
    base = {item: True for item in GATE_ITEMS}
    base.update(over)
    return GateEvidence(passed=base)


class RolloutTests(unittest.TestCase):
    def test_all_green_expands(self):
        v = evaluate_gate(full_evidence(), priority="P1")
        self.assertTrue(v.expand)
        self.assertEqual(v.missing, [])

    def test_single_missing_blocks(self):
        for item in GATE_ITEMS:
            ev = full_evidence(**{item: False})
            v = evaluate_gate(ev, priority="P0")
            self.assertFalse(v.expand, item)
            self.assertIn(item, v.missing)

    def test_unknown_priority_fail_closed(self):
        v = evaluate_gate(full_evidence(), priority="P9")
        self.assertFalse(v.expand)

    def test_gate_has_eleven_items(self):
        self.assertEqual(len(GATE_ITEMS), 11)
        self.assertIn("no_access_control_bypass", GATE_ITEMS)

    def test_progressive_order(self):
        fams = [
            {"family": "p3a", "priority": "P3", "health": 0.9, "verified": True},
            {"family": "p0a", "priority": "P0", "health": 0.5, "verified": True},
            {"family": "p1a", "priority": "P1", "health": 0.9, "verified": True},
            {"family": "unver", "priority": "P0", "health": 1.0, "verified": False},
            {"family": "p2a", "priority": "P2", "health": 0.4, "verified": True},
            {"family": "p2b", "priority": "P2", "health": 0.8, "verified": True},
        ]
        order = [f["family"] for f in rollout_order(fams)]
        self.assertEqual(order, ["p0a", "p1a", "p2b", "p2a", "p3a", "unver"])


if __name__ == "__main__":
    unittest.main()
