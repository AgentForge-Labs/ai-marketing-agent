"""MailBridge — one entry for every project: ref + secrets -> provider."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from .errors import MailBridgeError
from .providers import (
    CustomProvider,
    DisrootProvider,
    GmailApiProvider,
    ImapProvider,
    MailfenceProvider,
    ProtonBridgeProvider,
    RawMail,
    SmtpProvider,
    TutaProvider,
)

Loader = Callable[[str], Optional[str]]

_CODE_RE = re.compile(r"\b\d{4,8}\b")
_LINK_RE = re.compile(r"https?://[^\s\"'<>]+")


@dataclass
class Mail:
    id: str
    subject: str
    from_addr: str
    date_ts: float
    body_text: str = ""
    body_html: str = ""


def extract_code(text: str) -> Optional[str]:
    m = _CODE_RE.search(text or "")
    return m.group(0) if m else None


def extract_link(text: str, pattern: Optional[str] = None) -> Optional[str]:
    if pattern:
        m = re.search(pattern, text or "")
        if m:
            return m.group(0)
    m = _LINK_RE.search(text or "")
    return m.group(0) if m else None


# ref: vault://mail/<provider>/<account>  (account = secret namespace suffix)
# hotmail is an alias of outlook (same Microsoft Graph endpoint).
PROVIDERS = ("gmail", "gmail_imap", "proton", "mailfence", "disroot", "custom",
             "outlook", "hotmail", "tuta")


class MailBridge:
    """Resolve one mailbox. Usage:

        bridge = MailBridge(loader)  # loader(vault_ref) -> value|None
        box = bridge.open("vault://mail/disroot/brand", {"send": True})
        mails = box.fetch_recent(since_minutes=10, subject_contains="verify")
    """

    def __init__(self, loader: Loader) -> None:
        self._loader = loader

    def _get(self, *names: str) -> Optional[str]:
        for name in names:
            val = self._loader(name)
            if val:
                return val
        return None

    def open(self, mailbox_ref: str, capabilities: Optional[Dict[str, bool]] = None) -> Any:
        parts = mailbox_ref.strip().split("/")
        # vault://mail/<provider>[/<account...>]
        try:
            i = parts.index("mail")
            provider = parts[i + 1]
            account = "/".join(parts[i + 2:]) or "default"
        except (ValueError, IndexError):
            raise MailBridgeError(f"bad mailbox ref (want vault://mail/<provider>/<account>): {mailbox_ref}")
        if provider not in PROVIDERS:
            raise MailBridgeError(f"unknown mail provider: {provider!r}")
        ns = f"vault://mail/{provider}/{account}"
        user = self._get(f"{ns}/user", f"vault://mail/{provider}/user")
        password = self._get(f"{ns}/pass", f"vault://mail/{provider}/pass",
                             f"{ns}/password", f"vault://mail/{provider}/password")

        if provider == "tuta":
            TutaProvider()  # always raises NotSupportedError
        if provider in ("outlook", "hotmail"):
            return self._open_outlook(ns)
        if provider == "gmail" and (capabilities or {}).get("api", True):
            refresh_ns = self._gmail_refresh(ns)
            if refresh_ns is not None:
                return GmailApiProvider(refresh_ns)
            token = self._get(f"{ns}/oauth", f"vault://mail/gmail/oauth")
            if token:
                return GmailApiProvider(lambda: self._get(f"{ns}/oauth", "vault://mail/gmail/oauth") or "")
            # fall through to IMAP when no oauth material is configured
        if provider in ("gmail", "gmail_imap"):
            host = self._get(f"{ns}/host", "vault://mail/imap/host") or "imap.gmail.com"
            return ImapProvider(host, int(self._get(f"{ns}/port", "vault://mail/imap/port") or 993),
                                user or "", password or "")
        if provider == "proton":
            return ProtonBridgeProvider(
                user or "", password or "",
                bridge_host=self._get(f"{ns}/host", "vault://mail/proton/host") or "127.0.0.1",
                imap_port=int(self._get(f"{ns}/imap_port", "vault://mail/proton/imap_port") or 1143),
                smtp_port=int(self._get(f"{ns}/smtp_port", "vault://mail/proton/smtp_port") or 1025))
        if provider == "mailfence":
            return MailfenceProvider(user or "", password or "")
        if provider == "disroot":
            return DisrootProvider(user or "", password or "")
        # custom: explicit host/ports required
        host = self._get(f"{ns}/imap_host", f"{ns}/host")
        if not host:
            raise MailBridgeError(f"custom provider needs {ns}/imap_host")
        return CustomProvider(
            imap_host=host, imap_port=int(self._get(f"{ns}/imap_port") or 993),
            smtp_host=self._get(f"{ns}/smtp_host") or host,
            smtp_port=int(self._get(f"{ns}/smtp_port") or 465),
            user=user or "", password=password or "")


    def _gmail_refresh(self, ns: str):
        """Cached OAuth bearer from client_id/secret + refresh_token (None = not configured)."""
        from .oauth import CachedToken

        client_id = self._get(f"{ns}/client_id", "vault://mail/gmail/client_id")
        refresh = self._get(f"{ns}/refresh", "vault://mail/gmail/refresh")
        if not client_id or not refresh:
            return None
        secret = self._get(f"{ns}/client_secret", "vault://mail/gmail/client_secret") or ""
        return CachedToken("https://oauth2.googleapis.com/token", client_id=client_id,
                           client_secret=secret, refresh_token=refresh,
                           scope="https://www.googleapis.com/auth/gmail.modify")

    def _open_outlook(self, ns: str):
        from .oauth import CachedToken
        from .providers import OutlookGraphProvider

        client_id = self._get(f"{ns}/client_id", "vault://mail/outlook/client_id")
        refresh = self._get(f"{ns}/refresh", "vault://mail/outlook/refresh")
        if not client_id or not refresh:
            # Static bearer fallback (short-lived; refresh triple preferred).
            token = self._get(f"{ns}/oauth", "vault://mail/outlook/oauth")
            if token:
                return OutlookGraphProvider(
                    lambda: self._get(f"{ns}/oauth", "vault://mail/outlook/oauth") or "")
            raise MailBridgeError(
                f"outlook needs {ns}/client_id + {ns}/refresh (or {ns}/oauth bearer)")
        secret = self._get(f"{ns}/client_secret", "vault://mail/outlook/client_secret") or ""
        authority = self._get(f"{ns}/authority", "vault://mail/outlook/authority") or "common"
        cached = CachedToken(
            f"https://login.microsoftonline.com/{authority}/oauth2/v2.0/token",
            client_id=client_id, client_secret=secret, refresh_token=refresh,
            scope="Mail.Read Mail.Send offline_access")
        return OutlookGraphProvider(cached)


def to_mail(raw: RawMail) -> Mail:
    return Mail(id=raw.id, subject=raw.subject, from_addr=raw.from_addr,
                date_ts=raw.date_ts, body_text=raw.body_text, body_html=raw.body_html)
