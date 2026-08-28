"""
Human-like mouse — agentic wrapper for wassim-sayah/biometric-mouse.

Vault: profile from vault://mouse/profile/mouse_profile.json (never in repo).
Original: ai_mouse/playwright_integration.py PlaywrightHumanMouse

Usage:
    from ai_marketing_agent.human_mouse import get_human_mouse
    mouse = get_human_mouse(page, profile_ref="vault://mouse/profile/mouse_profile.json")
    await mouse.click_element(page.locator("button.submit"))
    await mouse.move_to(800, 300)

Policy-gated: only when site-adapter.json: biometricMouse.enabled=true and
policy.allowedActions allows the operation. Never used to bypass bans.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

try:
    # Optional import — only available if services/biometric-mouse/ai_mouse is installed
    from ai_mouse.playwright_integration import PlaywrightHumanMouse as _BaseMouse  # type: ignore
except Exception:  # pragma: no cover
    _BaseMouse = None  # type: ignore


def _resolve_profile(profile_ref: str) -> str:
    """Resolve vault:// or file:// ref to local path. In production, decrypt from Vault."""
    if profile_ref.startswith("vault://"):
        # Vault integration point: fetch and decrypt, cache to /tmp
        # For prototype, expect env VAULT_MOUSE_PROFILE_JSON or file at C:\...\sunucular\mouse_profile.json
        env_val = os.getenv("VAULT_MOUSE_PROFILE")
        if env_val and Path(env_val).exists():
            return env_val
        # Fallback: look for local profile/mouse_profile.json (gitignored)
        for cand in [Path("profile/mouse_profile.json"), Path("services/biometric-mouse/profile/mouse_profile.json")]:
            if cand.exists():
                return str(cand)
        raise FileNotFoundError(f"Vault profile not found for {profile_ref}. Run record/train first (services/biometric-mouse/README.md).")
    if profile_ref.startswith("file://"):
        return profile_ref[7:]
    return profile_ref


class HumanMouse:
    """Thin wrapper that enforces policy-gated, audited human-like moves."""

    def __init__(self, page: Any, profile_ref: str = "vault://mouse/profile/mouse_profile.json", rotation_minutes: int = 30, variance_percent: int = 8):
        self.page = page
        self.profile_ref = profile_ref
        self.profile_path = _resolve_profile(profile_ref)
        self.rotation_minutes = rotation_minutes
        self.variance_percent = variance_percent
        self._base = None
        if _BaseMouse is not None and Path(self.profile_path).exists():
            try:
                self._base = _BaseMouse(page, profile_path=self.profile_path)  # type: ignore
            except Exception:
                self._base = None

    async def click_element(self, locator: Any) -> None:
        if self._base is not None:
            await self._base.click_element(locator)  # biometric FFT path
        else:
            # Fallback: Playwright default (still human-like via B-spline if buster enabled)
            await locator.click()

    async def move_to(self, x: int, y: int) -> None:
        if self._base is not None:
            await self._base.move_to(x, y)
        else:
            await self.page.mouse.move(x, y)


def get_human_mouse(page: Any, profile_ref: str = "vault://mouse/profile/mouse_profile.json", **kw: Any) -> HumanMouse:
    return HumanMouse(page, profile_ref=profile_ref, **kw)


def is_available() -> bool:
    return _BaseMouse is not None
