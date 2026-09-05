#!/usr/bin/env python3
"""Fail-closed secret scan for tracked text files (stdlib only).

Flags high-confidence live secrets; vault:// references and *.example
placeholders are explicitly allowed. Exit 1 on any hit.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PATTERNS = [
    (r"ghp_[A-Za-z0-9]{10,}", "github PAT"),
    (r"github_pat_[A-Za-z0-9_]{10,}", "fine-grained PAT"),
    (r"sk-live-[A-Za-z0-9]{10,}", "live secret key"),
    (r"xox[bap]-[A-Za-z0-9-]{10,}", "slack token"),
    (r"-----BEGIN (RSA )?PRIVATE KEY-----", "private key"),
    (r"AKIA[0-9A-Z]{16}", "aws access key"),
]

SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", "node_modules", ".venv", "venv"}
SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".xpi", ".pdf", ".xlsx", ".sqlite3", ".db"}
# Placeholder/example files may contain key-shaped samples.
SKIP_FILES = {"requirements.txt", "requirements.lock", ".env.example"}


def main() -> int:
    hits = 0
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in SKIP_SUFFIXES or path.name in SKIP_FILES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        rel = path.relative_to(ROOT).as_posix()
        for pat, label in PATTERNS:
            if re.search(pat, text):
                print(f"HIT [{label}] {rel}")
                hits += 1
    if hits:
        print(f"{hits} possible live secret(s). Use vault:// refs (docs/05-vault-credentials-mapping.md).")
        return 1
    print("secret scan clean.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
