from __future__ import annotations

import io
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_marketing_agent import (  # noqa: E402
    ChannelCatalogue,
    PlatformRiskRouter,
    MigrationError,
    RuntimeStore,
    URLValidationError,
    normalize_http_url,
    preflight_url,
)
from ai_marketing_agent.storage import apply_migrations, connect_sqlite  # noqa: E402

CSV = ROOT / "data/saas_marketing_1000_channels_ranked - 1000 Channels.csv"
MIGRATIONS = ROOT / "database/migrations"
PUBLIC_ADDR = "93.184.216.34"


def public_resolver(host, port, **kwargs):
    return [(2, 1, 6, "", (PUBLIC_ADDR, port))]


class FakeResponse:
    def __init__(self, status=200, url="https://example.com/"):
        self.status = status
        self.url = url
        self.closed = False

    def getcode(self):
        return self.status

    def geturl(self):
        return self.url

    def close(self):
        self.closed = True


class FakeOpener:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.requests = []

    def open(self, request, timeout=0):
        self.requests.append((request, timeout))
        if self.error:
            raise self.error
        return self.response


class StorageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalogue = ChannelCatalogue.load(CSV)

    def make_store(self):
        td = tempfile.TemporaryDirectory()
        path = Path(td.name) / "runtime.sqlite3"
        store = RuntimeStore.open(path, migrations_dir=MIGRATIONS)
        return td, path, store

    def test_migrations_are_idempotent_and_checksum_tracked(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "db.sqlite3"
            conn = connect_sqlite(path)
            try:
                self.assertEqual(apply_migrations(conn, MIGRATIONS), 2)
                self.assertEqual(apply_migrations(conn, MIGRATIONS), 0)
                row = conn.execute("SELECT version, filename, length(checksum) AS n FROM schema_migrations ORDER BY version").fetchone()
                self.assertEqual((row["version"], row["filename"], row["n"]), ("001", "001_runtime_foundation.sql", 64))
                latest = conn.execute("SELECT version, filename FROM schema_migrations ORDER BY version DESC").fetchone()
                self.assertEqual((latest["version"], latest["filename"]), ("002", "002_policy_registry.sql"))
            finally:
                conn.close()

    def test_changed_applied_migration_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            migrations = base / "migrations"
            migrations.mkdir()
            original = MIGRATIONS / "001_runtime_foundation.sql"
            copy = migrations / original.name
            copy.write_text(original.read_text(encoding="utf-8"), encoding="utf-8")
            conn = connect_sqlite(base / "db.sqlite3")
            try:
                self.assertEqual(apply_migrations(conn, migrations), 1)
                copy.write_text(copy.read_text(encoding="utf-8") + "\n-- changed after apply\n", encoding="utf-8")
                with self.assertRaisesRegex(MigrationError, "differs from tracked file"):
                    apply_migrations(conn, migrations)
            finally:
                conn.close()

    def test_repeated_full_import_is_idempotent(self):
        td, path, store = self.make_store()
        try:
            first = store.import_catalogue(self.catalogue)
            self.assertEqual(first.to_dict(), {"channels": 1000, "action_risks": 8000, "changed_channels": 1000, "changed_action_risks": 8000})
            before = store.conn.execute("SELECT rank, source_hash, imported_at, updated_at FROM site_registry ORDER BY rank").fetchall()
            second = store.import_catalogue(self.catalogue)
            after = store.conn.execute("SELECT rank, source_hash, imported_at, updated_at FROM site_registry ORDER BY rank").fetchall()
            self.assertEqual(second.to_dict(), {"channels": 1000, "action_risks": 8000, "changed_channels": 0, "changed_action_risks": 0})
            self.assertEqual([tuple(r) for r in before], [tuple(r) for r in after])
            self.assertEqual(store.table_count("site_registry"), 1000)
            self.assertEqual(store.table_count("channel_action_risk"), 8000)
        finally:
            store.close(); td.cleanup()

    def test_all_8000_persisted_risks_match_canonical_records(self):
        td, path, store = self.make_store()
        try:
            store.import_catalogue(self.catalogue)
            rows = store.conn.execute(
                "SELECT channel_rank, action, main_risk, best_medium, medium_risks_json FROM channel_action_risk"
            ).fetchall()
            persisted = {(r["channel_rank"], r["action"]): r for r in rows}
            self.assertEqual(len(persisted), 8000)
            for channel in self.catalogue:
                for action, risk in channel.action_risks.items():
                    row = persisted[(channel.rank, action)]
                    self.assertEqual(row["main_risk"], risk.main_risk)
                    self.assertEqual(row["best_medium"], risk.best_medium)
                    self.assertEqual(json.loads(row["medium_risks_json"]), dict(risk.medium_risks))
        finally:
            store.close(); td.cleanup()

    def test_changed_source_row_updates_without_duplicates(self):
        td, path, store = self.make_store()
        try:
            first = store.import_catalogue(self.catalogue)
            old_hash = store.conn.execute("SELECT source_hash FROM site_registry WHERE rank=1").fetchone()[0]
            text = CSV.read_text(encoding="utf-8")
            needle = "Founder posts, carousels, customer outcomes, employee amplification and targeted comments for B2B demand generation."
            self.assertIn(needle, text)
            changed = text.replace(needle, needle + " Runtime import regression marker.", 1)
            with tempfile.TemporaryDirectory() as source_td:
                changed_csv = Path(source_td) / "changed.csv"
                changed_csv.write_text(changed, encoding="utf-8")
                changed_catalogue = ChannelCatalogue.load(changed_csv)
                summary = store.import_catalogue(changed_catalogue)
            new_hash = store.conn.execute("SELECT source_hash FROM site_registry WHERE rank=1").fetchone()[0]
            self.assertEqual(summary.changed_channels, 1)
            self.assertEqual(summary.changed_action_risks, 0)
            self.assertNotEqual(old_hash, new_hash)
            self.assertEqual(store.table_count("site_registry"), 1000)
            self.assertEqual(store.table_count("channel_action_risk"), 8000)
        finally:
            store.close(); td.cleanup()

    def test_import_normalizes_all_3000_urls(self):
        td, path, store = self.make_store()
        try:
            store.import_catalogue(self.catalogue)
            row = store.conn.execute(
                "SELECT COUNT(*) FROM site_registry WHERE homepage_url LIKE 'https://%' AND register_submit_url LIKE 'https://%' AND login_url LIKE 'https://%'"
            ).fetchone()
            self.assertEqual(row[0], 1000)
        finally:
            store.close(); td.cleanup()

    def test_route_and_audit_is_append_only(self):
        td, path, store = self.make_store()
        try:
            store.import_catalogue(self.catalogue)
            linkedin = self.catalogue.require_unique_domain("linkedin.com")
            first, first_id = store.route_and_audit(linkedin, "post")
            second, second_id = store.route_and_audit(linkedin, "dm")
            self.assertNotEqual(first_id, second_id)
            self.assertTrue(first.should_execute)
            self.assertFalse(second.should_execute)
            self.assertEqual(store.table_count("risk_decision"), 2)
            rows = store.conn.execute("SELECT requested_action, main_risk, selected_medium, execution_mode, should_execute FROM risk_decision ORDER BY id").fetchall()
            self.assertEqual(tuple(rows[0]), ("post", "Low", "official_api", "api_auto", 1))
            self.assertEqual(tuple(rows[1]), ("dm", "Critical", "none", "auto_quarantine", 0))
            with self.assertRaisesRegex(sqlite3.IntegrityError, "append-only"):
                store.conn.execute("UPDATE risk_decision SET reason='tampered' WHERE decision_id=?", (first_id,))
            store.conn.rollback()
            with self.assertRaisesRegex(sqlite3.IntegrityError, "append-only"):
                store.conn.execute("DELETE FROM risk_decision WHERE decision_id=?", (first_id,))
            store.conn.rollback()
        finally:
            store.close(); td.cleanup()

    def test_representative_decisions_persist_expected_media(self):
        td, path, store = self.make_store()
        try:
            store.import_catalogue(self.catalogue)
            cases = [
                ("linkedin.com", "post", "Low", "official_api", 1),
                ("producthunt.com", "submit", "Moderate", "official_api", 1),
                ("producthunt.com", "vote", "Critical", "none", 0),
                ("reddit.com", "comment", "Low", "official_api", 1),
                ("reddit.com", "vote", "Very High", "none", 0),
            ]
            for domain, action, risk, medium, execute in cases:
                decision, _ = store.route_and_audit(self.catalogue.require_unique_domain(domain), action)
                self.assertEqual((decision.main_risk, decision.selected_medium, int(decision.should_execute)), (risk, medium, execute))
            self.assertEqual(store.table_count("risk_decision"), len(cases))
        finally:
            store.close(); td.cleanup()


class URLValidationTests(unittest.TestCase):
    def test_normalization(self):
        self.assertEqual(normalize_http_url("HTTPS://Example.COM:443/path?q=1#frag"), "https://example.com/path?q=1")
        self.assertEqual(normalize_http_url("http://example.com"), "http://example.com/")

    def test_rejects_unsafe_or_malformed_urls(self):
        bad = [
            "file:///etc/passwd",
            "ftp://example.com/a",
            "https://user:pass@example.com/",
            "https://example.com:8443/",
            "https://exa mple.com/",
            "javascript:alert(1)",
        ]
        for url in bad:
            with self.subTest(url=url), self.assertRaises(URLValidationError):
                normalize_http_url(url)

    def test_preflight_blocks_private_targets_before_open(self):
        opener = FakeOpener(FakeResponse())
        result = preflight_url("http://127.0.0.1/", opener=opener, resolver=public_resolver)
        self.assertEqual(result.status, "blocked")
        self.assertEqual(opener.requests, [])

    def test_reachable_and_redirected_results(self):
        reachable = preflight_url(
            "HTTPS://Example.COM:443/#fragment",
            opener=FakeOpener(FakeResponse(200, "https://example.com/")),
            resolver=public_resolver,
        )
        self.assertEqual((reachable.status, reachable.http_status, reachable.final_url), ("reachable", 200, "https://example.com/"))
        self.assertEqual(reachable.requested_url, "HTTPS://Example.COM:443/#fragment")
        self.assertEqual(reachable.normalized_url, "https://example.com/")
        redirected = preflight_url(
            "https://example.com/start",
            opener=FakeOpener(FakeResponse(200, "https://www.example.org/final")),
            resolver=public_resolver,
        )
        self.assertEqual((redirected.status, redirected.http_status, redirected.final_url), ("redirected", 200, "https://www.example.org/final"))

    def test_private_redirect_target_is_blocked(self):
        result = preflight_url(
            "https://example.com/start",
            opener=FakeOpener(FakeResponse(200, "http://127.0.0.1/admin")),
            resolver=public_resolver,
        )
        self.assertEqual(result.status, "blocked")
        self.assertIn("non-public IP", result.error)

    def test_http_and_network_errors_are_classified(self):
        http_error = HTTPError("https://example.com/missing", 404, "Not Found", {}, io.BytesIO(b""))
        result = preflight_url(
            "https://example.com/missing",
            opener=FakeOpener(error=http_error),
            resolver=public_resolver,
        )
        self.assertEqual((result.status, result.http_status), ("http_error", 404))
        network = preflight_url(
            "https://example.com/",
            opener=FakeOpener(error=URLError("connection refused")),
            resolver=public_resolver,
        )
        self.assertEqual(network.status, "network_error")
        self.assertIn("connection refused", network.error)

    def test_preflight_observation_is_persisted(self):
        catalogue = ChannelCatalogue.load(CSV)
        with tempfile.TemporaryDirectory() as td:
            store = RuntimeStore.open(Path(td) / "db.sqlite3", migrations_dir=MIGRATIONS)
            try:
                store.import_catalogue(catalogue)
                channel = catalogue.require_unique_domain("linkedin.com")
                result, observation_id = store.preflight_channel_url(
                    channel,
                    "homepage",
                    opener=FakeOpener(FakeResponse(200, "https://www.linkedin.com/")),
                    resolver=public_resolver,
                )
                self.assertEqual(result.status, "reachable")
                row = store.conn.execute(
                    "SELECT observation_id, channel_rank, url_kind, status FROM url_preflight_observation"
                ).fetchone()
                self.assertEqual(tuple(row), (observation_id, 1, "homepage", "reachable"))
                with self.assertRaisesRegex(sqlite3.IntegrityError, "append-only"):
                    store.conn.execute("DELETE FROM url_preflight_observation")
                store.conn.rollback()
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
