"""Analytics + learning loop (Phase 10, #14) — static rank becomes a prior.

Real outcomes update channel_scores: reliability, conversion, cost, ROI.
next-best-action selection reads updated scores instead of static ranking.
Deterministic, stdlib + sqlite3 only.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class ChannelScore:
    channel_id: str
    attempts: int = 0
    successes: int = 0
    conversions: int = 0
    total_cost: float = 0.0
    total_value: float = 0.0
    score: float = 0.0

    @property
    def reliability(self) -> float:
        return self.successes / self.attempts if self.attempts else 0.0

    @property
    def conversion_rate(self) -> float:
        return self.conversions / self.attempts if self.attempts else 0.0

    @property
    def roi(self) -> float:
        if self.total_cost <= 0:
            return 0.0 if self.total_value <= 0 else float("inf")
        return (self.total_value - self.total_cost) / self.total_cost


def compute_score(successes: int, attempts: int, conversions: int, total_cost: float, total_value: float) -> float:
    """score = reliability x (1 + conversion_rate) x (1 + clamped_roi) / (1 + cost).

    Rewards reliability first, then conversion and ROI; cost dampens.
    Non-positive attempts -> 0.0 (no data, no rank).
    """
    if attempts <= 0:
        return 0.0
    reliability = max(0.0, min(1.0, successes / attempts))
    conv_rate = max(0.0, conversions / attempts)
    if total_cost <= 0:
        roi_term = 1.0 if total_value <= 0 else 2.0
    else:
        roi_term = max(0.0, min(3.0, 1.0 + (total_value - total_cost) / total_cost))
    return max(0.0, reliability * (1.0 + conv_rate) * roi_term / (1.0 + max(0.0, total_cost)))


class AnalyticsStore:
    """SQLite-backed scores + conversion events (prototype; PG port mirrors it)."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def record_attempt(self, channel_id: str, *, success: bool, cost: float = 0.0) -> None:
        with self.conn:
            self.conn.execute(
                """INSERT INTO channel_scores(channel_id, attempts, successes, conversions,
                                              total_cost, total_value, score, updated_at)
                   VALUES(?, 1, ?, 0, ?, 0.0, 0.0, ?)
                   ON CONFLICT(channel_id) DO UPDATE SET
                     attempts=attempts+1, successes=successes+excluded.successes,
                     total_cost=total_cost+excluded.total_cost, updated_at=excluded.updated_at""",
                (channel_id, 1 if success else 0, max(0.0, cost), _utc_now()),
            )
            self._refresh_score(channel_id)

    def record_conversion(self, channel_id: str, value: float = 0.0, *,
                          campaign_id: str = "", kind: str = "signup") -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO conversion_events(channel_id, campaign_id, kind, value, occurred_at) VALUES(?,?,?,?,?)",
                (channel_id, campaign_id, kind, value, _utc_now()),
            )
            self.conn.execute(
                """INSERT INTO channel_scores(channel_id, attempts, successes, conversions,
                                              total_cost, total_value, score, updated_at)
                   VALUES(?, 0, 0, 1, 0.0, ?, 0.0, ?)
                   ON CONFLICT(channel_id) DO UPDATE SET
                     conversions=conversions+1, total_value=total_value+excluded.total_value,
                     updated_at=excluded.updated_at""",
                (channel_id, max(0.0, value), _utc_now()),
            )
            self._refresh_score(channel_id)

    def _refresh_score(self, channel_id: str) -> None:
        row = self.conn.execute(
            "SELECT attempts, successes, conversions, total_cost, total_value FROM channel_scores WHERE channel_id=?",
            (channel_id,),
        ).fetchone()
        if not row:
            return
        score = compute_score(row["attempts"], row["successes"], row["conversions"],
                              row["total_cost"], row["total_value"])
        self.conn.execute("UPDATE channel_scores SET score=?, updated_at=? WHERE channel_id=?",
                          (score, _utc_now(), channel_id))

    def get_score(self, channel_id: str) -> Optional[ChannelScore]:
        row = self.conn.execute("SELECT * FROM channel_scores WHERE channel_id=?", (channel_id,)).fetchone()
        if not row:
            return None
        return ChannelScore(channel_id=row["channel_id"], attempts=row["attempts"], successes=row["successes"],
                            conversions=row["conversions"], total_cost=row["total_cost"],
                            total_value=row["total_value"], score=row["score"])

    def ranking(self) -> List[ChannelScore]:
        rows = self.conn.execute("SELECT * FROM channel_scores ORDER BY score DESC").fetchall()
        return [ChannelScore(channel_id=r["channel_id"], attempts=r["attempts"], successes=r["successes"],
                             conversions=r["conversions"], total_cost=r["total_cost"],
                             total_value=r["total_value"], score=r["score"]) for r in rows]

    def to_next_best_input(self, channel_id: str) -> Dict[str, Any]:
        """Feed real outcomes into orchestrator selection (historical_conversion)."""
        score = self.get_score(channel_id)
        if score is None:
            return {"historical_conversion": 0.0}
        return {"historical_conversion": score.conversion_rate}
