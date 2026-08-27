"""Safe, bounded URL normalization and read-only HTTP(S) preflight primitives."""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import SplitResult, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

ALLOWED_SCHEMES = frozenset({"http", "https"})
ALLOWED_PORTS = frozenset({80, 443})
BLOCKED_HOST_SUFFIXES = (".localhost", ".local", ".internal")


class URLValidationError(ValueError):
    """Raised when a URL is not safe enough for runtime preflight."""


@dataclass(frozen=True, slots=True)
class PreflightResult:
    requested_url: str
    normalized_url: str
    status: str
    http_status: int | None
    final_url: str
    error: str
    observed_at: str

    def to_dict(self) -> dict[str, object]:
        return {
            "requested_url": self.requested_url,
            "normalized_url": self.normalized_url,
            "status": self.status,
            "http_status": self.http_status,
            "final_url": self.final_url,
            "error": self.error,
            "observed_at": self.observed_at,
        }


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _reject_control_or_space(value: str) -> None:
    if any(ord(ch) < 32 or ord(ch) == 127 or ch.isspace() for ch in value):
        raise URLValidationError("URL contains whitespace or control characters")


def _normalized_host(parts: SplitResult) -> str:
    if parts.username is not None or parts.password is not None:
        raise URLValidationError("credentials in URL are not allowed")
    host = parts.hostname
    if not host:
        raise URLValidationError("URL must contain a hostname")
    try:
        host_ascii = host.encode("idna").decode("ascii").lower().rstrip(".")
    except UnicodeError as exc:
        raise URLValidationError("hostname cannot be IDNA-normalized") from exc
    if not host_ascii:
        raise URLValidationError("URL hostname is empty")
    return host_ascii


def normalize_http_url(value: str) -> str:
    """Normalize an HTTP(S) URL without resolving or contacting the host."""

    if not isinstance(value, str) or not value.strip():
        raise URLValidationError("URL is empty")
    raw = value.strip()
    _reject_control_or_space(raw)
    parts = urlsplit(raw)
    scheme = parts.scheme.lower()
    if scheme not in ALLOWED_SCHEMES:
        raise URLValidationError(f"unsupported URL scheme: {parts.scheme!r}")
    host = _normalized_host(parts)
    try:
        port = parts.port
    except ValueError as exc:
        raise URLValidationError("URL contains an invalid port") from exc
    if port is not None and port not in ALLOWED_PORTS:
        raise URLValidationError(f"non-default network port is not allowed: {port}")
    if (scheme == "http" and port == 80) or (scheme == "https" and port == 443) or port is None:
        port_text = ""
    else:
        port_text = f":{port}"
    host_text = f"[{host}]" if ":" in host else host
    path = parts.path or "/"
    return urlunsplit((scheme, f"{host_text}{port_text}", path, parts.query, ""))


def _is_public_ip(value: str) -> bool:
    try:
        return ipaddress.ip_address(value).is_global
    except ValueError:
        return False


def assert_public_network_target(
    normalized_url: str,
    *,
    resolver: Callable[..., Iterable[tuple]] = socket.getaddrinfo,
) -> None:
    """Resolve a normalized URL and reject local/private/reserved targets."""

    parts = urlsplit(normalized_url)
    host = _normalized_host(parts)
    host_lower = host.lower()
    if host_lower == "localhost" or host_lower.endswith(BLOCKED_HOST_SUFFIXES):
        raise URLValidationError("local/internal hostname is not allowed")

    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        if not literal.is_global:
            raise URLValidationError("non-public IP target is not allowed")
        return

    port = parts.port or (443 if parts.scheme == "https" else 80)
    try:
        resolved = list(resolver(host, port, type=socket.SOCK_STREAM))
    except OSError as exc:
        raise URLValidationError(f"hostname resolution failed: {exc}") from exc
    if not resolved:
        raise URLValidationError("hostname did not resolve")

    addresses: set[str] = set()
    for item in resolved:
        try:
            address = item[4][0]
        except (IndexError, TypeError):
            raise URLValidationError("resolver returned malformed address data") from None
        addresses.add(address)
    blocked = sorted(address for address in addresses if not _is_public_ip(address))
    if blocked:
        raise URLValidationError(f"hostname resolves to non-public address: {blocked[0]}")


class PublicOnlyRedirectHandler(HTTPRedirectHandler):
    """Validate every redirect target before urllib follows it."""

    def __init__(self, resolver: Callable[..., Iterable[tuple]]) -> None:
        super().__init__()
        self.resolver = resolver

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        normalized = normalize_http_url(newurl)
        assert_public_network_target(normalized, resolver=self.resolver)
        return super().redirect_request(req, fp, code, msg, headers, normalized)


def _result(
    requested: str,
    normalized: str,
    status: str,
    *,
    http_status: int | None = None,
    final_url: str = "",
    error: str = "",
) -> PreflightResult:
    return PreflightResult(
        requested_url=requested,
        normalized_url=normalized,
        status=status,
        http_status=http_status,
        final_url=final_url,
        error=error,
        observed_at=utc_now(),
    )


def preflight_url(
    url: str,
    *,
    timeout: float = 5.0,
    resolver: Callable[..., Iterable[tuple]] = socket.getaddrinfo,
    opener=None,
) -> PreflightResult:
    """Perform a bounded GET preflight with no auth, form submit, cookies, or body read."""

    requested = url
    try:
        normalized = normalize_http_url(url)
        assert_public_network_target(normalized, resolver=resolver)
    except URLValidationError as exc:
        return _result(requested, "", "blocked", error=str(exc))

    active_opener = opener or build_opener(PublicOnlyRedirectHandler(resolver))
    request = Request(
        normalized,
        method="GET",
        headers={
            "User-Agent": "AI-Marketing-Agent-Preflight/1.0",
            "Accept": "text/html,application/json;q=0.8,*/*;q=0.1",
            "Range": "bytes=0-0",
            "Cache-Control": "no-cache",
        },
    )
    try:
        response = active_opener.open(request, timeout=timeout)
        try:
            status_code = int(response.getcode())
            final_url = normalize_http_url(response.geturl())
            assert_public_network_target(final_url, resolver=resolver)
        finally:
            response.close()
        status = "redirected" if final_url != normalized else "reachable"
        return _result(requested, normalized, status, http_status=status_code, final_url=final_url)
    except HTTPError as exc:
        try:
            final_url = normalize_http_url(exc.geturl()) if exc.geturl() else normalized
            assert_public_network_target(final_url, resolver=resolver)
        except URLValidationError as validation_exc:
            return _result(requested, normalized, "blocked", error=str(validation_exc))
        finally:
            exc.close()
        return _result(
            requested,
            normalized,
            "http_error",
            http_status=int(exc.code),
            final_url=final_url,
            error=str(exc.reason),
        )
    except (URLError, TimeoutError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        return _result(requested, normalized, "network_error", error=str(reason))
    except URLValidationError as exc:
        return _result(requested, normalized, "blocked", error=str(exc))
