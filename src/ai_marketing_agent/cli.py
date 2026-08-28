"""Small inspection CLI for deterministic channel-action routing."""

from __future__ import annotations

import argparse
import json
from .catalogue import ChannelCatalogue
from .risk_router import PlatformRiskRouter


def main() -> int:
    parser = argparse.ArgumentParser(description="Route one channel action through the canonical risk matrix")
    parser.add_argument("domain", help="canonical channel domain, e.g. linkedin.com")
    parser.add_argument("action", help="action or alias, e.g. post, dm, public_browse")
    parser.add_argument("--csv", default=None, help="override canonical CSV path")
    parser.add_argument("--max-auto-risk", default="Moderate", choices=["Low", "Moderate"])
    args = parser.parse_args()

    catalogue = ChannelCatalogue.load(args.csv) if args.csv else ChannelCatalogue.load()
    router = PlatformRiskRouter(max_autonomous_risk=args.max_auto_risk)
    try:
        channel = catalogue.require_unique_domain(args.domain)
    except KeyError as exc:
        print(json.dumps({"execution_mode": "auto_quarantine", "should_execute": False, "reason": str(exc)}, indent=2))
        return 2

    decision = router.route(channel, args.action)
    print(json.dumps(decision.to_dict(), indent=2, sort_keys=True))
    return 0 if decision.should_execute else 3


if __name__ == "__main__":
    raise SystemExit(main())
