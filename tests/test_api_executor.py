"""#32 official_api executor (feat-scoped: local stub HTTP server, real requests)."""
import json
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_marketing_agent.api_executor import execute_api_flow  # noqa: E402

STATE = {"hits": [], "fail_once": False, "always_429": False}


class StubHandler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        payload = json.loads(self.rfile.read(length).decode() or "{}")
        STATE["hits"].append({"path": self.path, "auth": self.headers.get("Authorization"),
                              "idem": self.headers.get("X-Idem"), "payload": payload})
        if STATE["always_429"]:
            self._json(429, {"error": "slow down"})
            return
        if STATE["fail_once"]:
            STATE["fail_once"] = False
            self._json(503, {"error": "boom"})
            return
        if self.path == "/v1/listings":
            if payload.get("title") != "Acme":
                self._json(422, {"error": "bad title"})
                return
            self._json(201, {"id": "L123", "url": "https://x.test/L123", "apiKey": "SHOULD-NEVER-LEAK"})
            return
        self._json(404, {"error": "nope"})


def flow(base, **over):
    f = {"baseUrl": base,
         "requests": [{"method": "POST", "path": "/v1/listings",
                       "headersFrom": {"Authorization": "vault://sites/x/key"},
                       "payloadFrom": {"title": "content.title", "kind": "listing"},
                       "idempotencyHeader": "X-Idem",
                       "expectStatus": 201,
                       "successExtract": {"listing_id": "id", "missing": "nope.deeper"}}]}
    f.update(over)
    return f


ADAPTER = {"retry": {"maxAttempts": 3, "backoffSeconds": [0, 0], "retryOn": ["timeout", "networkError", "rateLimited"]}}
VALUES = {"content.title": "Acme"}
LOADER = lambda ref: "Bearer T" if ref == "vault://sites/x/key" else None  # noqa: E731


class ApiExecutorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), StubHandler)
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        cls.thread = threading.Thread(target=cls.srv.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.thread.join(timeout=5)

    def setUp(self):
        STATE["hits"] = []
        STATE["fail_once"] = False
        STATE["always_429"] = False

    def test_success_with_evidence(self):
        res = execute_api_flow(ADAPTER, flow(self.base), VALUES, loader=LOADER, sleep=lambda s: None)
        self.assertEqual(res.status, "done")
        step = res.detail["steps"][0]
        self.assertEqual(step["status"], 201)
        self.assertEqual(step["extracted"]["listing_id"], "L123")
        self.assertIsNone(step["extracted"]["missing"])
        hit = STATE["hits"][-1]
        self.assertEqual(hit["auth"], "Bearer T")
        self.assertTrue(hit["idem"])
        self.assertEqual(hit["payload"], {"title": "Acme", "kind": "listing"})

    def test_retry_then_success(self):
        STATE["fail_once"] = True
        res = execute_api_flow(ADAPTER, flow(self.base), VALUES, loader=LOADER, sleep=lambda s: None)
        self.assertEqual(res.status, "done")
        self.assertEqual(len(STATE["hits"]), 2)

    def test_persistent_429_fails_redacted(self):
        STATE["always_429"] = True
        res = execute_api_flow(ADAPTER, flow(self.base), VALUES, loader=LOADER, sleep=lambda s: None)
        self.assertEqual(res.status, "failed")
        self.assertIn("rateLimited", res.detail["reason"])
        self.assertEqual(len(STATE["hits"]), 3)

    def test_validation_error_no_retry(self):
        res = execute_api_flow(ADAPTER, flow(self.base), {"content.title": "Wrong"},
                               loader=LOADER, sleep=lambda s: None)
        self.assertEqual(res.status, "failed")
        self.assertIn("unexpected_status:422", res.detail["reason"])
        self.assertEqual(len(STATE["hits"]), 1)

    def test_unresolvable_header_raises(self):
        # ValueError propagates (worker maps to api_failed) — never half-executed.
        with self.assertRaises(ValueError):
            execute_api_flow(ADAPTER, flow(self.base), VALUES, loader=lambda r: None,
                             sleep=lambda s: None)
        self.assertEqual(STATE["hits"], [])

    def test_non_http_base_rejected(self):
        with self.assertRaises(ValueError):
            execute_api_flow(ADAPTER, flow("ftp://x.test"), VALUES, loader=LOADER)

    def test_missing_payload_ref_rejected(self):
        bad = flow(self.base)
        bad["requests"][0]["payloadFrom"] = {"title": "content.missing"}
        with self.assertRaises(ValueError):
            execute_api_flow(ADAPTER, bad, VALUES, loader=LOADER)


if __name__ == "__main__":
    unittest.main()
