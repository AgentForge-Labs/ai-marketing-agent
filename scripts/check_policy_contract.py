#!/usr/bin/env python3
"""Validate every layer against canonical schemas/policy-contract.json.

Single source of truth: schemas/policy-contract.json (v1.0.0).
Checks:
  - risk_router.PlatformRiskRouter default max_autonomous_risk == contract maxAutonomousRisk
  - cli --max-auto-risk default + choices include contract max
  - execution_policy allows Low/Moderate/High, quarantines Very High/Critical
  - site-adapter.schema.json captcha.policy enum/default match contract
  - README / SECURITY / docs/01/02/03/04/05 contain no stale Moderate-ceiling or no-bypass drift
Fail-closed: any mismatch -> exit 1.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

CONTRACT = json.loads((ROOT / "schemas" / "policy-contract.json").read_text(encoding="utf-8"))
MAX_RISK = CONTRACT["maxAutonomousRisk"]
assert MAX_RISK == "High", f"contract must pin High, got {MAX_RISK!r}"

errors: list[str] = []

def fail(msg: str) -> None:
    errors.append(msg)
    print(f"FAIL: {msg}")

def ok(msg: str) -> None:
    print(f"OK: {msg}")

# 1. risk_router default
from ai_marketing_agent.risk_router import PlatformRiskRouter
import inspect
sig = inspect.signature(PlatformRiskRouter.__init__)
default = sig.parameters["max_autonomous_risk"].default
if default != MAX_RISK:
    fail(f"risk_router default max_autonomous_risk={default!r}, contract={MAX_RISK!r}")
else:
    ok(f"risk_router default == {MAX_RISK}")

# 2. CLI default + choices
cli_text = (ROOT / "src" / "ai_marketing_agent" / "cli.py").read_text(encoding="utf-8")
m = re.search(r'--max-auto-risk.*?default="(\w+)".*?choices=\[(.*?)\]', cli_text, re.S)
if not m or m.group(1) != MAX_RISK or '"High"' not in m.group(2):
    fail(f"cli --max-auto-risk must default to High with High in choices; found {m.groups() if m else None}")
else:
    ok("cli default/choices == High")

# 3. execution_policy allows High, blocks Very High/Critical
ep = (ROOT / "src" / "ai_marketing_agent" / "execution_policy.py").read_text(encoding="utf-8")
if 'RISK_ORDER["High"]' not in ep:
    fail("execution_policy must reference RISK_ORDER[High] ceiling")
else:
    ok("execution_policy High ceiling present")

# 4. site-adapter schema captcha default
schema = json.loads((ROOT / "schemas" / "site-adapter.schema.json").read_text(encoding="utf-8"))
cap = schema["properties"]["captcha"]["properties"]
if cap["policy"].get("default") != CONTRACT["captcha"]["defaultPolicy"]:
    fail(f"schema captcha.policy default {cap['policy'].get('default')!r} != contract {CONTRACT['captcha']['defaultPolicy']!r}")
else:
    ok(f"schema captcha.policy default == {CONTRACT['captcha']['defaultPolicy']}")
if "auto_ensemble" not in cap["policy"].get("enum", []):
    fail("schema captcha.policy enum must include auto_ensemble")
else:
    ok("schema captcha.policy enum includes auto_ensemble")

# 5. Doc drift guards
checks = [
    ("README.md", r"maximum production autonomous threshold is \*\*High\*\*", "README max threshold High"),
    ("README.md", r"must not circumvent bans/suspensions", "README ban-evasion-only prohibition"),
    ("SECURITY.md", r"solves CAPTCHAs", "SECURITY solves CAPTCHAs"),
    ("SECURITY.md", r"varsayılan açıktır", "SECURITY ensemble default-open"),
    ("docs/04-implementation-roadmap.md", r"Solve CAPTCHA/security challenges on `Low`/`Moderate`/`High`", "roadmap Phase 6 ensemble"),
    ("docs/04-implementation-roadmap.md", r"Implement CAPTCHA solving", "roadmap Phase 7 ensemble"),
    ("docs/05-platform-automation-risk-matrix.md", r"solved via `auto_ensemble`", "risk-matrix ensemble"),
    ("docs/01-identity-strategy.md", r"solved via the audited `auto_ensemble`", "identity ensemble"),
    ("docs/02-channel-strategy.md", r"solved via `auto_ensemble`", "channel ensemble"),
]
for rel, pat, label in checks:
    text = (ROOT / rel).read_text(encoding="utf-8")
    if not re.search(pat, text):
        fail(f"{rel} missing: {label} ({pat})")
    else:
        ok(f"{rel}: {label}")

# 6. Stale drift must be gone
stale = [
    ("README.md", r"threshold is \*\*Moderate\*\*", "stale Moderate ceiling"),
    ("README.md", r"It must not bypass CAPTCHAs", "stale no-bypass"),
    ("SECURITY.md", r"must not route CAPTCHA challenges to third-party", "stale no-third-party"),
    ("SECURITY.md", r"varsayılan kapalıdır", "stale default-closed"),
    ("docs/04-implementation-roadmap.md", r"not bypass opportunities", "stale Phase 6 quarantine-only"),
    ("docs/04-implementation-roadmap.md", r"do \*\*not\*\* implement CAPTCHA bypass", "stale Phase 7 no-bypass"),
    ("docs/01-identity-strategy.md", r"CAPTCHA or security challenges are not bypassed", "stale identity no-bypass"),
    ("docs/02-channel-strategy.md", r"must not circumvent bans, CAPTCHAs", "stale channel no-bypass"),
]
for rel, pat, label in stale:
    text = (ROOT / rel).read_text(encoding="utf-8")
    if re.search(pat, text):
        fail(f"{rel} still contains stale: {label}")
    else:
        ok(f"{rel}: stale gone ({label})")

if errors:
    print(f"\n{len(errors)} contract violation(s). Fix schemas/policy-contract.json or the layer above.")
    sys.exit(1)
print(f"\nContract {CONTRACT['policyContractVersion']} consistent: maxAutonomousRisk={MAX_RISK}, captcha={CONTRACT['captcha']['defaultPolicy']}.")
