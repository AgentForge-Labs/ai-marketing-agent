"""
Discovery Agent — same BrowserProvider for discovery & normal mode.

Uses BrowserProvider.launch_for_discovery() so both modes share:
  - MultiLogin → headed fallback
  - per-tenant proxy (vault://proxy/... → http://IP:PORT) or default
"""
from __future__ import annotations

from typing import Any, Dict

from .browser import BrowserProvider


async def discover_site(
    url: str,
    *,
    tenant_id: str | None = None,
    profile_id: str | None = None,
    proxy_ref: str | None = None,
) -> Dict[str, Any]:
    """
    Minimal discovery: open URL with BrowserProvider (discovery mode), capture sanitized form model.
    In production, this would use semantic_browser + Vision-LLM to generate adapter.json.
    """
    provider = BrowserProvider()
    launched = await provider.launch_for_discovery(tenant_id=tenant_id, profile_id=profile_id, proxy_ref=proxy_ref)
    try:
        # Simple capture: get page content and URL
        await launched.page.goto(url, wait_until="domcontentloaded")
        content = await launched.page.content()
        return {
            "url": url,
            "mode": launched.mode,
            "proxy_used": bool(launched.proxy_used),
            "content_len": len(content),
            "discovery": True,
        }
    finally:
        await provider.close(launched)
