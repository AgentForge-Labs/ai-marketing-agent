"""Mail providers (stdlib only). Transports are injectable for tests.

IMAP providers expose: connect/close/fetch_recent/mark_processed.
SMTP providers expose: send.
Gmail REST uses urllib (no google libs needed).
"""
from __future__ import annotations

import base64
import email
import imaplib
import json
import smtplib
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import parsedate_to_datetime
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError

from .errors import NotSupportedError, ProviderError


@dataclass
class RawMail:
    id: str
    subject: str
    from_addr: str
    date_ts: float
    body_text: str = ""
    body_html: str = ""


def _decode_header(value: Any) -> str:
    try:
        from email.header import decode_header
        out = ""
        for part, enc in decode_header(value or ""):
            out += part.decode(enc or "utf-8", errors="ignore") if isinstance(part, bytes) else part
        return out
    except Exception:
        return str(value or "")


def parse_rfc822(raw: bytes) -> RawMail:
    msg = email.message_from_bytes(raw)
    try:
        ts = parsedate_to_datetime(msg.get("Date", "")).timestamp()
    except Exception:
        ts = time.time()
    body_text, body_html = "", ""
    if msg.is_multipart():
        for part in msg.walk():
            try:
                payload = part.get_payload(decode=True)
                if not payload:
                    continue
                text = payload.decode(part.get_content_charset() or "utf-8", errors="ignore")
            except Exception:
                continue
            if part.get_content_type() == "text/plain":
                body_text += text
            elif part.get_content_type() == "text/html":
                body_html += text
    else:
        try:
            body_text = msg.get_payload(decode=True).decode("utf-8", errors="ignore")  # type: ignore
        except Exception:
            body_text = ""
    return RawMail(id="", subject=_decode_header(msg.get("Subject", "")),
                   from_addr=_decode_header(msg.get("From", "")),
                   date_ts=ts, body_text=body_text, body_html=body_html)


class ImapProvider:
    """Generic IMAP inbox. imap_class injectable (tests use a fake)."""

    def __init__(self, host: str, port: int = 993, user: str = "", password: str = "",
                 use_ssl: bool = True, imap_class: Any = None) -> None:
        if not host or not user or password is None:
            raise ProviderError("imap host/user/password required (resolve from vault first)")
        self.host, self.port, self.user = host, port, user
        self._password = password
        self.use_ssl = use_ssl
        self._imap_class = imap_class or (imaplib.IMAP4_SSL if use_ssl else imaplib.IMAP4)
        self.conn: Any = None

    def connect(self) -> None:
        try:
            self.conn = self._imap_class(self.host, self.port)
            self.conn.login(self.user, self._password)
            self.conn.select("INBOX")
        except Exception as e:
            raise ProviderError(f"imap connect failed for {self.host}: {type(e).__name__}")

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
        try:
            if self.conn and mail_id:
                self.conn.store(mail_id.encode() if isinstance(mail_id, str) else mail_id,
                                "+FLAGS", "\\Seen")
        except Exception:
            pass

    def fetch_recent(self, since_minutes: int = 10, subject_contains: Optional[str] = None,
                     from_contains: Optional[str] = None, limit: int = 10) -> List[RawMail]:
        if not self.conn:
            self.connect()
        assert self.conn is not None
        try:
            typ, data = self.conn.search(None, "ALL")
        except Exception as e:
            raise ProviderError(f"imap search failed: {type(e).__name__}")
        if typ != "OK" or not data or not data[0]:
            return []
        cutoff = time.time() - since_minutes * 60
        out: List[RawMail] = []
        for eid in data[0].split()[-limit:][::-1]:
            try:
                typ, msg_data = self.conn.fetch(eid, "(RFC822)")
            except Exception:
                continue
            if typ != "OK" or not msg_data or not msg_data[0]:
                continue
            raw = msg_data[0][1] if isinstance(msg_data[0], tuple) else msg_data[0]
            if not isinstance(raw, (bytes, bytearray)):
                continue
            mail = parse_rfc822(bytes(raw))
            mail.id = eid.decode() if isinstance(eid, bytes) else str(eid)
            if mail.date_ts < cutoff:
                continue
            if subject_contains and subject_contains.lower() not in mail.subject.lower():
                continue
            if from_contains and from_contains.lower() not in mail.from_addr.lower():
                continue
            out.append(mail)
        return out


class SmtpProvider:
    """Generic SMTP sender. smtp_class injectable (tests use a fake)."""

    def __init__(self, host: str, port: int = 465, user: str = "", password: str = "",
                 use_tls: str = "ssl", smtp_class: Any = None) -> None:
        if not host or not user or password is None:
            raise ProviderError("smtp host/user/password required (resolve from vault first)")
        if use_tls not in ("ssl", "starttls", "none"):
            raise ProviderError(f"bad use_tls: {use_tls!r}")
        self.host, self.port, self.user = host, port, user
        self._password = password
        self.use_tls = use_tls
        self._smtp_class = smtp_class

    def _connect(self) -> Any:
        if self._smtp_class is not None:
            conn = self._smtp_class(self.host, self.port)
        elif self.use_tls == "ssl":
            conn = smtplib.SMTP_SSL(self.host, self.port, timeout=20)
        else:
            conn = smtplib.SMTP(self.host, self.port, timeout=20)
            if self.use_tls == "starttls":
                conn.starttls()
        try:
            conn.login(self.user, self._password)
        except Exception as e:
            try:
                conn.quit()
            except Exception:
                pass
            raise ProviderError(f"smtp auth failed for {self.host}: {type(e).__name__}")
        return conn

    def send(self, to: str, subject: str, body_text: str = "", body_html: str = "",
             from_addr: Optional[str] = None) -> Dict[str, str]:
        if not to or not subject:
            raise ProviderError("send needs to + subject")
        msg = EmailMessage()
        msg["From"] = from_addr or self.user
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body_text or "")
        if body_html:
            msg.add_alternative(body_html, subtype="html")
        conn = self._connect()
        try:
            conn.send_message(msg)
        except Exception as e:
            raise ProviderError(f"smtp send failed: {type(e).__name__}")
        finally:
            try:
                conn.quit()
            except Exception:
                pass
        return {"to": to, "subject": subject, "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}


class CustomProvider:
    """One account, both directions: IMAP inbox + SMTP outbox."""

    def __init__(self, *, imap_host: str, imap_port: int = 993, smtp_host: str = "",
                 smtp_port: int = 465, user: str = "", password: str = "",
                 imap_ssl: bool = True, smtp_tls: str = "ssl",
                 imap_class: Any = None, smtp_class: Any = None) -> None:
        self.inbox = ImapProvider(imap_host, imap_port, user, password, imap_ssl, imap_class)
        self.outbox = SmtpProvider(smtp_host or imap_host, smtp_port, user, password,
                                   smtp_tls, smtp_class)

    def __getattr__(self, name: str) -> Any:  # delegate connect/close/fetch/send/mark
        for part in (self.inbox, self.outbox):
            if hasattr(part, name):
                return getattr(part, name)
        raise AttributeError(name)


class MailfenceProvider(CustomProvider):
    """Mailfence: standard IMAP/SMTP (imap.mailfence.com:993, smtp.mailfence.com:465)."""

    def __init__(self, user: str, password: str, **kw: Any) -> None:
        super().__init__(imap_host="imap.mailfence.com", smtp_host="smtp.mailfence.com",
                         user=user, password=password, **kw)


class DisrootProvider(CustomProvider):
    """Disroot: standard IMAP/SMTP (disroot.org:993/465)."""

    def __init__(self, user: str, password: str, **kw: Any) -> None:
        super().__init__(imap_host="disroot.org", smtp_host="disroot.org",
                         user=user, password=password, **kw)


class ProtonBridgeProvider(CustomProvider):
    """Proton Mail ONLY via the local Proton Bridge (Proton exposes no direct IMAP).

    Run Proton Bridge on the agent host first, then point at it
    (defaults 127.0.0.1:1143 IMAP / :1025 SMTP with the bridge-generated password).
    """

    def __init__(self, user: str, password: str, bridge_host: str = "127.0.0.1",
                 imap_port: int = 1143, smtp_port: int = 1025, **kw: Any) -> None:
        super().__init__(imap_host=bridge_host, imap_port=imap_port,
                         smtp_host=bridge_host, smtp_port=smtp_port,
                         user=user, password=password,
                         imap_ssl=False, smtp_tls="starttls", **kw)


class GmailApiProvider:
    """Gmail REST API via urllib (no google libs). token_loader() -> OAuth bearer."""

    def __init__(self, token_loader: Callable[[], str],
                 http: Any = None) -> None:
        self._token_loader = token_loader
        self._http = http  # injectable (urlopen-compatible) for tests

    def _call(self, method: str, path: str, payload: Optional[dict] = None) -> dict:
        token = self._token_loader()
        if not token:
            raise ProviderError("gmail oauth token missing")
        data = json.dumps(payload).encode() if payload is not None else None
        req = urlrequest.Request(f"https://gmail.googleapis.com{path}", data=data, method=method,
                                 headers={"Authorization": f"Bearer {token}",
                                          "Content-Type": "application/json"})
        opener = self._http or urlrequest.urlopen
        try:
            with opener(req, timeout=20) as r:
                return json.loads(r.read().decode())
        except (HTTPError, URLError) as e:
            raise ProviderError(f"gmail api failed: {type(e).__name__}")

    def fetch_recent(self, since_minutes: int = 10, subject_contains: Optional[str] = None,
                     from_contains: Optional[str] = None, limit: int = 10) -> List[RawMail]:
        q = [f"newer_than:{max(1, int(since_minutes // 60) or 1)}h"]
        if subject_contains:
            q.append(f"subject:{subject_contains}")
        if from_contains:
            q.append(f"from:{from_contains}")
        listing = self._call("GET", f"/gmail/v1/users/me/messages?q={' '.join(q)}&maxResults={limit}")
        out: List[RawMail] = []
        for m in (listing.get("messages") or [])[:limit]:
            full = self._call("GET", f"/gmail/v1/users/me/messages/{m['id']}?format=full")
            headers = {h["name"].lower(): h["value"]
                       for h in (full.get("payload", {}).get("headers") or [])}
            try:
                ts = int(full.get("internalDate", "0")) / 1000.0
            except ValueError:
                ts = time.time()
            out.append(RawMail(id=m["id"], subject=headers.get("subject", ""),
                               from_addr=headers.get("from", ""), date_ts=ts))
            try:  # mark read (best-effort, never fails the fetch)
                self._call("POST", f"/gmail/v1/users/me/messages/{m['id']}/modify",
                           {"removeLabelIds": ["UNREAD"]})
            except ProviderError:
                pass
        return out

    def mark_processed(self, mail_id: str) -> None:
        try:
            self._call("POST", f"/gmail/v1/users/me/messages/{mail_id}/modify",
                       {"removeLabelIds": ["UNREAD"]})
        except ProviderError:
            pass

    def send(self, to: str, subject: str, body_text: str = "", **kw: Any) -> Dict[str, str]:
        raw = base64.urlsafe_b64encode(
            f"To: {to}\r\nSubject: {subject}\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n{body_text}".encode()
        ).decode()
        res = self._call("POST", "/gmail/v1/users/me/messages/send", {"raw": raw})
        return {"id": res.get("id", ""), "to": to}


class OutlookGraphProvider:
    """Outlook.com / Hotmail / Microsoft 365 via Microsoft Graph (OAuth2).

    Setup (one time, per account): Azure app (personal MS accounts allowed) with
    Mail.Read + Mail.Send + offline_access -> admin/user consent -> authorization
    code -> exchange_code() -> store refresh_token in vault:
      vault://mail/outlook/<acct>/client_id
      vault://mail/outlook/<acct>/refresh   (refresh_token; client_secret only for confidential apps)
    Hotmail addresses use the same Graph endpoint (provider alias 'hotmail').
    """

    TOKEN_HOST = "login.microsoftonline.com"
    GRAPH = "https://graph.microsoft.com/v1.0"

    def __init__(self, token_loader: Callable[[], str], http: Any = None) -> None:
        self._token_loader = token_loader
        self._http = http

    def _call(self, method: str, path: str, payload: Optional[dict] = None) -> Any:
        import json as _json
        token = self._token_loader()
        if not token:
            raise ProviderError("outlook oauth token missing")
        data = _json.dumps(payload).encode() if payload is not None else None
        req = urlrequest.Request(f"{self.GRAPH}{path}", data=data, method=method,
                                 headers={"Authorization": f"Bearer {token}",
                                          "Content-Type": "application/json"})
        opener = self._http or urlrequest.urlopen
        try:
            with opener(req, timeout=20) as r:
                body = r.read().decode()
                return _json.loads(body) if body else {}
        except (HTTPError, URLError) as e:
            raise ProviderError(f"outlook graph failed: {type(e).__name__}")

    def fetch_recent(self, since_minutes: int = 10, subject_contains: Optional[str] = None,
                     from_contains: Optional[str] = None, limit: int = 10) -> List[RawMail]:
        res = self._call("GET", f"/me/messages?$top={max(1, min(limit, 50))}"
                                "&$orderby=receivedDateTime desc"
                                "&$select=id,subject,from,receivedDateTime,bodyPreview")
        cutoff = time.time() - since_minutes * 60
        out: List[RawMail] = []
        for m in (res.get("value") or [])[:limit]:
            try:
                ts = parsedate_to_datetime(m.get("receivedDateTime", "")).timestamp()
            except Exception:
                ts = time.time()
            if ts < cutoff:
                continue
            subject = m.get("subject", "") or ""
            sender = ((m.get("from") or {}).get("emailAddress") or {}).get("address", "")
            if subject_contains and subject_contains.lower() not in subject.lower():
                continue
            if from_contains and from_contains.lower() not in sender.lower():
                continue
            out.append(RawMail(id=m.get("id", ""), subject=subject, from_addr=sender,
                               date_ts=ts, body_text=m.get("bodyPreview", "") or ""))
        return out

    def mark_processed(self, mail_id: str) -> None:
        try:
            self._call("PATCH", f"/me/messages/{mail_id}", {"isRead": True})
        except ProviderError:
            pass

    def send(self, to: str, subject: str, body_text: str = "", **kw: Any) -> Dict[str, str]:
        if not to or not subject:
            raise ProviderError("send needs to + subject")
        self._call("POST", "/me/sendMail", {"message": {
            "subject": subject,
            "body": {"contentType": "Text", "content": body_text or ""},
            "toRecipients": [{"emailAddress": {"address": to}}],
        }, "saveToSentItems": True})
        return {"to": to, "subject": subject,
                "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}


class TutaBridgeProvider(CustomProvider):
    """Tuta Mail ONLY via a local unofficial bridge (same pattern as Proton Bridge).

    Tuta exposes no official IMAP/SMTP/OAuth/public API (verified 2026). The
    community bridge (e.g. tutaproxy, AGPL-3.0 — NOT vendored here, run it
    yourself after auditing the code) translates local IMAP/SMTP to Tuta's
    native API with client-side E2E crypto. Defaults match tutaproxy
    (127.0.0.1:1143 IMAP / :1025 SMTP); remap ports if Proton Bridge runs too.
    Caveats: unofficial (breaks on Tuta API changes), check Tuta ToS for your
    use case, TOTP accounts need the bridge's TOTP env.
    """

    def __init__(self, user: str, password: str, bridge_host: str = "127.0.0.1",
                 imap_port: int = 1143, smtp_port: int = 1025, **kw: Any) -> None:
        super().__init__(imap_host=bridge_host, imap_port=imap_port,
                         smtp_host=bridge_host, smtp_port=smtp_port,
                         user=user, password=password,
                         imap_ssl=False, smtp_tls="none", **kw)


class TutaProvider(TutaBridgeProvider):
    """Tuta = bridge-only. Direct access raises; use the local bridge.

    Instantiating with user/password targets the local bridge (see
    TutaBridgeProvider). There is deliberately NO direct mode: Tuta offers no
    official protocol, so a bare TutaProvider() without bridge intent would
    fail confusingly — pass explicit bridge_host/ports to show intent.
    """
