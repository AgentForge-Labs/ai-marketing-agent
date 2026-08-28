"""
Semantic Browser — agentic wrapper for visser23/semantic-browser.

Token-efficient: live Chromium → ManagedSession → observe(mode=summary) → ~540 token room_text (vs 10k).
Original: https://github.com/visser23/semantic-browser (MIT, v1.3.2)

Vault: serviceUrl vault://semantic/browser/url (http://127.0.0.1:8765)

Usage:
    from ai_marketing_agent.semantic_browser import get_semantic_browser
    browser = get_semantic_browser(service_url="http://127.0.0.1:8765")
    obs = await browser.observe("https://example.com")
    # obs.room_text, obs.available_actions (top 25 + more), obs.blockers
    result = await browser.act(action_id)
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

try:
    from semantic_browser import ManagedSession  # type: ignore
    from semantic_browser.models import ActionRequest  # type: ignore
    _SEMANTIC_AVAILABLE = True
except Exception:  # pragma: no cover
    ManagedSession = None  # type: ignore
    ActionRequest = None  # type: ignore
    _SEMANTIC_AVAILABLE = False


def _resolve_service_url(ref: str) -> str:
    if ref.startswith("vault://"):
        return os.getenv("SEMANTIC_BROWSER_URL") or "http://127.0.0.1:8765"
    return ref


class SemanticBrowser:
    def __init__(self, service_url: str = "http://127.0.0.1:8765", mode: str = "summary", top_actions: int = 25):
        self.service_url = _resolve_service_url(service_url)
        self.mode = mode
        self.top_actions = top_actions
        self._session: Any = None
        self._runtime: Any = None

    async def launch(self, headless: bool = True) -> "SemanticBrowser":
        if not _SEMANTIC_AVAILABLE or ManagedSession is None:
            raise RuntimeError("semantic-browser not installed: pip install \"semantic-browser[managed]\" && semantic-browser install-browser")
        self._session = await ManagedSession.launch(headful=not headless)  # type: ignore
        self._runtime = self._session.runtime
        return self

    async def observe(self, url: Optional[str] = None, mode: Optional[str] = None) -> Any:
        if url and self._runtime:
            await self._runtime.navigate(url)
        if self._runtime:
            return await self._runtime.observe(mode=mode or self.mode)
        raise RuntimeError("SemanticBrowser not launched")

    async def act(self, action_id: str) -> Any:
        if not self._runtime or ActionRequest is None:
            raise RuntimeError("SemanticBrowser not launched")
        return await self._runtime.act(ActionRequest(action_id=action_id))  # type: ignore

    async def close(self) -> None:
        if self._session:
            await self._session.close()
            self._session = None
            self._runtime = None

    def is_available(self) -> bool:
        return _SEMANTIC_AVAILABLE


def get_semantic_browser(service_url: str = "vault://semantic/browser/url", **kw: Any) -> SemanticBrowser:
    return SemanticBrowser(service_url=_resolve_service_url(service_url), **kw)
