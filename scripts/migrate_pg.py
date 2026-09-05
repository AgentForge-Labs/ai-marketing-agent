#!/usr/bin/env python3
"""Apply database/migrations_pg/*.sql to PostgreSQL (DATABASE_URL).

Requires psycopg (v3) installed; without it exits 2 with guidance.
SQLite prototype (database/migrations/) is untouched and stays for tests/dev.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "database" / "migrations_pg"


def main() -> int:
    dsn = os.getenv("DATABASE_URL", "")
    if not dsn.startswith(("postgresql://", "postgres://")):
        print("DATABASE_URL must be a postgresql:// URL (SQLite stays for tests).")
        return 2
    try:
        import psycopg  # type: ignore
    except ImportError:
        print("psycopg (v3) is required: pip install 'psycopg[binary]'. No changes applied.")
        return 2
    files = sorted(MIGRATIONS.glob("*.sql"))
    if not files:
        print(f"no PG migrations in {MIGRATIONS}")
        return 2
    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ DEFAULT now())")
            for path in files:
                version = path.stem.split("_", 1)[0]
                cur.execute("SELECT 1 FROM schema_migrations WHERE version = %s", (version,))
                if cur.fetchone():
                    print(f"SKIP {path.name} (applied)")
                    continue
                cur.execute(path.read_text(encoding="utf-8"))
                cur.execute("INSERT INTO schema_migrations(version) VALUES (%s)", (version,))
                print(f"APPLIED {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
