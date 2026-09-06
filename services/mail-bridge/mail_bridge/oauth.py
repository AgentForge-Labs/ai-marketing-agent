"""OAuth2 helper (stdlib only) — authorize URL, code exchange, refresh grant.

Used by Gmail (refresh_token grant) and Outlook/Microsoft identity platform.
Secrets are never logged: errors carry only the token endpoint host + kind.
"""
from __future__ import annotations

import time
import urllib.parse
from typing import Any, Callable, Dict, Optional
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError

from .errors import ProviderError

import json as _json


def build_authorize_url(auth_endpoint: str, *, client_id: str, redirect_uri: str,
                        scope: str, state: str = "", extra: Optional[Dict[str, str]] = None) -> str:
    params = {"client_id": client_id, "redirect_uri": redirect_uri, "response_type": "code",
              "scope": scope, "access_type": "offline", "prompt": "consent"}
    if state:
        params["state"] = state
    params.update(extra or {})
    return f"{auth_endpoint}?{urllib.parse.urlencode(params)}"


def _post_form(url: str, fields: Dict[str, str], http: Any = None) -> dict:
    data = urllib.parse.urlencode(fields).encode()
    req = urlrequest.Request(url, data=data, method="POST",
                             headers={"Content-Type": "application/x-www-form-urlencoded"})
    opener = http or urlrequest.urlopen
    try:
        with opener(req, timeout=20) as r:
            return _json.loads(r.read().decode())
    except (HTTPError, URLError) as e:
        host = urllib.parse.urlsplit(url).hostname or "token-endpoint"
        raise ProviderError(f"oauth token call failed at {host}: {type(e).__name__}")


def exchange_code(token_endpoint: str, *, client_id: str, client_secret: str, code: str,
                  redirect_uri: str, http: Any = None) -> dict:
    """One-time setup helper: authorization code -> {access_token, refresh_token}."""
    return _post_form(token_endpoint, {
        "grant_type": "authorization_code", "client_id": client_id,
        "client_secret": client_secret, "code": code, "redirect_uri": redirect_uri,
    }, http)


def refresh_access_token(token_endpoint: str, *, client_id: str, client_secret: str = "",
                         refresh_token: str = "", scope: str = "", http: Any = None) -> dict:
    fields = {"grant_type": "refresh_token", "client_id": client_id,
              "refresh_token": refresh_token}
    if client_secret:
        fields["client_secret"] = client_secret
    if scope:
        fields["scope"] = scope
    return _post_form(token_endpoint, fields, http)


class CachedToken:
    """Callable bearer supply with refresh + expiry cache (60s clock skew)."""

    def __init__(self, token_endpoint: str, *, client_id: str, client_secret: str = "",
                 refresh_token: str = "", scope: str = "", http: Any = None,
                 now: Callable[[], float] = time.time) -> None:
        # client_secret is optional (public clients: personal Outlook, mobile/desktop).
        for name, val in [("client_id", client_id), ("refresh_token", refresh_token)]:
            if not val:
                raise ProviderError(f"oauth {name} missing (resolve from vault first)")
        self.token_endpoint = token_endpoint
        self.client_id, self.client_secret, self.refresh_token = client_id, client_secret, refresh_token
        self.scope = scope
        self._http = http
        self._now = now
        self._token = ""
        self._expires_at = 0.0

    def __call__(self) -> str:
        if self._token and self._now() < self._expires_at - 60:
            return self._token
        res = refresh_access_token(self.token_endpoint, client_id=self.client_id,
                                   client_secret=self.client_secret,
                                   refresh_token=self.refresh_token,
                                   scope=self.scope, http=self._http)
        token = res.get("access_token", "")
        if not token:
            raise ProviderError("oauth refresh returned no access_token")
        try:
            ttl = float(res.get("expires_in", 3600))
        except (TypeError, ValueError):
            ttl = 3600.0
        self._token = token
        self._expires_at = self._now() + max(ttl, 60.0)
        # Providers rotate refresh tokens (Google doesn't; Microsoft sometimes does).
        if res.get("refresh_token"):
            self.refresh_token = res["refresh_token"]
        return self._token
