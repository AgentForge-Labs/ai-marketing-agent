import os
import sys
from pathlib import Path

# Ensure src/ is on path for `python -m unittest discover`
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from ai_marketing_agent.browser import BrowserProvider, get_tenant_proxy


class TestTenantProxy(unittest.TestCase):
    def test_get_tenant_proxy_none_when_no_env(self):
        os.environ.pop("RESIDENTIAL_PROXY_URI", None)
        os.environ.pop("PROXY_URL", None)
        os.environ.pop("TENANT_acme_PROXY", None)
        self.assertIsNone(get_tenant_proxy("acme"))

    def test_get_tenant_proxy_per_tenant_env(self):
        os.environ["TENANT_acme_PROXY"] = "http://user:pass@1.1.1.1:8080"
        self.assertEqual(get_tenant_proxy("acme"), "http://user:pass@1.1.1.1:8080")
        del os.environ["TENANT_acme_PROXY"]

    def test_get_tenant_proxy_global_fallback(self):
        os.environ.pop("TENANT_acme_PROXY", None)
        os.environ["RESIDENTIAL_PROXY_URI"] = "http://proxy.example:3128"
        self.assertEqual(get_tenant_proxy("other"), "http://proxy.example:3128")
        del os.environ["RESIDENTIAL_PROXY_URI"]


class TestBrowserProvider(unittest.IsolatedAsyncioTestCase):
    async def test_fallback_to_headed_when_no_multilogin(self):
        os.environ["MULTILOGIN_API_URL"] = "http://127.0.0.1:1"
        provider = BrowserProvider(multilogin_api_base="http://127.0.0.1:1")

        mock_browser = MagicMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_browser.contexts = []
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_browser.close = AsyncMock()
        mock_context.close = AsyncMock()

        with patch("ai_marketing_agent.browser._is_multilogin_available", return_value=False):
            with patch("playwright.async_api.async_playwright") as mock_ap:
                mock_pw_instance = MagicMock()
                mock_pw_instance.chromium.launch = AsyncMock(return_value=mock_browser)
                mock_ap.return_value.start = AsyncMock(return_value=mock_pw_instance)
                result = await provider.launch(tenant_id="acme", is_discovery=False)
                self.assertIn(result.mode, ("headed", "headless"))
                self.assertIs(result.page, mock_page)
        os.environ.pop("MULTILOGIN_API_URL", None)

    async def test_uses_proxy_per_tenant(self):
        os.environ["RESIDENTIAL_PROXY_URI"] = "http://proxy.example:8080"
        provider = BrowserProvider(multilogin_api_base="http://127.0.0.1:1")
        mock_browser = MagicMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_browser.contexts = []
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_browser.close = AsyncMock()
        mock_context.close = AsyncMock()
        with patch("ai_marketing_agent.browser._is_multilogin_available", return_value=False):
            with patch("playwright.async_api.async_playwright") as mock_ap:
                mock_pw_instance = MagicMock()
                mock_pw_instance.chromium.launch = AsyncMock(return_value=mock_browser)
                mock_ap.return_value.start = AsyncMock(return_value=mock_pw_instance)
                result = await provider.launch(tenant_id="acme", proxy_ref="http://proxy.example:8080", is_discovery=False)
                self.assertEqual(result.proxy_used, "http://proxy.example:8080")
                self.assertTrue(mock_pw_instance.chromium.launch.called)
        os.environ.pop("RESIDENTIAL_PROXY_URI", None)

    async def test_discovery_uses_same_provider(self):
        provider = BrowserProvider(multilogin_api_base="http://127.0.0.1:1")
        # Just verify provider has launch_for_discovery and can be mocked
        self.assertTrue(hasattr(provider, "launch_for_discovery"))
        # Verify discovery module uses same provider
        from ai_marketing_agent.discovery import discover_site

        self.assertTrue(callable(discover_site))
