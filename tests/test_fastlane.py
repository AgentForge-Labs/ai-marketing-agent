"""#21 P1: fast-lane primitives (feat-scoped only, no live network)."""
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_marketing_agent.discovery import extract_page_model  # noqa: E402
from ai_marketing_agent.perf import ConcurrencyGate, TTLCache, benchmark  # noqa: E402


class CacheTests(unittest.TestCase):
    def test_hit_miss_expiry(self):
        cache: TTLCache[str] = TTLCache(ttl_seconds=60)
        self.assertEqual(cache.get("k"), (False, None, None))
        cache.put("k", "v", etag='"e1"')
        self.assertEqual(cache.get("k"), (True, "v", '"e1"'))
        hit, _, _ = cache.get("k", now=10 ** 10)
        self.assertFalse(hit)
        self.assertEqual(cache.conditional_headers("k"), {})
        cache.put("k2", "v2", etag='"e2"')
        self.assertEqual(cache.conditional_headers("k2"), {"If-None-Match": '"e2"'})

    def test_eviction_bounded(self):
        cache: TTLCache[int] = TTLCache(ttl_seconds=9999, max_items=2)
        cache.put("a", 1, now=1.0)
        cache.put("b", 2, now=2.0)
        cache.put("c", 3, now=3.0)
        self.assertEqual(len(cache._items), 2)
        self.assertFalse(cache.get("a", now=4.0)[0])


class GateTests(unittest.TestCase):
    def test_cap_rejects_over_limit(self):
        gate = ConcurrencyGate(max_per_key=1)
        self.assertTrue(gate.acquire("host:x"))
        self.assertFalse(gate.acquire("host:x"))
        gate.release("host:x")
        self.assertTrue(gate.acquire("host:x"))

    def test_independent_keys(self):
        gate = ConcurrencyGate(max_per_key=1)
        self.assertTrue(gate.acquire("a"))
        self.assertTrue(gate.acquire("b"))


class ProbeCacheTests(unittest.TestCase):
    def test_probe_cached_within_ttl(self):
        import ai_marketing_agent.browser as browser_mod

        browser_mod._PROBE_CACHE.update(at=1000.0, value=True)
        with patch.object(browser_mod.requests, "get", side_effect=AssertionError("no network")):
            self.assertTrue(browser_mod._is_multilogin_available(now=1005.0))
        browser_mod._PROBE_CACHE.update(at=0.0, value=False)

    def test_probe_miss_returns_false_without_requests(self):
        import ai_marketing_agent.browser as browser_mod

        with patch.object(browser_mod, "requests", None):
            browser_mod._PROBE_CACHE.update(at=0.0, value=False)
            self.assertFalse(browser_mod._is_multilogin_available(now=10 ** 9))


class PageModelTests(unittest.TestCase):
    HTML = """
    <html><head><meta name="csrf-token" content="x"></head><body>
    <form action="/submit" method="post">
      <input type="email" name="email" required>
      <input type="text" name="name">
    </form>
    <a href="/api/docs">docs</a><a href="https://other.test/y">y</a>
    </body></html>
    """

    def test_forms_inputs_hints(self):
        model = extract_page_model(self.HTML, base_url="https://x.test/page")
        self.assertEqual(model["form_count"], 1)
        self.assertEqual(model["required_inputs"], 1)
        self.assertIn("/api/docs", model["api_hints"])
        self.assertIn("csrf-meta", model["auth_hints"])
        self.assertEqual(model["same_host_links"], 1)
        self.assertEqual(model["total_links"], 2)

    def test_empty_html(self):
        model = extract_page_model("", base_url="https://x.test/")
        self.assertEqual(model["form_count"], 0)


class BenchmarkTests(unittest.TestCase):
    def test_benchmark_reports_slo(self):
        res = benchmark(lambda: sum(range(100)), samples=5, slo_key="route_decision_p50_s")
        self.assertEqual(res.samples, 5)
        self.assertTrue(res.within_slo)
        self.assertGreaterEqual(res.p95_s, res.p50_s)


if __name__ == "__main__":
    unittest.main()
