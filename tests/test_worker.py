"""#29 worker loop (feat-scoped: real sqlite queue + real catalogue/router, fake run fns)."""
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_marketing_agent.queue import enqueue, ensure_queue_tables, get_job  # noqa: E402
from ai_marketing_agent.worker import run_once, serve_forever  # noqa: E402

BROWSER_DOMAIN = "g2.com"      # Low submit via local_browser_agent (real CSV)
API_DOMAIN = "linkedin.com"    # Low submit via official_api (real CSV)


class Stub:
    def __init__(self, status, detail=None):
        self.status = status
        self.detail = detail or {}


def adapter(domain, allowed, flows):
    return {"siteId": "t", "domains": [domain], "policy": {"allowedActions": allowed}, "flows": flows}


FLOW = {"entryUrl": "https://example.com/submit", "fields": [],
        "submit": {"locator": {"kind": "css", "value": "button[type=submit]"}},
        "success": [{"kind": "url", "matches": "ok"}]}


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_queue_tables(self.conn)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def put(self, site_id, operation):
        return enqueue(self.conn, tenant_id="t1", site_id=site_id, operation=operation,
                       key_parts=["t1", site_id, operation, "v1"])

    def write_adapter(self, site_id, data):
        (self.dir / f"{site_id}.json").write_text(json.dumps(data), encoding="utf-8")

    def test_done_path(self):
        self.write_adapter("s1", adapter(BROWSER_DOMAIN, ["submitListing"], {"submitListing": FLOW}))
        jid = self.put("s1", "submitListing")
        out = run_once(self.conn, "w1", run_fn=lambda a, d, f, v: Stub("done"),
                       adapters_dir=self.dir)
        self.assertEqual(out, "done")
        self.assertEqual(get_job(self.conn, jid)["status"], "done")

    def test_failed_path_retries(self):
        self.write_adapter("s1", adapter(BROWSER_DOMAIN, ["submitListing"], {"submitListing": FLOW}))
        jid = self.put("s1", "submitListing")
        out = run_once(self.conn, "w1", run_fn=lambda a, d, f, v: Stub("failed", {"reason": "x"}),
                       adapters_dir=self.dir)
        self.assertEqual(out, "failed")
        self.assertEqual(get_job(self.conn, jid)["status"], "queued")  # backoff retry

    def test_exception_path(self):
        self.write_adapter("s1", adapter(BROWSER_DOMAIN, ["submitListing"], {"submitListing": FLOW}))
        self.put("s1", "submitListing")
        def boom(a, d, f, v):
            raise RuntimeError("pw missing")
        out = run_once(self.conn, "w1", run_fn=boom, adapters_dir=self.dir)
        self.assertEqual(out, "failed")

    def test_no_adapter_quarantine(self):
        jid = self.put("ghost", "submitListing")
        self.assertEqual(run_once(self.conn, "w1", adapters_dir=self.dir), "quarantined")
        self.assertEqual(get_job(self.conn, jid)["status"], "auto_quarantine")

    def test_operation_denied_and_no_flow(self):
        self.write_adapter("s1", adapter(BROWSER_DOMAIN, ["submitListing"], {"submitListing": FLOW}))
        jid = self.put("s1", "dm_outreach")
        self.assertEqual(run_once(self.conn, "w1", adapters_dir=self.dir), "quarantined")
        self.assertEqual(get_job(self.conn, jid)["status"], "auto_quarantine")
        self.write_adapter("s2", adapter(BROWSER_DOMAIN, ["submitListing"], {}))
        jid2 = self.put("s2", "submitListing")
        self.assertEqual(run_once(self.conn, "w1", adapters_dir=self.dir), "quarantined")
        self.assertEqual(get_job(self.conn, jid2)["status"], "auto_quarantine")

    def test_unknown_matrix_action_quarantine(self):
        self.write_adapter("s1", adapter(BROWSER_DOMAIN, ["register"], {"register": FLOW}))
        jid = self.put("s1", "register")
        self.assertEqual(run_once(self.conn, "w1", adapters_dir=self.dir), "quarantined")
        self.assertEqual(get_job(self.conn, jid)["status"], "auto_quarantine")

    def test_api_branch_and_not_wired(self):
        self.write_adapter("s1", adapter(API_DOMAIN, ["submitListing"], {"submitListing": FLOW}))
        self.put("s1", "submitListing")
        out = run_once(self.conn, "w1", run_fn=lambda a, d, f, v: Stub("done"),
                       adapters_dir=self.dir)
        self.assertEqual(out, "failed")  # api_fn missing -> fail, browser fn NOT used
        self.write_adapter("s2", adapter(API_DOMAIN, ["submitListing"], {"submitListing": FLOW}))
        jid = self.put("s2", "submitListing")
        seen = {}
        def api_fn(a, d, f, v):
            seen["medium"] = d.selected_medium
            return Stub("done")
        out = run_once(self.conn, "w1", api_fn=api_fn,
                       run_fn=lambda a, d, f, v: (_ for _ in ()).throw(AssertionError("browser must not run")),
                       adapters_dir=self.dir)
        self.assertEqual(out, "done")
        self.assertEqual(seen["medium"], "official_api")
        self.assertEqual(get_job(self.conn, jid)["status"], "done")

    def test_idle(self):
        self.assertEqual(run_once(self.conn, "w1", adapters_dir=self.dir), "idle")

    def test_serve_forever_settles_then_idles(self):
        import threading
        db = str(self.dir / "q.db")

        def factory():
            c = sqlite3.connect(db, timeout=10)
            c.row_factory = sqlite3.Row
            ensure_queue_tables(c)
            return c

        c0 = factory()
        enqueue(c0, tenant_id="t1", site_id="s1", operation="submitListing",
                key_parts=["t1", "s1", "submitListing", "v1"])
        c0.close()
        self.write_adapter("s1", adapter(BROWSER_DOMAIN, ["submitListing"], {"submitListing": FLOW}))
        stop = threading.Event()
        threading.Timer(3.0, stop.set).start()
        n = serve_forever(factory, "w1", poll_seconds=0.05, stop=stop,
                          run_fn=lambda a, d, f, v: Stub("done"),
                          adapters_dir=self.dir)
        self.assertEqual(n, 1)
        c1 = factory()
        row = c1.execute("SELECT status FROM jobs").fetchone()
        c1.close()
        self.assertEqual(row["status"], "done")


if __name__ == "__main__":
    unittest.main()
