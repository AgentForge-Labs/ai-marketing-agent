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
if CONTRACT["captcha"]["solvers"][0] != "capsolver":
    fail(f"contract solvers must start with capsolver, got {CONTRACT['captcha']['solvers']!r}")
else:
    ok("contract solvers start with capsolver")
if "capsolver" not in cap.get("solvers", {}).get("items", {}).get("enum", []):
    fail("schema captcha.solvers enum must include capsolver")
else:
    ok("schema captcha.solvers enum includes capsolver")
if cap.get("solvers", {}).get("default", [None])[0] != "capsolver":
    fail(f"schema captcha.solvers default must start with capsolver, got {cap.get('solvers', {}).get('default')!r}")
else:
    ok("schema captcha.solvers default starts with capsolver")
if "capSolver" not in cap or cap["capSolver"].get("properties", {}).get("apiKeyRef") is None:
    fail("schema must define captcha.capSolver.apiKeyRef (vault://captcha/capsolver/apiKey)")
else:
    ok("schema captcha.capSolver.apiKeyRef present")

# 4b. ensemble code: CapSolver client + order
ens = (ROOT / "src" / "ai_marketing_agent" / "captcha_ensemble.py").read_text(encoding="utf-8")
for needle, label in [
    ("_solve_with_capsolver", "ensemble CapSolver client"),
    ('order = order or ["capsolver", "2captcha", "ai_lmm", "buster"]', "ensemble default order capsolver-first"),
    ("vault://captcha/capsolver/apiKey", "ensemble capsolver vault ref"),
]:
    if needle not in ens:
        fail(f"captcha_ensemble.py missing: {label}")
    else:
        ok(f"captcha_ensemble.py: {label}")

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

# 7. Account-reuse rule must exist in contract and be referenced by identity + architecture docs
if CONTRACT.get("accountReuse", {}).get("rule") != "same-IP-or-same-profile-second-account-forbidden":
    fail("contract accountReuse.rule must be same-IP-or-same-profile-second-account-forbidden")
else:
    ok("contract accountReuse rule present")
for rel in ["docs/01-identity-strategy.md", "docs/03-automation-architecture.md"]:
    text = (ROOT / rel).read_text(encoding="utf-8")
    if "fresh profile AND a fresh IP" not in text and "fresh browser profile AND a fresh IP" not in text:
        fail(f"{rel} missing account-reuse rule (fresh profile AND fresh IP)")
    else:
        ok(f"{rel}: account-reuse rule")

if errors:
    print(f"\n{len(errors)} contract violation(s). Fix schemas/policy-contract.json or the layer above.")
    sys.exit(1)
print(f"\nContract {CONTRACT['policyContractVersion']} consistent: maxAutonomousRisk={MAX_RISK}, captcha={CONTRACT['captcha']['defaultPolicy']}.")
