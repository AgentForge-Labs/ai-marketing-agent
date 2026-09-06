"""#26 management HTTP API (feat-scoped: real HTTP + real store, no mocks, no secrets)."""
import json
import sqlite3
import sys
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_marketing_agent.api import ApiServer  # noqa: E402
from ai_marketing_agent.metrics import get_metrics  # noqa: E402
from ai_marketing_agent.saas import SaaSStore  # noqa: E402
from ai_marketing_agent.storage import apply_migrations  # noqa: E402


def call(base, method, path, token=None, payload=None):
    req = urllib.request.Request(base + path, method=method,
                                 data=json.dumps(payload).encode() if payload is not None else None,
                                 headers={"Content-Type": "application/json"})
    if token:
        req.add_header("X-API-Token", token)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        try:
            return e.code, e.read().decode()
        finally:
            e.close()


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        conn = sqlite3.connect(":memory:", check_same_thread=False)
        conn.row_factory = sqlite3.Row
        apply_migrations(conn, ROOT / "database" / "migrations")
        cls.conn = conn
        cls.store = SaaSStore(conn)
        cls.tenant = cls.store.create_tenant("ops")
        cls.key = cls.store.issue_api_key(cls.tenant, "test")
        cls.srv = ApiServer(cls.store).start()
        cls.base = cls.srv.url
        get_metrics().inc("api_selftest_total")

    @classmethod
    def tearDownClass(cls):
        cls.srv.stop()
        cls.conn.close()

    def test_health_open(self):
        status, body = call(self.base, "GET", "/health")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["status"], "ok")

    def test_auth_required(self):
        for path in ["/metrics", "/stats", "/quota", "/route", "/consent"]:
            status, _ = call(self.base, "GET" if path != "/route" else "POST", path)
            self.assertEqual(status, 401, path)
        status, _ = call(self.base, "GET", "/stats", token="ak_wrong")
        self.assertEqual(status, 401)

    def test_metrics_and_stats(self):
        status, body = call(self.base, "GET", "/metrics", token=self.key)
        self.assertEqual(status, 200)
        self.assertIn("api_selftest_total 1", body)
        status, body = call(self.base, "GET", "/stats", token=self.key)
        snap = json.loads(body)
        self.assertEqual(snap["tenant_id"], self.tenant)
        self.assertGreaterEqual(snap["metrics"].get("api_selftest_total", 0), 1)

    def test_route_real_decision(self):
        status, body = call(self.base, "POST", "/route", token=self.key,
                            payload={"domain": "linkedin.com", "action": "post"})
        self.assertEqual(status, 200)
        dec = json.loads(body)
        self.assertTrue(dec["should_execute"])
        self.assertEqual(dec["domain"], "linkedin.com")
        status, body = call(self.base, "POST", "/route", token=self.key,
                            payload={"domain": "nope.invalid", "action": "post"})
        self.assertEqual(json.loads(body)["execution_mode"], "auto_quarantine")

    def test_route_bad_input(self):
        status, body = call(self.base, "POST", "/route", token=self.key,
                            payload={"domain": "linkedin.com", "action": "post", "max_auto_risk": "Critical"})
        self.assertEqual(status, 400)
        status, _ = call(self.base, "POST", "/quota", token=self.key, payload={})
        self.assertEqual(status, 404)

    def test_quota_and_consent(self):
        status, body = call(self.base, "GET", "/quota", token=self.key)
        self.assertEqual(json.loads(body)["quota_remaining"], 1000)
        status, body = call(self.base, "POST", "/consent", token=self.key,
                            payload={"subject_id": "s1", "purpose": "marketing", "action": "grant"})
        self.assertEqual(status, 200)
        status, body = call(self.base, "GET", "/consent?subject_id=s1&purpose=marketing", token=self.key)
        self.assertTrue(json.loads(body)["has_consent"])
        status, body = call(self.base, "POST", "/consent", token=self.key,
                            payload={"subject_id": "s1", "purpose": "marketing", "action": "bogus"})
        self.assertEqual(status, 400)


if __name__ == "__main__":
    unittest.main()
