#!/usr/bin/env python3
"""Zero-dependency entrypoint for inspecting canonical channel-action routing."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_marketing_agent.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
