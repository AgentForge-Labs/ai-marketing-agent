"""Durable queue: leases, worker recovery, retry/backoff, dead-letter/quarantine.

Prototype implementation on sqlite3 (same SQL style as storage.py; production
PostgreSQL port uses %s placeholders + SELECT ... FOR UPDATE SKIP LOCKED —
see database/migrations_pg/003_production_schema.sql). Fail-closed throughout.

Redaction: error payloads stored truncated (<=200 chars); never secrets.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

TERMINAL = {"done", "failed", "dead_letter", "cool_down", "needs_remap", "blocked_policy", "auto_quarantine"}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def idempotency_key(*parts: str) -> str:
    """Deterministic key: sha256 of tenant/campaign/site/operation/target/content parts."""
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def _redact(text: str, limit: int = 200) -> str:
    return (text or "")[:limit]


@dataclass
class Job:
    id: str
    tenant_id: str
    site_id: str
    operation: str
    status: str
    attempts: int
    max_attempts: int
    idempotency_key: str


def ensure_queue_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            site_id TEXT NOT NULL,
            operation TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'queued',
            attempts INTEGER NOT NULL DEFAULT 0,
            max_attempts INTEGER NOT NULL DEFAULT 3,
            next_run_at TEXT NOT NULL,
            lease_owner TEXT NOT NULL DEFAULT '',
            lease_expires_at TEXT,
            last_error_code TEXT NOT NULL DEFAULT '',
            idempotency_key TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_jobs_lease ON jobs(status, next_run_at);
        CREATE TABLE IF NOT EXISTS idempotency_keys (
            key TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            operation TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'claimed',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS queue_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT,
            event TEXT NOT NULL,
            detail TEXT NOT NULL DEFAULT '',
            occurred_at TEXT NOT NULL
        );
        """
    )
    conn.commit()


def _audit(conn: sqlite3.Connection, job_id: Optional[str], event: str, detail: str = "") -> None:
    conn.execute(
        "INSERT INTO queue_audit(job_id, event, detail, occurred_at) VALUES(?,?,?,?)",
        (job_id, event, _redact(detail), _iso(_utc_now())),
    )


def enqueue(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    site_id: str,
    operation: str,
    key_parts: List[str],
    max_attempts: int = 3,
) -> str:
    """Idempotent enqueue: same key returns existing job id, never duplicates."""
    key = idempotency_key(*key_parts)
    now = _iso(_utc_now())
    with conn:
        row = conn.execute("SELECT id FROM jobs WHERE idempotency_key = ?", (key,)).fetchone()
        if row:
            return row["id"] if isinstance(row, sqlite3.Row) else row[0]
        conn.execute("INSERT OR IGNORE INTO idempotency_keys(key, tenant_id, operation, status, created_at) VALUES(?,?,?,?,?)",
                     (key, tenant_id, operation, "claimed", now))
        job_id = uuid.uuid4().hex
        conn.execute(
            """INSERT INTO jobs(id, tenant_id, site_id, operation, status, attempts, max_attempts,
                                next_run_at, idempotency_key, created_at)
               VALUES(?,?,?,?, 'queued', 0, ?, ?, ?, ?)""",
            (job_id, tenant_id, site_id, operation, max_attempts, now, key, now),
        )
        _audit(conn, job_id, "enqueued", operation)
    return job_id


def lease_next_job(conn: sqlite3.Connection, worker: str, *, lease_seconds: int = 120) -> Optional[Job]:
    """Lease oldest due, non-terminal job. Single-writer semantics via transaction."""
    now = _utc_now()
    with conn:
        row = conn.execute(
            """SELECT id, tenant_id, site_id, operation, status, attempts, max_attempts, idempotency_key
               FROM jobs WHERE status = 'queued' AND next_run_at <= ?
               ORDER BY next_run_at LIMIT 1""",
            (_iso(now),),
        ).fetchone()
        if not row:
            return None
        expires = _iso(now + timedelta(seconds=lease_seconds))
        cur = conn.execute(
            "UPDATE jobs SET status='leased', lease_owner=?, lease_expires_at=? WHERE id=? AND status='queued'",
            (worker, expires, row["id"]),
        )
        if cur.rowcount != 1:
            return None
        _audit(conn, row["id"], "leased", worker)
        return Job(id=row["id"], tenant_id=row["tenant_id"], site_id=row["site_id"],
                   operation=row["operation"], status="leased", attempts=row["attempts"],
                   max_attempts=row["max_attempts"], idempotency_key=row["idempotency_key"])


def complete_job(conn: sqlite3.Connection, job_id: str) -> None:
    with conn:
        conn.execute("UPDATE jobs SET status='done', lease_owner='', lease_expires_at=NULL WHERE id=?", (job_id,))
        conn.execute("UPDATE idempotency_keys SET status='completed' WHERE key=(SELECT idempotency_key FROM jobs WHERE id=?)", (job_id,))
        _audit(conn, job_id, "done")


def fail_job(conn: sqlite3.Connection, job_id: str, error_code: str, *, backoff_seconds: tuple = (60, 600, 3600)) -> str:
    """Retry with backoff until max_attempts, then dead_letter. Returns new status."""
    with conn:
        row = conn.execute("SELECT attempts, max_attempts FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not row:
            raise ValueError(f"unknown job: {job_id}")
        attempts = int(row["attempts"]) + 1
        if attempts >= int(row["max_attempts"]):
            conn.execute("UPDATE jobs SET status='dead_letter', attempts=?, last_error_code=?, lease_owner='' WHERE id=?",
                         (attempts, _redact(error_code), job_id))
            _audit(conn, job_id, "dead_letter", error_code)
            return "dead_letter"
        delay = backoff_seconds[min(attempts - 1, len(backoff_seconds) - 1)]
        nxt = _iso(_utc_now() + timedelta(seconds=delay))
        conn.execute("UPDATE jobs SET status='queued', attempts=?, next_run_at=?, last_error_code=?, lease_owner='' WHERE id=?",
                     (attempts, nxt, _redact(error_code), job_id))
        _audit(conn, job_id, "retry_queued", error_code)
        return "queued"


def quarantine_job(conn: sqlite3.Connection, job_id: str, reason: str) -> None:
    with conn:
        conn.execute("UPDATE jobs SET status='auto_quarantine', last_error_code=?, lease_owner='' WHERE id=?",
                     (_redact(reason), job_id))
        _audit(conn, job_id, "auto_quarantine", reason)


def recover_stalled(conn: sqlite3.Connection, *, now: Optional[datetime] = None) -> int:
    """Worker recovery: expired leases go back to queued. Returns recovered count."""
    ref = _iso(now or _utc_now())
    with conn:
        cur = conn.execute(
            "UPDATE jobs SET status='queued', lease_owner='', lease_expires_at=NULL "
            "WHERE status IN ('leased','running') AND lease_expires_at IS NOT NULL AND lease_expires_at <= ?",
            (ref,),
        )
        n = cur.rowcount
        if n:
            _audit(conn, None, "recovered_stalled", str(n))
        return n


def get_job(conn: sqlite3.Connection, job_id: str) -> Optional[Dict[str, Any]]:
    row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    return dict(row) if row else None
