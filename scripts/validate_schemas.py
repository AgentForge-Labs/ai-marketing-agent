#!/usr/bin/env python3
"""Validate schemas/*.json parse + examples/*.json parse (+ policy-contract version pin).

Full jsonschema validation is intentionally out of scope here (no extra deps);
structural validation lives in tests/test_workspace_ci.py. Exit 1 on any failure.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    failures = 0
    adapters = ROOT / "adapters"
    extra = sorted(adapters.glob("*.json")) if adapters.exists() else []
    for path in sorted((ROOT / "schemas").glob("*.json")) + sorted((ROOT / "examples").glob("*.json")) + extra:
        try:
            json.loads(path.read_text(encoding="utf-8"))
            print(f"OK: {path.relative_to(ROOT)}")
        except Exception as e:
            print(f"FAIL: {path.relative_to(ROOT)}: {e}")
            failures += 1
    contract = json.loads((ROOT / "schemas" / "policy-contract.json").read_text(encoding="utf-8"))
    if contract.get("policyContractVersion") != "1.0.0":
        print(f"FAIL: policy-contract version pin mismatch: {contract.get('policyContractVersion')}")
        failures += 1
    else:
        print("OK: policy-contract version 1.0.0")
    if failures:
        print(f"{failures} schema file(s) invalid.")
        return 1
    print("schemas valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
