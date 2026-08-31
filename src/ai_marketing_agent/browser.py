"""
BrowserProvider — MultiLogin → headed fallback + per-tenant proxy.

- MultiLogin varsa: Local API (http://127.0.0.1:35000) üzerinden profil başlat, dönen CDP portuna
  Playwright `chromium.connect_over_cdp` ile bağlan. Her site/hesap aynı sanal cihazdan gelir.
- MultiLogin yoksa: vanilla Playwright `chromium.launch(headless=False)` headed (kullanıcı isteği).
- Proxy: tenant başına farklı proxy. Vault referansı `vault://proxy/<tenant|residential>/uri`
  → `login:password@IP:PORT` → Playwright `proxy: {"server": "http://IP:PORT"}`.
  Tenant proxy yoksa default bağlantı (proxy yok). Hem discovery hem normal mod aynı provider'ı kullanır.
"""
from __future__ import annotations

import os
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

try:
    import requests  # type: ignore
except Exception:  # pragma: no cover
    requests = None  # type: ignore


@dataclass
class BrowserLaunchResult:
    browser: Any
    context: Any
    page: Any
    mode: str  # "multilogin_cdp" | "headed" | "headless"
    proxy_used: Optional[str] = None


def _get_multilogin_api_base() -> Optional[str]:
    # Env: MULTILOGIN_API_URL or default local API
    # Docs/03: MultiLogin Local API — her login aynı sanal cihazdan gelir
    return os.getenv("MULTILOGIN_API_URL") or os.getenv("MULTILOGIN_LOCAL_API") or "http://127.0.0.1:35000"


def _is_multilogin_available() -> bool:
    base = _get_multilogin_api_base()
    if not base or requests is None:
        return False
    try:
        # Lightweight probe — /api/v1/profile/list or /status
        r = requests.get(f"{base.rstrip('/')}/api/v1/profile/list", timeout=2)
        return r.status_code < 500
    except Exception:
        try:
            r = requests.get(f"{base.rstrip('/')}/status", timeout=2)
            return r.status_code < 500
        except Exception:
            return False


def _resolve_proxy_for_tenant(tenant_id: Optional[str], proxy_ref: Optional[str] = None) -> Optional[str]:
    """
    Tenant başına farklı proxy. Sıra:
      1) adapter.captcha.proxyRef / RunnerConfig.proxy_ref (vault://)
      2) tenant-specific env: TENANT_<ID>_PROXY or PROXY_<TENANT>
      3) global RESIDENTIAL_PROXY_URI
      4) yoksa None → default bağlantı
    Vault ref `vault://proxy/...` ise C:/.../sunucular dosyasından env'e aktarılmış olmalı (docs/05).
    """
    # 1) explicit proxy_ref from adapter
    if proxy_ref:
        # vault:// → env
        if proxy_ref.startswith("vault://"):
            key = proxy_ref.replace("vault://", "").replace("/", "_").upper()
            # e.g. vault://proxy/residential/uri → PROXY_RESIDENTIAL_URI
            val = os.getenv(key) or os.getenv(f"TENANT_{tenant_id}_{key}" if tenant_id else key)
            if val:
                return val
            # fallback: try to read from C:\...\sunucular mapping (docs/05)
            # In production, Vault decrypts; here we just return None to use default
            return None
        return proxy_ref

    if tenant_id:
        # Try tenant-specific env
        for cand in [f"TENANT_{tenant_id}_PROXY", f"PROXY_{tenant_id.upper()}", f"{tenant_id.upper()}_PROXY"]:
            v = os.getenv(cand)
            if v:
                return v
    # Global fallback
    return os.getenv("RESIDENTIAL_PROXY_URI") or os.getenv("PROXY_URL") or None


def _parse_proxy_server(proxy_uri: Optional[str]) -> Optional[Dict[str, str]]:
    if not proxy_uri:
        return None
    # Playwright expects {"server": "http://IP:PORT", "username": ..., "password": ...} or just server
    # proxy_uri format: login:password@IP:PORT or http://login:password@IP:PORT
    if "://" not in proxy_uri:
        proxy_uri = f"http://{proxy_uri}"
    return {"server": proxy_uri}


class BrowserProvider:
    """
    MultiLogin → headed fallback. Proxy per-tenant, discovery & normal mod aynı.

    Kullanım:
        provider = BrowserProvider()
        result = await provider.launch(tenant_id="acme", proxy_ref="vault://proxy/residential/uri", is_discovery=False)
        page = result.page
        # ... runner ...
        await provider.close(result)
    """

    def __init__(self, multilogin_api_base: Optional[str] = None):
        self.api_base = multilogin_api_base or _get_multilogin_api_base()

    async def launch(
        self,
        *,
        tenant_id: Optional[str] = None,
        profile_id: Optional[str] = None,
        proxy_ref: Optional[str] = None,
        is_discovery: bool = False,
        headless: Optional[bool] = None,
    ) -> BrowserLaunchResult:
        """
        is_discovery: discovery ve normal mod aynı provider'ı kullanır, sadece audit farkı.
        headless: None → auto (MultiLogin varsa headless, yoksa headed). True/False ile override.
        """
        from playwright.async_api import async_playwright  # type: ignore

        proxy_uri = _resolve_proxy_for_tenant(tenant_id, proxy_ref)
        proxy_cfg = _parse_proxy_server(proxy_uri)

        # 1) Try MultiLogin CDP
        if _is_multilogin_available() and profile_id:
            try:
                # Start profile via Local API
                if requests is not None:
                    # Example: POST /api/v1/profile/start?automation=true&pIds=profile_id
                    try:
                        resp = requests.get(f"{self.api_base.rstrip('/')}/api/v1/profile/start", params={"automation": "true", "pIds": profile_id}, timeout=10)
                        data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                        # Try to extract CDP port: data may contain wsUrl or port
                        cdp_url = data.get("wsUrl") or data.get("ws") or data.get("value", {}).get("wsUrl") if isinstance(data, dict) else None
                        if not cdp_url:
                            # Fallback: try to get debugging port via /api/v1/profile/status
                            pass
                        if cdp_url:
                            pw = await async_playwright().start()
                            browser = await pw.chromium.connect_over_cdp(cdp_url)
                            context = browser.contexts[0] if browser.contexts else await browser.new_context(proxy=proxy_cfg)  # type: ignore
                            page = await context.new_page()
                            return BrowserLaunchResult(browser=browser, context=context, page=page, mode="multilogin_cdp", proxy_used=proxy_uri)
                    except Exception:
                        pass
            except Exception:
                pass

            # Fallback within MultiLogin path: try connect_over_cdp with default port 35000
            try:
                pw = await async_playwright().start()
                # MultiLogin default CDP is often http://127.0.0.1:35000
                browser = await pw.chromium.connect_over_cdp(self.api_base.replace("http://", "ws://") + "/devtools/browser")
                context = browser.contexts[0] if browser.contexts else await browser.new_context(proxy=proxy_cfg)  # type: ignore
                page = await context.new_page()
                return BrowserLaunchResult(browser=browser, context=context, page=page, mode="multilogin_cdp", proxy_used=proxy_uri)
            except Exception:
                # Fall through to headed fallback
                pass

        # 2) Fallback: headed browser (kullanıcı isteği: multilogin yoksa headed)
        # headless = False → headed, True → headless (only if explicitly requested)
        use_headless = False if headless is None else bool(headless)
        # Discovery modunda da aynı fallback, sadece log farkı
        pw = await async_playwright().start()
        # Proxy per-tenant: her tenant farklı IP'den çıkar
        browser = await pw.chromium.launch(headless=use_headless, proxy=proxy_cfg)  # type: ignore
        context = await browser.new_context(proxy=proxy_cfg) if proxy_cfg else await browser.new_context()
        page = await context.new_page()
        mode = "headed" if not use_headless else "headless"
        return BrowserLaunchResult(browser=browser, context=context, page=page, mode=mode, proxy_used=proxy_uri)

    async def launch_for_discovery(
        self,
        *,
        tenant_id: Optional[str] = None,
        profile_id: Optional[str] = None,
        proxy_ref: Optional[str] = None,
    ) -> BrowserLaunchResult:
        """Discovery de aynı provider — sadece audit etiketi farklı."""
        return await self.launch(tenant_id=tenant_id, profile_id=profile_id, proxy_ref=proxy_ref, is_discovery=True, headless=False)

    async def close(self, result: BrowserLaunchResult) -> None:
        try:
            await result.context.close()
        except Exception:
            pass
        try:
            await result.browser.close()
        except Exception:
            pass


# Convenience helpers for runner/discovery
async def get_browser_for_tenant(
    tenant_id: Optional[str] = None,
    *,
    proxy_ref: Optional[str] = None,
    is_discovery: bool = False,
    profile_id: Optional[str] = None,
) -> BrowserLaunchResult:
    provider = BrowserProvider()
    return await provider.launch(tenant_id=tenant_id, profile_id=profile_id, proxy_ref=proxy_ref, is_discovery=is_discovery)


def get_tenant_proxy(tenant_id: str) -> Optional[str]:
    """Public helper for docs/05 mapping — proxy yoksa None → default bağlantı."""
    return _resolve_proxy_for_tenant(tenant_id)
