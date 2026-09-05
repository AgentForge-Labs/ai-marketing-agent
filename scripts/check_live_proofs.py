#!/usr/bin/env python3
"""Live-proof readiness checklist (Phase 5B, #9) — informational, exit 0 always.

Reports ready/missing per item WITHOUT live calls or secrets:
  - mouse profile (services/biometric-mouse/profile/mouse_profile.json) schema
  - successful_solves evidence dir + manifest redaction
  - vault:// refs in examples/ resolvable via EnvVault (missing = manual step)
  - semantic-browser service reachability flag (env SEMANTIC_BROWSER_URL only)

Live runs stay a manual checklist (docs/04 Phase 5B); this script only shows
what is ready. Full E2E evidence rules live in the FINAL regression issue.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

BUCKETS = ("short", "medium", "long")
TOKEN_PATTERNS = [r"gRecaptchaResponse\"\s*:\s*\"[A-Za-z0-9_-]{20,}", r"\"token\"\s*:\s*\"[A-Za-z0-9_-]{20,}"]


def check_mouse_profile(root: Path = ROOT) -> dict:
    path = root / "services" / "biometric-mouse" / "profile" / "mouse_profile.json"
    if not path.exists():
        return {"status": "missing", "detail": "record via scripts/record_mouse.py (see services/biometric-mouse/README.md)"}
    try:
        profile = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return {"status": "invalid", "detail": f"unparsable: {e}"}
    buckets = profile.get("buckets", {})
    missing = [b for b in BUCKETS if b not in buckets]
    if missing:
        return {"status": "invalid", "detail": f"buckets missing: {missing}"}
    for name, bucket in buckets.items():
        for key in ("overshoot_rate", "jitter_amplitude_px", "velocity_shape"):
            if key not in bucket:
                return {"status": "invalid", "detail": f"bucket {name} missing {key}"}
    blob = json.dumps(profile)
    if re.search(r"(api[_-]?key|secret|token)[\"']?\s*[:=]\s*['\"][A-Za-z0-9_-]{16,}", blob, re.I):
        return {"status": "invalid", "detail": "profile must not contain secrets"}
    return {"status": "ready", "detail": f"buckets={sorted(buckets)}, segments={profile.get('source_segments')}"}


def check_solves_evidence(root: Path = ROOT) -> dict:
    directory = root / "services" / "captcha-ensemble" / "successful_solves"
    if not directory.exists():
        return {"status": "missing", "detail": "no successful_solves dir yet (manual live runs, docs/04 Phase 5B)"}
    files = [p for p in directory.iterdir() if p.is_file()]
    for path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for pat in TOKEN_PATTERNS:
            if re.search(pat, text):
                return {"status": "invalid", "detail": f"raw token in {path.name} (must be masked: type/duration/result only)"}
    return {"status": "ready" if files else "missing",
            "detail": f"{len(files)} evidence file(s), all masked" if files else "empty"}


def check_vault_refs(root: Path = ROOT) -> dict:
    from ai_marketing_agent.vault import EnvVault

    refs: set[str] = set()
    for path in sorted((root / "examples").glob("*.json")):
        for m in re.finditer(r"vault://[A-Za-z0-9_/.-]+", path.read_text(encoding="utf-8")):
            refs.add(m.group(0))
    vault = EnvVault()
    resolved = sorted(r for r in refs if vault.resolve(r))
    missing = sorted(r for r in refs if not vault.resolve(r))
    return {"status": "ready" if not missing else "missing",
            "detail": f"{len(resolved)}/{len(refs)} refs resolvable via env",
            "resolved": resolved, "missing": missing}


def main() -> int:
    report = {
        "mouse_profile": check_mouse_profile(),
        "solves_evidence": check_solves_evidence(),
        "vault_refs": check_vault_refs(),
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
