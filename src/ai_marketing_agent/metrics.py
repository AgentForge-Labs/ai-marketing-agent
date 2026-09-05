"""Ops metrics (#24) — process-local counters with a Prometheus text endpoint.

No external dependency: `render_prometheus()` returns the standard exposition
format so any scraper (or the SaaS dashboard) can poll it. Thread-safe.
"""
from __future__ import annotations

import threading
from typing import Dict, Tuple


class Metrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: Dict[Tuple[str, Tuple[Tuple[str, str], ...]], float] = {}

    def inc(self, name: str, amount: float = 1.0, **labels: str) -> None:
        key = (name, tuple(sorted(labels.items())))
        with self._lock:
            self._counters[key] = self._counters.get(key, 0.0) + amount

    def snapshot(self) -> Dict[str, float]:
        with self._lock:
            return {self._fmt(k): v for k, v in self._counters.items()}

    @staticmethod
    def _fmt(key: Tuple[str, Tuple[Tuple[str, str], ...]]) -> str:
        name, labels = key
        if not labels:
            return name
        inner = ",".join(f'{k}="{v}"' for k, v in labels)
        return f"{name}{{{inner}}}"

    def render_prometheus(self) -> str:
        lines = []
        with self._lock:
            items = sorted(self._counters.items(), key=lambda kv: self._fmt(kv[0]))
        for key, value in items:
            lines.append(f"# TYPE {key[0]} counter")
            lines.append(f"{self._fmt(key)} {value:g}")
        return "\n".join(lines) + ("\n" if lines else "")

    def reset(self) -> None:
        with self._lock:
            self._counters.clear()


_METRICS = Metrics()


def get_metrics() -> Metrics:
    return _METRICS
