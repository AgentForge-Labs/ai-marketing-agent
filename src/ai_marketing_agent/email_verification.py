"""
Email verification — Gmail (Gmail API OAuth2) + custom IMAP, vault-backed.

Vault refs (C:/Users/ahmet/Downloads/DIGER/sunucular -> vault://):
  - vault://mail/gmail/oauth  -> Gmail API OAuth2 token (gmail_worker.py style) or app password
  - vault://mail/imap/host, /port, /user, /pass, /ssl

Flow (discovery & normal, per-tenant proxy aware via BrowserProvider):
  1) Poll inbox for last N minutes, filter by subjectContains/fromContains (xyz sitesi)
  2) Extract code (\\b\\d{4,8}\\b) or link (https://xyz.../verify?token=)
  3) Fill code via HumanMouse or open link in same BrowserProvider session
  4) Audit maskeli (kodun kendisi değil, var/yok + süre)

Usage:
    from ai_marketing_agent.email_verification import fetch_code, fetch_link, handle_verification
    code = await fetch_code(tenant_id="acme", mailbox_ref="vault://mail/imap/acme", subject_contains="xyz")
    await handle_verification(page, tenant_id="acme", mailbox_ref="...", code_selector="input[name=code]")
"""
from __future__ import annotations

import asyncio
import imaplib
import email
import os
import re
import time
from dataclasses import dataclass
from email.header import decode_header
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Vault resolution — same pattern as human_mouse/captcha_ensemble
import sys

for _p in [Path(__file__).resolve().parents[2] / "services", Path("services")]:
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
        # Try to resolve IMAP config from vault/env
        host = _vault_get("vault://mail/imap/host") or os.getenv("IMAP_HOST") or "imap.gmail.com"
        port = int(_vault_get("vault://mail/imap/port") or os.getenv("IMAP_PORT") or "993")
        user = _vault_get(mailbox_ref + "/user") or _vault_get("vault://mail/imap/user") or os.getenv("IMAP_USER")
        password = _vault_get(mailbox_ref + "/pass") or _vault_get("vault://mail/imap/pass") or os.getenv("IMAP_PASS")
        # Also try direct file mapping: C:/.../sunucular/mediaharvester_api_credentials.txt may contain IMAP creds
        return cls(protocol="imap", host=host, port=port, user=user, password=password)


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
        # Search since
        # Use SINCE with date, then filter by time manually
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
                    "subject": subject,
                    "from": from_addr,
                    "date": date_str,
                    "body_text": body_text,
                    "body_html": body_html,
                    "raw": msg,
                }
            )
            if len(out) >= limit:
                break
        return out


class GmailApiMailbox:
    """Gmail API via googleapiclient — vault://mail/gmail/oauth."""

    def __init__(self, token_ref: str):
        self.token_ref = token_ref

    def _service(self):
        token = _vault_get(self.token_ref) or os.getenv("GMAIL_OAUTH_TOKEN")
        if not token:
            raise RuntimeError(f"Gmail token missing for {self.token_ref} — set vault://mail/gmail/oauth")
        try:
            from googleapiclient.discovery import build  # type: ignore
            from google.oauth2.credentials import Credentials  # type: ignore

            creds = Credentials(token=token)
            return build("gmail", "v1", credentials=creds)
        except Exception as e:
            raise RuntimeError(f"Gmail API not available: {e}")

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
            out.append({"subject": subject, "from": from_addr, "body_text": body_text, "body_html": "", "raw": msg})
        return out

    def close(self):
        pass


def _get_mailbox(mailbox_ref: str):
    cfg = MailboxConfig.from_ref(mailbox_ref)
    if cfg.protocol == "gmail_api":
        return GmailApiMailbox(cfg.gmail_token_ref or mailbox_ref)
    return ImapMailbox(cfg)


async def fetch_code(
    mailbox_ref: str,
    since_minutes: int = 10,
    subject_contains: Optional[str] = None,
    from_contains: Optional[str] = None,
) -> Optional[str]:
    """Poll inbox for verification code. Discovery & normal mod aynı."""
    box = _get_mailbox(mailbox_ref)
    try:
        # Run sync IMAP in thread to avoid blocking event loop
        def _fetch():
            if hasattr(box, "connect"):
                try:
                    box.connect()  # type: ignore
                except Exception:
                    pass
            return box.fetch_recent(since_minutes=since_minutes, subject_contains=subject_contains, from_contains=from_contains, limit=10)

        mails = await asyncio.to_thread(_fetch)
        for m in mails:
            text = f"{m.get('subject','')} {m.get('body_text','')} {m.get('body_html','')}"
            code = _extract_code(text)
            if code:
                return code
        return None
    finally:
        try:
            box.close()
        except Exception:
            pass


async def fetch_link(
    mailbox_ref: str,
    since_minutes: int = 10,
    subject_contains: Optional[str] = None,
    from_contains: Optional[str] = None,
    link_pattern: Optional[str] = None,
) -> Optional[str]:
    box = _get_mailbox(mailbox_ref)
    try:

        def _fetch():
            if hasattr(box, "connect"):
                try:
                    box.connect()  # type: ignore
                except Exception:
                    pass
            return box.fetch_recent(since_minutes=since_minutes, subject_contains=subject_contains, from_contains=from_contains, limit=10)

        mails = await asyncio.to_thread(_fetch)
        for m in mails:
            text = f"{m.get('body_text','')} {m.get('body_html','')}"
            link = _extract_link(text, link_pattern)
            if link:
                return link
        return None
    finally:
        try:
            box.close()
        except Exception:
            pass


async def handle_verification(
    page: Any,
    *,
    mailbox_ref: str,
    tenant_id: Optional[str] = None,
    code_selector: Optional[str] = None,
    link_pattern: Optional[str] = None,
    subject_contains: Optional[str] = None,
    from_contains: Optional[str] = None,
    timeout_minutes: int = 5,
) -> Dict[str, Any]:
    """
    xyz sitesinden kod geldiginde inbox'u acip bulup ilgili yere yazma.
    - Kod varsa: humanMouse ile input'a yaz (code_selector required)
    - Link varsa: aynı BrowserProvider session'ında page.goto(link) ile aç
    Returns audit dict with found, type, duration.
    """
    start = time.time()
    # Try code first
    code = await fetch_code(mailbox_ref, since_minutes=timeout_minutes, subject_contains=subject_contains, from_contains=from_contains)
    if code and code_selector and page:
        try:
            # Use human mouse if available, else direct fill
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
            return {"found": True, "type": "code", "code": code[:3] + "***", "duration_s": round(time.time() - start, 1)}
        except Exception as e:
            return {"found": False, "type": "code", "error": str(e)[:200]}

    # Try link
    link = await fetch_link(mailbox_ref, since_minutes=timeout_minutes, subject_contains=subject_contains, from_contains=from_contains, link_pattern=link_pattern)
    if link and page:
        try:
            await page.goto(link, wait_until="domcontentloaded")
            return {"found": True, "type": "link", "link": link[:80], "duration_s": round(time.time() - start, 1)}
        except Exception as e:
            return {"found": False, "type": "link", "error": str(e)[:200]}

    return {"found": False, "type": "none", "duration_s": round(time.time() - start, 1)}
