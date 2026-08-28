#!/usr/bin/env python3
"""Prototype runtime DB/import/audit/preflight CLI using Python stdlib only."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_marketing_agent import ChannelCatalogue, PlatformRiskRouter  # noqa: E402
from ai_marketing_agent.storage import RuntimeStore  # noqa: E402

DEFAULT_DB = ROOT / "runtime" / "ai-marketing-agent.sqlite3"
DEFAULT_CSV = ROOT / "data" / "saas_marketing_1000_channels_ranked - 1000 Channels.csv"
DEFAULT_MIGRATIONS = ROOT / "database" / "migrations"


def _store(path: str) -> RuntimeStore:
    return RuntimeStore.open(path, migrations_dir=DEFAULT_MIGRATIONS)


def _catalogue(path: str | None) -> ChannelCatalogue:
    return ChannelCatalogue.load(path or DEFAULT_CSV)


def main() -> int:
    parser = argparse.ArgumentParser(description="AI Marketing Agent prototype persistence/preflight runtime")
    parser.add_argument("--db", default=str(DEFAULT_DB))
    sub = parser.add_subparsers(dest="command", required=True)

    import_cmd = sub.add_parser("import", help="migrate DB and idempotently import canonical catalogue")
    import_cmd.add_argument("--csv", default=None)

    route_cmd = sub.add_parser("route", help="route one action and append a risk audit record")
    route_cmd.add_argument("domain")
    route_cmd.add_argument("action")
    route_cmd.add_argument("--csv", default=None)
    route_cmd.add_argument("--max-auto-risk", default="Moderate", choices=["Low", "Moderate"])

    preflight_cmd = sub.add_parser("preflight", help="read-only bounded HTTP(S) preflight for one channel URL")
    preflight_cmd.add_argument("domain")
    preflight_cmd.add_argument("url_kind", choices=["homepage", "register_submit", "login"])
    preflight_cmd.add_argument("--csv", default=None)
    preflight_cmd.add_argument("--timeout", type=float, default=5.0)

    args = parser.parse_args()
    catalogue = _catalogue(getattr(args, "csv", None))
    with _store(args.db) as store:
        summary = store.import_catalogue(catalogue)
        if args.command == "import":
            print(json.dumps(summary.to_dict(), indent=2, sort_keys=True))
            return 0

        channel = catalogue.require_unique_domain(args.domain)
        if args.command == "route":
            decision, decision_id = store.route_and_audit(
                channel,
                args.action,
                router=PlatformRiskRouter(max_autonomous_risk=args.max_auto_risk),
            )
            payload = decision.to_dict()
            payload["decision_id"] = decision_id
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0 if decision.should_execute else 3

        if args.command == "preflight":
            result, observation_id = store.preflight_channel_url(
                channel, args.url_kind, timeout=args.timeout
            )
            payload = result.to_dict()
            payload["observation_id"] = observation_id
            payload["channel_rank"] = channel.rank
            payload["domain"] = channel.domain
            payload["url_kind"] = args.url_kind
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0 if result.status in {"reachable", "redirected"} else 4

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
