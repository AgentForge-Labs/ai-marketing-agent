"""mail-bridge errors. Messages never contain secrets (callers must redact)."""
from __future__ import annotations


class MailBridgeError(Exception):
    """Base: misconfiguration, unreachable provider, auth failure (redacted)."""


class ProviderError(MailBridgeError):
    """The provider call itself failed (network/auth/protocol)."""


class NotSupportedError(MailBridgeError):
    """The provider cannot be automated (e.g. Tuta: no IMAP/SMTP/public API)."""
