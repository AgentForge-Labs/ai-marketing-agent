"""SQLite prototype persistence for canonical channels, risk audits and preflight observations."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .catalogue import Channel, ChannelCatalogue
from .risk_router import ACTION_COLUMNS, PlatformRiskRouter, RouteDecision, normalize_action
from .url_preflight import PreflightResult, normalize_http_url, preflight_url

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MIGRATIONS_DIR = PROJECT_ROOT / "database" / "migrations"


class MigrationError(RuntimeError):
    """Raised when migration history is missing or has changed after application."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _stable_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def connect_sqlite(path: str | Path) -> sqlite3.Connection:
    path_text = str(path)
    if path_text != ":memory:":
        Path(path_text).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path_text)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    if path_text != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL")
    return conn


def apply_migrations(conn: sqlite3.Connection, migrations_dir: str | Path = DEFAULT_MIGRATIONS_DIR) -> int:
    directory = Path(migrations_dir)
    files = sorted(directory.glob("[0-9][0-9][0-9]_*.sql"))
    if not files:
        raise MigrationError(f"no migration files found in {directory}")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            checksum TEXT NOT NULL,
            applied_at TEXT NOT NULL
        )
        """
    )
    applied_count = 0
    for migration in files:
        version = migration.name.split("_", 1)[0]
        sql = migration.read_text(encoding="utf-8")
        checksum = _sha256_text(sql)
        existing = conn.execute(
            "SELECT checksum, filename FROM schema_migrations WHERE version = ?", (version,)
        ).fetchone()
        if existing:
            if existing["checksum"] != checksum or existing["filename"] != migration.name:
                raise MigrationError(f"applied migration {version} differs from tracked file {migration.name}")
            continue
        try:
            conn.executescript("BEGIN IMMEDIATE;\n" + sql)
            conn.execute(
                "INSERT INTO schema_migrations(version, filename, checksum, applied_at) VALUES(?,?,?,?)",
                (version, migration.name, checksum, utc_now()),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        applied_count += 1
    return applied_count


@dataclass(frozen=True, slots=True)
class ImportSummary:
    channels: int
    action_risks: int
    changed_channels: int
    changed_action_risks: int

    def to_dict(self) -> dict[str, int]:
        return {
            "channels": self.channels,
            "action_risks": self.action_risks,
            "changed_channels": self.changed_channels,
            "changed_action_risks": self.changed_action_risks,
        }


class RuntimeStore:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    @classmethod
    def open(
        cls,
        path: str | Path,
        *,
        migrations_dir: str | Path = DEFAULT_MIGRATIONS_DIR,
    ) -> "RuntimeStore":
        conn = connect_sqlite(path)
        apply_migrations(conn, migrations_dir)
        return cls(conn)

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "RuntimeStore":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        self.close()

    def import_catalogue(self, catalogue: ChannelCatalogue) -> ImportSummary:
        now = utc_now()
        changed_channels = 0
        changed_action_risks = 0
        pilot_cells = ChannelCatalogue.pilot_raw_cells()
        with self.conn:
            for channel in catalogue:
                raw = dict(channel.raw)
                homepage = normalize_http_url(raw["Homepage URL"])
                register_submit = normalize_http_url(raw["Register / Submit URL"])
                login = normalize_http_url(raw["Login URL"])
                raw_json = _stable_json(raw)
                source_hash = _sha256_text(raw_json)
                before = self.conn.total_changes
                self.conn.execute(
                    """
                    INSERT INTO site_registry(
                        rank, site, domain, channel_type, homepage_url, register_submit_url, login_url,
                        url_confidence, automation_fit, preferred_automation_route, runtime_mode,
                        risk_reviewed_at, action_risk_model, raw_json, source_hash, imported_at, updated_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(rank) DO UPDATE SET
                        site=excluded.site,
                        domain=excluded.domain,
                        channel_type=excluded.channel_type,
                        homepage_url=excluded.homepage_url,
                        register_submit_url=excluded.register_submit_url,
                        login_url=excluded.login_url,
                        url_confidence=excluded.url_confidence,
                        automation_fit=excluded.automation_fit,
                        preferred_automation_route=excluded.preferred_automation_route,
                        runtime_mode=excluded.runtime_mode,
                        risk_reviewed_at=excluded.risk_reviewed_at,
                        action_risk_model=excluded.action_risk_model,
                        raw_json=excluded.raw_json,
                        source_hash=excluded.source_hash,
                        updated_at=excluded.updated_at
                    WHERE site_registry.source_hash <> excluded.source_hash
                    """,
                    (
                        channel.rank,
                        channel.site,
                        channel.domain,
                        channel.channel_type,
                        homepage,
                        register_submit,
                        login,
                        raw.get("URL Confidence", ""),
                        raw.get("Automation Fit", ""),
                        raw.get("Preferred Automation Route", ""),
                        raw.get("0-HITL Runtime Mode", ""),
                        raw.get("Risk Reviewed At", ""),
                        raw["Action Risk Model"],
                        raw_json,
                        source_hash,
                        now,
                        now,
                    ),
                )
                if self.conn.total_changes > before:
                    changed_channels += 1

                for action, risk in channel.action_risks.items():
                    if action in ACTION_COLUMNS:
                        raw_cell = raw[ACTION_COLUMNS[action]]
                    else:
                        # Pilot override cell (#33): provenance from the JSON file.
                        raw_cell = pilot_cells.get(
                            ChannelCatalogue._normalize_domain(channel.domain), {}).get(action, "")
                    medium_json = _stable_json(dict(risk.medium_risks))
                    risk_hash = _sha256_text(
                        _stable_json(
                            {
                                "action": action,
                                "main_risk": risk.main_risk,
                                "best_medium": risk.best_medium,
                                "medium_risks": dict(risk.medium_risks),
                                "note": risk.note,
                                "raw_cell": raw_cell,
                            }
                        )
                    )
                    before = self.conn.total_changes
                    self.conn.execute(
                        """
                        INSERT INTO channel_action_risk(
                            channel_rank, action, main_risk, best_medium, medium_risks_json,
                            note, raw_cell, source_hash, imported_at, updated_at
                        ) VALUES(?,?,?,?,?,?,?,?,?,?)
                        ON CONFLICT(channel_rank, action) DO UPDATE SET
                            main_risk=excluded.main_risk,
                            best_medium=excluded.best_medium,
                            medium_risks_json=excluded.medium_risks_json,
                            note=excluded.note,
                            raw_cell=excluded.raw_cell,
                            source_hash=excluded.source_hash,
                            updated_at=excluded.updated_at
                        WHERE channel_action_risk.source_hash <> excluded.source_hash
                        """,
                        (
                            channel.rank,
                            action,
                            risk.main_risk,
                            risk.best_medium,
                            medium_json,
                            risk.note,
                            raw_cell,
                            risk_hash,
                            now,
                            now,
                        ),
                    )
                    if self.conn.total_changes > before:
                        changed_action_risks += 1

        return ImportSummary(
            channels=len(catalogue),
            action_risks=sum(len(channel.action_risks) for channel in catalogue),
            changed_channels=changed_channels,
            changed_action_risks=changed_action_risks,
        )

    def append_risk_decision(self, decision: RouteDecision, requested_action: str) -> str:
        if decision.channel_rank is None:
            raise ValueError("cannot audit a decision without a channel rank")
        decision_id = uuid.uuid4().hex
        normalized = normalize_action(requested_action) or decision.action
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO risk_decision(
                    decision_id, channel_rank, site, domain, requested_action, normalized_action,
                    main_risk, selected_medium, execution_mode, should_execute, reason, note,
                    medium_risks_json, decided_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    decision_id,
                    decision.channel_rank,
                    decision.site,
                    decision.domain,
                    requested_action,
                    normalized,
                    decision.main_risk,
                    decision.selected_medium,
                    decision.execution_mode,
                    int(decision.should_execute),
                    decision.reason,
                    decision.note,
                    _stable_json(dict(decision.medium_risks)),
                    utc_now(),
                ),
            )
        return decision_id

    def route_and_audit(
        self,
        channel: Channel,
        requested_action: str,
        *,
        router: PlatformRiskRouter | None = None,
    ) -> tuple[RouteDecision, str]:
        active_router = router or PlatformRiskRouter()
        decision = active_router.route(channel, requested_action)
        decision_id = self.append_risk_decision(decision, requested_action)
        return decision, decision_id

    @staticmethod
    def _channel_url(channel: Channel, url_kind: str) -> str:
        mapping = {
            "homepage": "Homepage URL",
            "register_submit": "Register / Submit URL",
            "login": "Login URL",
        }
        if url_kind not in mapping:
            raise ValueError(f"unknown URL kind: {url_kind!r}")
        return channel.raw[mapping[url_kind]]

    def append_preflight_observation(
        self,
        channel_rank: int,
        url_kind: str,
        result: PreflightResult,
    ) -> str:
        observation_id = uuid.uuid4().hex
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO url_preflight_observation(
                    observation_id, channel_rank, url_kind, requested_url, normalized_url,
                    status, http_status, final_url, error, observed_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    observation_id,
                    channel_rank,
                    url_kind,
                    result.requested_url,
                    result.normalized_url,
                    result.status,
                    result.http_status,
                    result.final_url,
                    result.error,
                    result.observed_at,
                ),
            )
        return observation_id

    def preflight_channel_url(
        self,
        channel: Channel,
        url_kind: str,
        **kwargs,
    ) -> tuple[PreflightResult, str]:
        url = self._channel_url(channel, url_kind)
        result = preflight_url(url, **kwargs)
        observation_id = self.append_preflight_observation(channel.rank, url_kind, result)
        return result, observation_id

    def table_count(self, table: str) -> int:
        allowed = {
            "site_registry",
            "channel_action_risk",
            "risk_decision",
            "url_preflight_observation",
            "schema_migrations",
        }
        if table not in allowed:
            raise ValueError(f"unsupported table: {table}")
        return int(self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
