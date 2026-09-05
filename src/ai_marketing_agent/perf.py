"""Fast-lane performance primitives (P1, #21) — cache, concurrency, benchmarks.

- TTLCache: ETag-aware entries (etag + body + stored_at). 304/unchanged content
  reuses the cached body instead of re-downloading.
- ConcurrencyGate: per-key in-flight caps (per-host preflight limits,
  maxConcurrency enforcement). Fail-closed: over-cap calls are rejected,
  never queued silently.
- Benchmark SLOs live in docs (see benchmark() output keys).
"""
from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Generic, Optional, Tuple, TypeVar

K = TypeVar("K")
V = TypeVar("V")

# Benchmark SLOs (seconds unless noted). Reported by benchmark(), enforced nowhere
# automatically — CI asserts the harness itself stays within 10x headroom.
SLO = {
    "catalogue_load_p50_s": 0.5,
    "route_decision_p50_s": 0.001,
    "preflight_single_p95_s": 10.0,
}


@dataclass
class _Entry(Generic[V]):
    value: V
    stored_at: float
    etag: Optional[str] = None


class TTLCache(Generic[V]):
    """TTL + ETag cache. get() returns (hit, value, etag)."""

    def __init__(self, ttl_seconds: float = 3600.0, max_items: int = 10_000) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_items = max_items
        self._items: Dict[Any, _Entry[V]] = {}

    def get(self, key: K, *, now: Optional[float] = None) -> Tuple[bool, Optional[V], Optional[str]]:
        entry = self._items.get(key)
        if entry is None:
            return False, None, None
        ts = now if now is not None else time.time()
        if ts - entry.stored_at > self.ttl_seconds:
            del self._items[key]
            return False, None, entry.etag
        return True, entry.value, entry.etag

    def put(self, key: K, value: V, *, etag: Optional[str] = None, now: Optional[float] = None) -> None:
        if len(self._items) >= self.max_items and key not in self._items:
            oldest = min(self._items, key=lambda k: self._items[k].stored_at)
            del self._items[oldest]
        self._items[key] = _Entry(value, now if now is not None else time.time(), etag)

    def conditional_headers(self, key: K) -> Dict[str, str]:
        """If-None-Match for conditional refetch; {} when no etag known."""
        _, _, etag = self.get(key)
        return {"If-None-Match": etag} if etag else {}


class ConcurrencyGate:
    """Per-key in-flight caps. acquire() False means: back off, do NOT queue silently."""

    def __init__(self, max_per_key: int = 1) -> None:
        self.max_per_key = max_per_key
        self._in_flight: Dict[str, int] = defaultdict(int)

    def acquire(self, key: str) -> bool:
        if self._in_flight[key] >= self.max_per_key:
            return False
        self._in_flight[key] += 1
        return True

    def release(self, key: str) -> None:
        if self._in_flight.get(key, 0) > 0:
            self._in_flight[key] -= 1

    def __enter__(self) -> "ConcurrencyGate":
        return self

    def in_flight(self, key: str) -> int:
        return self._in_flight.get(key, 0)


@dataclass
class BenchmarkResult:
    samples: int = 0
    p50_s: float = 0.0
    p95_s: float = 0.0
    slo_key: str = ""
    within_slo: bool = False


def benchmark(fn: Callable[[], Any], *, samples: int = 21, slo_key: str = "") -> BenchmarkResult:
    """Time fn() N times; report p50/p95 + SLO verdict (10x headroom for CI boxes)."""
    durations: List[float] = []
    for _ in range(max(1, samples)):
        start = time.perf_counter()
        fn()
        durations.append(time.perf_counter() - start)
    durations.sort()
    p50 = durations[len(durations) // 2]
    p95 = durations[min(len(durations) - 1, int(len(durations) * 0.95))]
    slo = SLO.get(slo_key, float("inf"))
    return BenchmarkResult(samples=len(durations), p50_s=p50, p95_s=p95,
                           slo_key=slo_key, within_slo=p95 <= slo * 10)
