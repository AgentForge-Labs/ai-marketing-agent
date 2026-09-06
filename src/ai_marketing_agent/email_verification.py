"""
Email verification — Gmail (Gmail API OAuth2 + refresh) + custom IMAP, vault-backed.

Vault refs (C:/Users/ahmet/Downloads/DIGER/sunucular -> vault://):
  - vault://mail/gmail/oauth          -> Gmail API OAuth2 access token
  - vault://mail/gmail/oauth/refresh  -> Gmail OAuth refresh token (+ client id/secret)
  - vault://mail/imap/host, /port, /user, /pass, /ssl (tenant overrides: <mailbox_ref>/host ...)

Flow (discovery & normal, per-tenant proxy aware via BrowserProvider):
  1) Open ONE mailbox connection, poll until deadline (real polling loop)
  2) Filter by subjectContains/fromContains, extract code or link
  3) Link opens ONLY if linkPattern matches OR host is in allowedDomains (fail-closed)
  4) Fill code via HumanMouse or open link in same BrowserProvider session
  5) mark_processed on consumed mail; redacted audit_event (never raw code/link/token)

Usage:
    from ai_marketing_agent.email_verification import fetch_code, fetch_link, handle_verification
    code = await fetch_code("vault://mail/imap/acme", subject_contains="xyz", timeout_seconds=120)
    await handle_verification(page, mailbox_ref="...", code_selector="input[name=code]",
                              allowed_domains=["xyz.com"], timeout_minutes=5)
"""
from __future__ import annotations

import asyncio
import imaplib
import email
import os
import re
import time
from dataclasses import dataclass, field
from email.header import decode_header
from email.utils import parsedate_to_datetime
from functools import partial
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlsplit

# Vault resolution — same pattern as human_mouse/captcha_ensemble
import sys

for _p in [Path(__file__).resolve().parents[2] / "services", Path("services"),
           Path(__file__).resolve().parents[2] / "services" / "mail-bridge",
           Path("services/mail-bridge")]:
    if _p.exists() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))


def _vault_get(ref: str) -> Optional[str]:
    if not ref.startswith("vault://"):
        return ref
    # Map vault://mail/... -> env
    key = ref.replace("vault://", "").replace("/", "_").upper()
    # e.g. vault://mail/gmail/oauth -> MAIL_GMAIL_OAUTH
    for cand in [key, f"TENANT_{key}", key.replace("MAIL_", "")]:
        v = os.getenv(cand)
        if v:
            return v
    # Fallback: try C:/.../sunucular file mapping (docs/05)
    # In production Vault decrypts; here we return None to use default
    return None


@dataclass
class MailboxConfig:
    protocol: str  # imap | gmail_api
    host: Optional[str] = None
    port: int = 993
    user: Optional[str] = None
    password: Optional[str] = None
    use_ssl: bool = True
    gmail_token_ref: Optional[str] = None  # vault://mail/gmail/oauth

    @classmethod
    def from_ref(cls, mailbox_ref: str) -> "MailboxConfig":
        # mailbox_ref like vault://mail/imap/acme or vault://mail/gmail/oauth
        if "gmail" in mailbox_ref.lower():
            return cls(protocol="gmail_api", gmail_token_ref=mailbox_ref)
        # Tenant-specific overrides first (<ref>/host ...), then globals.
        # Fully honored: host/port/user/pass/ssl (previously ssl was hardcoded).
        host = (
            _vault_get(mailbox_ref + "/host")
            or _vault_get("vault://mail/imap/host")
            or os.getenv("IMAP_HOST")
            or "imap.gmail.com"
        )
        port = int(
            _vault_get(mailbox_ref + "/port")
            or _vault_get("vault://mail/imap/port")
            or os.getenv("IMAP_PORT")
            or "993"
        )
        user = _vault_get(mailbox_ref + "/user") or _vault_get("vault://mail/imap/user") or os.getenv("IMAP_USER")
        password = _vault_get(mailbox_ref + "/pass") or _vault_get("vault://mail/imap/pass") or os.getenv("IMAP_PASS")
        ssl_raw = (
            _vault_get(mailbox_ref + "/ssl")
            or _vault_get("vault://mail/imap/ssl")
            or os.getenv("IMAP_SSL")
            or "true"
        )
        use_ssl = str(ssl_raw).strip().lower() not in ("0", "false", "no", "off")
        return cls(protocol="imap", host=host, port=port, user=user, password=password, use_ssl=use_ssl)


def _decode_header_value(value: str) -> str:
    try:
        parts = decode_header(value)
        out = ""
        for part, enc in parts:
            if isinstance(part, bytes):
                out += part.decode(enc or "utf-8", errors="ignore")
            else:
                out += part
        return out
    except Exception:
        return value


def _extract_code(text: str) -> Optional[str]:
    # 4-8 digit code, often in subject or body
    m = re.search(r"\b\d{4,8}\b", text)
    return m.group(0) if m else None


def _extract_link(text: str, pattern: Optional[str] = None) -> Optional[str]:
    if pattern:
        m = re.search(pattern, text)
        if m:
            return m.group(0)
    # Generic verify link
    m = re.search(r"https?://[^\s\"'<>]+verify[^\s\"'<>]*", text, re.IGNORECASE)
    if m:
        return m.group(0)
    # Fallback: any https link
    m = re.search(r"https?://[^\s\"'<>]+", text)
    return m.group(0) if m else None


def _host_allowed(url: str, allowed_domains: List[str]) -> bool:
    """Fail-closed host check: exact or subdomain match only."""
    try:
        host = (urlsplit(url).hostname or "").lower().rstrip(".")
    except Exception:
        return False
    if not host:
        return False
    for dom in allowed_domains:
        dom = (dom or "").lower().strip().lstrip(".")
        if not dom:
            continue
        if host == dom or host.endswith("." + dom):
            return True
    return False


def _is_link_acceptable(
    link: Optional[str],
    *,
    link_pattern: Optional[str] = None,
    allowed_domains: Optional[List[str]] = None,
) -> bool:
    """A link may be opened ONLY via link_pattern match or allowed_domains membership.

    Generic fallback links are never acceptable on their own (fail-closed).
    """
    if not link:
        return False
    if link_pattern and re.search(link_pattern, link):
        return True
    if allowed_domains and _host_allowed(link, allowed_domains):
        return True
    return False


class ImapMailbox:
    def __init__(self, config: MailboxConfig):
        self.config = config
        self.conn: Optional[imaplib.IMAP4_SSL] = None

    def connect(self) -> None:
        if not self.config.host or not self.config.user or not self.config.password:
            raise RuntimeError(f"IMAP config missing for {self.config.host}/{self.config.user} — set vault://mail/imap/* or IMAP_* env")
        if self.config.use_ssl:
            self.conn = imaplib.IMAP4_SSL(self.config.host, self.config.port)
        else:
            self.conn = imaplib.IMAP4(self.config.host, self.config.port)
        self.conn.login(self.config.user, self.config.password)
        self.conn.select("INBOX")

    def close(self) -> None:
        try:
            if self.conn:
                self.conn.close()
                self.conn.logout()
        except Exception:
            pass
        finally:
            self.conn = None

    def mark_processed(self, mail_id: str) -> None:
        """Mark consumed mail as seen so it is never reused. Best-effort."""
        try:
            if self.conn and mail_id:
                self.conn.store(mail_id.encode() if isinstance(mail_id, str) else mail_id, "+FLAGS", "\\Seen")
        except Exception:
            pass

    def fetch_recent(
        self,
        since_minutes: int = 10,
        subject_contains: Optional[str] = None,
        from_contains: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        if not self.conn:
            self.connect()
        assert self.conn is not None
        typ, data = self.conn.search(None, "ALL")
        if typ != "OK" or not data or not data[0]:
            return []
        ids = data[0].split()[-limit:][::-1]  # newest first
        out: List[Dict[str, Any]] = []
        cutoff = time.time() - since_minutes * 60
        for eid in ids:
            typ, msg_data = self.conn.fetch(eid, "(RFC822)")
            if typ != "OK" or not msg_data or not msg_data[0]:
                continue
            raw = msg_data[0][1] if isinstance(msg_data[0], tuple) else msg_data[0]
            if not isinstance(raw, (bytes, bytearray)):
                continue
            msg = email.message_from_bytes(raw)
            subject = _decode_header_value(msg.get("Subject", ""))
            from_addr = _decode_header_value(msg.get("From", ""))
            date_str = msg.get("Date", "")
            try:
                dt = parsedate_to_datetime(date_str)
                ts = dt.timestamp()
                if ts < cutoff:
                    continue
            except Exception:
                pass
            if subject_contains and subject_contains.lower() not in subject.lower():
                continue
            if from_contains and from_contains.lower() not in from_addr.lower():
                continue
            # Extract body
            body_text = ""
            body_html = ""
            if msg.is_multipart():
                for part in msg.walk():
                    ctype = part.get_content_type()
                    try:
                        payload = part.get_payload(decode=True)
                        if not payload:
                            continue
                        text = payload.decode(part.get_content_charset() or "utf-8", errors="ignore")
                    except Exception:
                        continue
                    if ctype == "text/plain":
                        body_text += text
                    elif ctype == "text/html":
                        body_html += text
            else:
                try:
                    payload = msg.get_payload(decode=True)
                    if payload:
                        body_text = payload.decode(msg.get_content_charset() or "utf-8", errors="ignore")
                except Exception:
                    body_text = str(msg.get_payload())

            out.append(
                {
                    "id": eid.decode() if isinstance(eid, (bytes, bytearray)) else str(eid),
                    "subject": subject,
                    "from": from_addr,
                    "date": date_str,
                    "body_text": body_text,
                    "body_html": body_html,
                }
            )
            if len(out) >= limit:
                break
        return out


class GmailApiMailbox:
    """Gmail API via googleapiclient — vault://mail/gmail/oauth (with refresh)."""

    def __init__(self, token_ref: str):
        self.token_ref = token_ref

    def _service(self):
        token = _vault_get(self.token_ref) or os.getenv("GMAIL_OAUTH_TOKEN")
        refresh_token = _vault_get(self.token_ref + "/refresh") or os.getenv("GMAIL_REFRESH_TOKEN")
        client_id = _vault_get(self.token_ref + "/client_id") or os.getenv("GMAIL_CLIENT_ID")
        client_secret = _vault_get(self.token_ref + "/client_secret") or os.getenv("GMAIL_CLIENT_SECRET")
        try:
            from googleapiclient.discovery import build  # type: ignore
            from google.oauth2.credentials import Credentials  # type: ignore
        except Exception as e:
            raise RuntimeError(f"Gmail API libraries missing (google-api-python-client, google-auth): {e}")
        # Refresh expired access tokens when refresh credentials are configured.
        if refresh_token and client_id and client_secret:
            try:
                from google.auth.transport.requests import Request  # type: ignore

                creds = Credentials(
                    token=token,
                    refresh_token=refresh_token,
                    token_uri="https://oauth2.googleapis.com/token",
                    client_id=client_id,
                    client_secret=client_secret,
                )
                if not creds.valid:
                    creds.refresh(Request())
                return build("gmail", "v1", credentials=creds)
            except Exception as e:
                raise RuntimeError(f"Gmail OAuth refresh failed: {e}")
        if not token:
            raise RuntimeError(f"Gmail token missing for {self.token_ref} — set vault://mail/gmail/oauth (+/refresh for auto-refresh)")
        return build("gmail", "v1", credentials=Credentials(token=token))

    def fetch_recent(self, since_minutes: int = 10, subject_contains: Optional[str] = None, from_contains: Optional[str] = None, limit: int = 10):
        service = self._service()
        q_parts = []
        if subject_contains:
            q_parts.append(f'subject:"{subject_contains}"')
        if from_contains:
            q_parts.append(f'from:{from_contains}')
        q_parts.append(f'newer_than:{since_minutes}m')
        q = " ".join(q_parts)
        res = service.users().messages().list(userId="me", q=q, maxResults=limit).execute()
        out = []
        for m in res.get("messages", [])[:limit]:
            msg = service.users().messages().get(userId="me", id=m["id"], format="full").execute()
            headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}
            subject = headers.get("subject", "")
            from_addr = headers.get("from", "")
            # Body
            body_text = ""
            try:
                import base64

                payload = msg.get("payload", {})
                parts = payload.get("parts", [payload])
                for p in parts:
                    data = p.get("body", {}).get("data")
                    if data:
                        body_text += base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
            except Exception:
                pass
            out.append({"id": m["id"], "subject": subject, "from": from_addr, "body_text": body_text, "body_html": ""})
        return out

    def mark_processed(self, mail_id: str) -> None:
        """Remove UNREAD label so consumed mail is never reused. Best-effort."""
        try:
            service = self._service()
            service.users().messages().modify(userId="me", id=mail_id, body={"removeLabelIds": ["UNREAD"]}).execute()
        except Exception:
            pass

    def close(self):
        pass


BRIDGE_PROVIDERS = frozenset({"mailfence", "disroot", "custom", "proton", "gmail_imap",
                               "outlook", "hotmail", "yandex", "tuta"})


def _bridge_provider_of(mailbox_ref: str) -> Optional[str]:
    parts = mailbox_ref.strip().split("/")
    try:
        i = parts.index("mail")
        provider = parts[i + 1].lower()
    except (ValueError, IndexError):
        return None
    return provider if provider in BRIDGE_PROVIDERS else None


class BridgeMailbox:
    """Vendored mail-bridge backend (#37): Gmail-IMAP/Proton/Mailfence/Disroot/custom.

    Same connect/fetch_recent/mark_processed/close surface as ImapMailbox;
    RawMail rows are adapted to the poll-loop dict shape. Tuta refs fail loudly
    (NotSupportedError) instead of silently doing nothing.
    """

    def __init__(self, mailbox_ref: str):
        self.mailbox_ref = mailbox_ref
        self._box: Any = None

    def _open(self) -> Any:
        if self._box is None:
            from mail_bridge import MailBridge
            self._box = MailBridge(_vault_get).open(self.mailbox_ref)
        return self._box

    def connect(self) -> None:
        box = self._open()
        if hasattr(box, "connect"):
            box.connect()

    def close(self) -> None:
        if self._box is not None:
            try:
                if hasattr(self._box, "close"):
                    self._box.close()
            except Exception:
                pass

    def mark_processed(self, mail_id: str) -> None:
        try:
            self._open().mark_processed(mail_id)
        except Exception:
            pass

    def fetch_recent(self, since_minutes: int = 10, subject_contains: Optional[str] = None,
                     from_contains: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for m in self._open().fetch_recent(since_minutes=since_minutes,
                                           subject_contains=subject_contains,
                                           from_contains=from_contains, limit=limit):
            out.append({
                "id": getattr(m, "id", ""),
                "subject": getattr(m, "subject", ""),
                "from": getattr(m, "from_addr", ""),
                "date": "",
                "body_text": getattr(m, "body_text", ""),
                "body_html": getattr(m, "body_html", ""),
            })
            if len(out) >= limit:
                break
        return out


def _get_mailbox(mailbox_ref: str):
    if _bridge_provider_of(mailbox_ref):
        return BridgeMailbox(mailbox_ref)
    cfg = MailboxConfig.from_ref(mailbox_ref)
    if cfg.protocol == "gmail_api":
        return GmailApiMailbox(cfg.gmail_token_ref or mailbox_ref)
    return ImapMailbox(cfg)


def _audit_event(
    *,
    event: str,
    mailbox_ref: str,
    tenant_id: Optional[str],
    idempotency_key: Optional[str],
    found: bool,
    type_: str,
    duration_s: float,
) -> Dict[str, Any]:
    """Persistent-shaped audit event. NEVER contains raw code/link/token."""
    return {
        "event": event,
        "idempotency_key": idempotency_key or f"{tenant_id or 'na'}:{mailbox_ref}:{int(time.time())}",
        "detail_json": {
            "mailbox": mailbox_ref,
            "tenant": tenant_id,
            "found": found,
            "type": type_,
            "duration_s": duration_s,
        },
    }


async def _poll_mailbox(
    box: Any,
    *,
    since_minutes: int,
    subject_contains: Optional[str],
    from_contains: Optional[str],
    deadline_s: float,
    poll_interval_s: float,
    match: Callable[[List[Dict[str, Any]]], Optional[Any]],
) -> tuple[List[Dict[str, Any]], Optional[Any]]:
    """ONE connection, repeated fetch_recent until match() hits or the real deadline.

    Returns (last_mails, hit). `timeout` here is a true deadline, not a search window.
    """
    start = time.time()
    if hasattr(box, "connect"):
        await asyncio.to_thread(box.connect)
    try:
        while True:
            mails = await asyncio.to_thread(
                partial(
                    box.fetch_recent,
                    since_minutes=since_minutes,
                    subject_contains=subject_contains,
                    from_contains=from_contains,
                    limit=10,
                )
            )
            hit = match(mails)
            if hit is not None:
                return mails, hit
            if time.time() - start >= deadline_s:
                return mails, None
            await asyncio.sleep(poll_interval_s)
    finally:
        try:
            box.close()
        except Exception:
            pass


async def fetch_code(
    mailbox_ref: str,
    since_minutes: int = 10,
    subject_contains: Optional[str] = None,
    from_contains: Optional[str] = None,
    timeout_seconds: float = 0,
    poll_interval_seconds: float = 15,
) -> Optional[str]:
    """Poll inbox for a verification code. `timeout_seconds=0` → single pass.

    The returned code is consumed by the caller (fill + mark_processed in
    handle_verification); direct callers must not log it.
    """
    box = _get_mailbox(mailbox_ref)

    def _match(mails: List[Dict[str, Any]]):
        for m in mails:
            text = f"{m.get('subject','')} {m.get('body_text','')} {m.get('body_html','')}"
            code = _extract_code(text)
            if code:
                return (m, code)
        return None

    if timeout_seconds <= 0:
        try:
            if hasattr(box, "connect"):
                await asyncio.to_thread(box.connect)
            mails = await asyncio.to_thread(
                partial(box.fetch_recent, since_minutes=since_minutes, subject_contains=subject_contains,
                        from_contains=from_contains, limit=10)
            )
            hit = _match(mails)
            return hit[1] if hit else None
        finally:
            try:
                box.close()
            except Exception:
                pass
    _, hit = await _poll_mailbox(
        box, since_minutes=since_minutes, subject_contains=subject_contains,
        from_contains=from_contains, deadline_s=timeout_seconds,
        poll_interval_s=poll_interval_seconds, match=_match,
    )
    return hit[1] if hit else None


async def fetch_link(
    mailbox_ref: str,
    since_minutes: int = 10,
    subject_contains: Optional[str] = None,
    from_contains: Optional[str] = None,
    link_pattern: Optional[str] = None,
    allowed_domains: Optional[List[str]] = None,
    timeout_seconds: float = 0,
    poll_interval_seconds: float = 15,
) -> Optional[str]:
    """Poll inbox for a verification link. A link is returned ONLY if it passes
    `_is_link_acceptable` (link_pattern match or allowed_domains membership)."""
    box = _get_mailbox(mailbox_ref)

    def _match(mails: List[Dict[str, Any]]):
        for m in mails:
            text = f"{m.get('body_text','')} {m.get('body_html','')}"
            link = _extract_link(text, link_pattern)
            if link and _is_link_acceptable(link, link_pattern=link_pattern, allowed_domains=allowed_domains):
                return (m, link)
        return None

    if timeout_seconds <= 0:
        try:
            if hasattr(box, "connect"):
                await asyncio.to_thread(box.connect)
            mails = await asyncio.to_thread(
                partial(box.fetch_recent, since_minutes=since_minutes, subject_contains=subject_contains,
                        from_contains=from_contains, limit=10)
            )
            hit = _match(mails)
            return hit[1] if hit else None
        finally:
            try:
                box.close()
            except Exception:
                pass
    _, hit = await _poll_mailbox(
        box, since_minutes=since_minutes, subject_contains=subject_contains,
        from_contains=from_contains, deadline_s=timeout_seconds,
        poll_interval_s=poll_interval_seconds, match=_match,
    )
    return hit[1] if hit else None


async def handle_verification(
    page: Any,
    *,
    mailbox_ref: str,
    tenant_id: Optional[str] = None,
    code_selector: Optional[str] = None,
    link_pattern: Optional[str] = None,
    allowed_domains: Optional[List[str]] = None,
    process_mode: str = "clickLink",
    mark_processed: bool = True,
    subject_contains: Optional[str] = None,
    from_contains: Optional[str] = None,
    timeout_minutes: int = 5,
    poll_interval_seconds: float = 15,
    idempotency_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    xyz sitesinden kod geldiginde inbox'u acip bulup ilgili yere yazma.
    - ONE mailbox connection reused across code+link attempts (no double connect).
    - Real deadline loop (`timeout_minutes`); `since_minutes` stays the search window.
    - Kod varsa: humanMouse ile input'a yaz (code_selector required).
    - Link varsa VE (link_pattern eşleşirse YA DA host allowed_domains içindeyse):
      process_mode=clickLink → aynı session'da page.goto; extractOnly → sadece bulgu.
    - Başarıyla tüketilen mail mark_processed ile işaretlenir.
    - Dönüşte ham kod/link/token ASLA yer almaz; sadece redacted audit_event.
    """
    start = time.time()
    deadline_s = max(float(timeout_minutes) * 60.0, 1.0)
    box = _get_mailbox(mailbox_ref)

    def _audit(found: bool, type_: str) -> Dict[str, Any]:
        return _audit_event(
            event="email_verified" if found else "email_verification_failed",
            mailbox_ref=mailbox_ref, tenant_id=tenant_id,
            idempotency_key=idempotency_key, found=found, type_=type_,
            duration_s=round(time.time() - start, 1),
        )

    try:
        if hasattr(box, "connect"):
            await asyncio.to_thread(box.connect)
    except Exception as e:
        return {"found": False, "type": "none", "error": str(e)[:200],
                "duration_s": round(time.time() - start, 1), "audit_event": _audit(False, "none")}

    async def _fetch():
        return await asyncio.to_thread(
            partial(box.fetch_recent, since_minutes=timeout_minutes, subject_contains=subject_contains,
                    from_contains=from_contains, limit=10)
        )

    try:
        while True:
            mails = await _fetch()
            # 1) Code path
            if code_selector and (page or process_mode == "extractOnly"):
                for m in mails:
                    text = f"{m.get('subject','')} {m.get('body_text','')} {m.get('body_html','')}"
                    code = _extract_code(text)
                    if not code:
                        continue
                    if process_mode == "extractOnly" or not page:
                        if mark_processed and m.get("id"):
                            try:
                                box.mark_processed(m["id"])
                            except Exception:
                                pass
                        return {"found": True, "type": "code",
                                "duration_s": round(time.time() - start, 1), "audit_event": _audit(True, "code")}
                    try:
                        try:
                            from .human_mouse import get_human_mouse

                            mouse = get_human_mouse(page)
                            loc = page.locator(code_selector) if hasattr(page, "locator") else None
                            if loc:
                                await mouse.click_element(loc)
                                await loc.fill(code)
                            else:
                                await page.fill(code_selector, code)
                        except Exception:
                            await page.fill(code_selector, code)
                        if mark_processed and m.get("id"):
                            try:
                                box.mark_processed(m["id"])
                            except Exception:
                                pass
                        return {"found": True, "type": "code",
                                "duration_s": round(time.time() - start, 1), "audit_event": _audit(True, "code")}
                    except Exception as e:
                        return {"found": False, "type": "code", "error": str(e)[:200],
                                "duration_s": round(time.time() - start, 1), "audit_event": _audit(False, "code")}
            # 2) Link path (fail-closed without pattern/allowlist)
            for m in mails:
                text = f"{m.get('body_text','')} {m.get('body_html','')}"
                link = _extract_link(text, link_pattern)
                if not link or not _is_link_acceptable(link, link_pattern=link_pattern, allowed_domains=allowed_domains):
                    continue
                if process_mode == "extractOnly" or not page:
                    if mark_processed and m.get("id"):
                        try:
                            box.mark_processed(m["id"])
                        except Exception:
                            pass
                    return {"found": True, "type": "link",
                            "duration_s": round(time.time() - start, 1), "audit_event": _audit(True, "link")}
                try:
                    await page.goto(link, wait_until="domcontentloaded")
                    if mark_processed and m.get("id"):
                        try:
                            box.mark_processed(m["id"])
                        except Exception:
                            pass
                    return {"found": True, "type": "link",
                            "duration_s": round(time.time() - start, 1), "audit_event": _audit(True, "link")}
                except Exception as e:
                    return {"found": False, "type": "link", "error": str(e)[:200],
                            "duration_s": round(time.time() - start, 1), "audit_event": _audit(False, "link")}
            if time.time() - start >= deadline_s:
                return {"found": False, "type": "none",
                        "duration_s": round(time.time() - start, 1), "audit_event": _audit(False, "none")}
            await asyncio.sleep(poll_interval_seconds)
    finally:
        try:
            box.close()
        except Exception:
            pass
