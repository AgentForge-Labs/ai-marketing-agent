"""
Discovery Agent — same BrowserProvider for discovery & normal mode.

Uses BrowserProvider.launch_for_discovery() so both modes share:
  - MultiLogin → headed fallback
  - per-tenant proxy (vault://proxy/... → http://IP:PORT) or default
"""
from __future__ import annotations

from html.parser import HTMLParser
from typing import Any, Dict, List
from urllib.parse import urljoin, urlparse

from .browser import BrowserProvider


class _PageModelParser(HTMLParser):
    """Single-pass stdlib extraction: forms/inputs, links, API hints, auth hints."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.forms: List[Dict[str, Any]] = []
        self._form: Dict[str, Any] | None = None
        self.links: List[str] = []
        self.api_hints: List[str] = []
        self.auth_hints: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[tuple]) -> None:
        attrs_d = dict(attrs)
        if tag == "form":
            self._form = {"action": attrs_d.get("action", ""), "method": (attrs_d.get("method") or "get").lower(),
                          "inputs": []}
            self.forms.append(self._form)
        elif tag == "input" and self._form is not None:
            self._form["inputs"].append({"type": attrs_d.get("type", "text"), "name": attrs_d.get("name", ""),
                                         "required": "required" in attrs_d})
        elif tag in ("a", "link"):
            href = attrs_d.get("href", "")
            if href:
                self.links.append(href)
                if "/api" in href or "oauth" in href or "login" in href:
                    self.api_hints.append(href)
        elif tag == "meta" and "csrf" in (attrs_d.get("name", "") + attrs_d.get("property", "")).lower():
            self.auth_hints.append("csrf-meta")


def extract_page_model(html: str, base_url: str = "") -> Dict[str, Any]:
    """Pure-HTML page model: form count/fields, API hints, auth hints, policy hints.

    No browser needed; used by discovery pre-pass and drift comparison.
    """
    parser = _PageModelParser()
    parser.feed(html[:500_000])
    absolute_links = [urljoin(base_url, href) for href in parser.links[:200]]
    hosts = {urlparse(link).hostname or "" for link in absolute_links}
    return {
        "forms": parser.forms,
        "form_count": len(parser.forms),
        "required_inputs": sum(1 for f in parser.forms for i in f["inputs"] if i["required"]),
        "api_hints": sorted(set(parser.api_hints))[:50],
        "auth_hints": sorted(set(parser.auth_hints)),
        "same_host_links": sum(1 for h in hosts if h and h == urlparse(base_url).hostname),
        "total_links": len(absolute_links),
    }


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
        await launched.page.goto(url, wait_until="domcontentloaded")
        content = await launched.page.content()
        model = extract_page_model(content, base_url=url)
        return {
            "url": url,
            "mode": launched.mode,
            "proxy_used": bool(launched.proxy_used),
            "content_len": len(content),
            "page_model": model,
            "discovery": True,
        }
    finally:
        await provider.close(launched)
