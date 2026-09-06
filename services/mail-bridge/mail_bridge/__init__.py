"""mail-bridge — reusable mail layer for all agent projects (stdlib only).

Providers: Gmail (REST API + IMAP), Proton (via local Bridge), Mailfence,
Disroot, generic custom IMAP+SMTP. Tuta offers no IMAP/SMTP/public API and is
explicitly unsupported (NotSupportedError, documented in README).

Secrets never live here: callers pass a loader mapping vault:// refs to values.
Errors never echo secrets (redacted).
"""
from .bridge import Mail, MailBridge, Mailbox, extract_code, extract_link
from .errors import MailBridgeError, NotSupportedError, ProviderError
from .oauth import CachedToken, build_authorize_url, exchange_code, refresh_access_token
from .providers import (
    CustomProvider,
    DisrootProvider,
    GmailApiProvider,
    ImapProvider,
    MailfenceProvider,
    OutlookGraphProvider,
    ProtonBridgeProvider,
    SmtpProvider,
    YandexProvider,
    TutaBridgeProvider,
    TutaProvider,
)

__all__ = [
    "Mail",
    "MailBridge",
    "Mailbox",
    "extract_code",
    "extract_link",
    "MailBridgeError",
    "NotSupportedError",
    "ProviderError",
    "CachedToken",
    "build_authorize_url",
    "exchange_code",
    "refresh_access_token",
    "CustomProvider",
    "DisrootProvider",
    "GmailApiProvider",
    "ImapProvider",
    "MailfenceProvider",
    "OutlookGraphProvider",
    "ProtonBridgeProvider",
    "SmtpProvider",
    "YandexProvider",
    "TutaBridgeProvider",
    "TutaProvider",
]
