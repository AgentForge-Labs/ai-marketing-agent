"""#27 dashboard: served, wired to same-origin API, no external deps/secrets."""
import re
import sqlite3
import sys
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_marketing_agent.api import ApiServer  # noqa: E402
from ai_marketing_agent.saas import SaaSStore  # noqa: E402
from ai_marketing_agent.storage import apply_migrations  # noqa: E402


def get(base, path):
    with urllib.request.urlopen(base + path, timeout=10) as r:
        return r.status, r.headers.get("Content-Type", ""), r.read().decode()


class DashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        conn = sqlite3.connect(":memory:", check_same_thread=False)
        conn.row_factory = sqlite3.Row
        apply_migrations(conn, ROOT / "database" / "migrations")
        cls.conn = conn
        store = SaaSStore(conn)
        cls.key = store.issue_api_key(store.create_tenant("dash"), "test")
        cls.srv = ApiServer(store).start()
        cls.base = cls.srv.url

    @classmethod
    def tearDownClass(cls):
        cls.srv.stop()
        cls.conn.close()

    def test_index_served(self):
        status, ctype, body = get(self.base, "/dashboard")
        self.assertEqual(status, 200)
        self.assertIn("text/html", ctype)
        for marker in ["Ops Dashboard", "routeBtn", "cGrant", "apiKey", 'src="app.js"']:
            self.assertIn(marker, body)

    def test_app_js_served(self):
        status, ctype, body = get(self.base, "/dashboard/app.js")
        self.assertEqual(status, 200)
        self.assertIn("javascript", ctype)
        for endpoint in ["/health", "/quota", "/stats", "/route", "/consent"]:
            self.assertIn(f'"{endpoint}"' if "?" not in endpoint else endpoint.split("?")[0], body)

    def test_no_external_dependencies(self):
        for name in ["index.html", "app.js"]:
            text = (ROOT / "dashboard" / name).read_text(encoding="utf-8")
            for m in re.finditer(r'https?://[^\s"\'<>]+', text):
                self.fail(f"external URL in dashboard/{name}: {m.group(0)}")
            self.assertNotIn("cdn", text.lower())

    def test_no_secrets_in_dashboard(self):
        for name in ["index.html", "app.js"]:
            text = (ROOT / "dashboard" / name).read_text(encoding="utf-8")
            self.assertNotRegex(text, r"sk-live-[A-Za-z0-9]{10,}")
            self.assertNotRegex(text, r"ak_[A-Za-z0-9_-]{10,}")

    def test_unknown_paths_fail_closed(self):
        # No token -> 401 even for unknown paths (auth before routing).
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            get(self.base, "/dashboard/nope.js")
        self.assertEqual(ctx.exception.code, 401)
        # Valid token + unknown path -> 404.
        req = urllib.request.Request(self.base + "/dashboard/nope.js",
                                     headers={"X-API-Token": self.key})
        with self.assertRaises(urllib.error.HTTPError) as ctx2:
            urllib.request.urlopen(req, timeout=10).close()
        self.assertEqual(ctx2.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
