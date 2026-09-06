"""#30 values resolver (feat-scoped only, no live calls, no real secrets)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_marketing_agent.values import ValuesError, default_values_fn, resolve_values  # noqa: E402

ADAPTER = {
    "auth": {"mode": "login", "usernameRef": "vault://sites/x/user", "passwordRef": "vault://sites/x/pass"},
    "flows": {
        "submitListing": {
            "fields": [
                {"valueFrom": "product.name"},
                {"valueFrom": "content.body"},
                {"valueFrom": "auth.username"},
                {"valueFrom": "vault://sites/x/extra"},
            ],
            "steps": [{"fields": [{"valueFrom": "persona.tone"}]}],
        }
    },
}

VAULT = {"vault://sites/x/user": "u1", "vault://sites/x/pass": "p1", "vault://sites/x/extra": "e1"}


def loader(ref):
    return VAULT.get(ref)


class ValuesTests(unittest.TestCase):
    def test_resolves_all_kinds(self):
        out = resolve_values(ADAPTER, "submitListing", loader=loader,
                             content={"body": "Hello"}, persona={"tone": "calm"},
                             product={"name": "Acme"})
        self.assertEqual(out, {"product.name": "Acme", "content.body": "Hello",
                               "auth.username": "u1", "vault://sites/x/extra": "e1",
                               "persona.tone": "calm"})

    def test_auth_password(self):
        ad = {"auth": ADAPTER["auth"],
              "flows": {"login": {"fields": [{"valueFrom": "auth.username"}, {"valueFrom": "auth.password"}]}}}
        out = resolve_values(ad, "login", loader=loader)
        self.assertEqual(out, {"auth.username": "u1", "auth.password": "p1"})

    def test_missing_secret_ref_fails(self):
        with self.assertRaises(ValuesError):
            resolve_values(ADAPTER, "submitListing", loader=lambda r: None,
                           content={"body": "x"}, persona={"tone": "x"}, product={"name": "x"})

    def test_missing_content_fails_closed(self):
        with self.assertRaises(ValuesError):
            resolve_values(ADAPTER, "submitListing", loader=loader, product={"name": "x"})

    def test_plaintext_auth_ref_rejected(self):
        ad = {"auth": {"usernameRef": "PLAINTEXT"},
              "flows": {"login": {"fields": [{"valueFrom": "auth.username"}]}}}
        with self.assertRaises(ValuesError):
            resolve_values(ad, "login", loader=loader)

    def test_unknown_valuefrom_rejected(self):
        ad = {"flows": {"login": {"fields": [{"valueFrom": "magic.stuff"}]}}}
        with self.assertRaises(ValuesError):
            resolve_values(ad, "login", loader=loader)

    def test_no_flow_rejected(self):
        with self.assertRaises(ValuesError):
            resolve_values({"flows": {}}, "login", loader=loader)

    def test_default_values_fn_fail_closed(self):
        job = type("J", (), {"operation": "submitListing"})()
        ad = {"flows": {"submitListing": {"fields": [{"valueFrom": "product.name"}]}}, "auth": {}}
        # No product/content wired -> ValuesError propagates (worker maps to values_failed).
        with self.assertRaises(ValuesError):
            default_values_fn(ad, job)


if __name__ == "__main__":
    unittest.main()
