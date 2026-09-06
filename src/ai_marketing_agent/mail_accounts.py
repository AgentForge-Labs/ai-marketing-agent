"""Dashboard mail accounts (#42) — metadata in sqlite, secrets in 0600 files.

Tenants manage mailboxes from the dashboard: provider/host/user/client_id go to
sqlite (returned by the API); passwords/tokens go ONLY to
runtime/mail_secrets/<tenant>/<name>.json (0600, gitignored, never returned,
never logged) AND into process env so the existing vault loader (_vault_get)
resolves them with zero changes to the runner/email path. Server boot reloads
all secret files via load_all_secrets_into_env().
"""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
SECRETS_DIR = ROOT / "runtime" / "mail_secrets"

SECRET_KEYS = ("password", "pass", "secret", "token", "oauth", "refresh", "totp")

PROVIDER_FIELDS = {
    # non-secret metadata fields per provider (everything else treated as secret)
    "gmail": ["auth_mode"],
    "gmail_imap": ["host", "port", "user", "ssl"],
    "outlook": ["client_id", "authority"],
    "hotmail": ["client_id", "authority"],
    "yandex": ["user"],
    "proton": ["user", "host", "imap_port", "smtp_port"],
    "mailfence": ["user"],
    "disroot": ["user"],
    "custom": ["user", "imap_host", "imap_port", "smtp_host", "smtp_port", "ssl"],
    "tuta": ["user", "host", "imap_port", "smtp_port"],
}


def ensure_mail_tables(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS mail_accounts("
        "tenant_id TEXT NOT NULL, name TEXT NOT NULL, provider TEXT NOT NULL, "
        "account TEXT NOT NULL, config TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL, "
        "PRIMARY KEY (tenant_id, name))")
    conn.commit()


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _secret_path(tenant_id: str, name: str) -> Path:
    safe_t = "".join(c if (c.isalnum() or c in "-_") else "_" for c in tenant_id)[:64]
    safe_n = "".join(c if (c.isalnum() or c in "-_") else "_" for c in name)[:64]
    return SECRETS_DIR / safe_t / f"{safe_n}.json"


def ref_env(ref: str) -> str:
    """vault://a/b/c -> A_B_C env name (mirrors email_verification + bridge service)."""
    return ref.replace("vault://", "").replace("/", "_").upper()


def save_account(conn: sqlite3.Connection, tenant_id: str, *, name: str, provider: str,
                 account: str, config: Optional[Dict[str, Any]] = None,
                 secrets: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Store metadata + write-only secrets. Returns metadata (never secrets)."""
    name = (name or "").strip()
    provider = (provider or "").strip().lower()
    account = (account or "").strip()
    if not name or not provider or not account:
        raise ValueError("name, provider and account required")
    if provider not in PROVIDER_FIELDS:
        raise ValueError(f"unknown provider: {provider}")
    config = dict(config or {})
    secrets = dict(secrets or {})
    for key in list(config.keys()):
        if any(s in key.lower() for s in SECRET_KEYS):
            raise ValueError(f"secret-looking config key rejected: {key!r} (put it in secrets)")
    ns = f"vault://mail/{provider}/{account}"
    for key, val in secrets.items():
        if not val:
            raise ValueError(f"empty secret for {key!r}")
        os.environ[ref_env(f"{ns}/{key}")] = val
    if secrets:
        path = _secret_path(tenant_id, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"ref": ns, "secrets": secrets}), encoding="utf-8")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    ensure_mail_tables(conn)
    with conn:
        conn.execute(
            "INSERT INTO mail_accounts(tenant_id, name, provider, account, config, created_at)"
            " VALUES(?,?,?,?,?,?) ON CONFLICT(tenant_id, name) DO UPDATE SET provider=excluded.provider,"
            " account=excluded.account, config=excluded.config",
            (tenant_id, name, provider, account, json.dumps(config), _now()))
    configured = _configured_fields(tenant_id, name, provider, account)
    return {"name": name, "provider": provider, "account": account, "config": config,
            "secrets_configured": sorted(configured)}


def _configured_fields(tenant_id: str, name: str, provider: str, account: str) -> List[str]:
    ns = f"vault://mail/{provider}/{account}"
    path = _secret_path(tenant_id, name)
    fields = set()
    if path.exists():
        try:
            saved = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(saved, dict) and saved.get("ref") == ns:
                fields.update((saved.get("secrets") or {}).keys())
        except (OSError, ValueError):
            pass
    prefix = ref_env(ns) + "_"
    for key, val in os.environ.items():
        if key.startswith(prefix) and val:
            fields.add(key[len(prefix):].lower())
    return sorted(fields)


def list_accounts(conn: sqlite3.Connection, tenant_id: str) -> List[Dict[str, Any]]:
    ensure_mail_tables(conn)
    rows = conn.execute(
        "SELECT name, provider, account, config FROM mail_accounts WHERE tenant_id=? ORDER BY name",
        (tenant_id,)).fetchall()
    out = []
    for r in rows:
        name, provider, account = r[0], r[1], r[2]
        out.append({"name": name, "provider": provider, "account": account,
                    "config": json.loads(r[3]),
                    "secrets_configured": _configured_fields(tenant_id, name, provider, account)})
    return out


def delete_account(conn: sqlite3.Connection, tenant_id: str, name: str) -> bool:
    ensure_mail_tables(conn)
    row = conn.execute("SELECT provider, account FROM mail_accounts WHERE tenant_id=? AND name=?",
                       (tenant_id, name)).fetchone()
    if not row:
        return False
    with conn:
        conn.execute("DELETE FROM mail_accounts WHERE tenant_id=? AND name=?", (tenant_id, name))
    # Remove secrets file + scrub process env (fail-closed: stale creds never linger).
    ns = f"vault://mail/{row[0]}/{row[1]}"
    try:
        _secret_path(tenant_id, name).unlink()
    except OSError:
        pass
    prefix = ref_env(ns) + "_"
    for key in [k for k in os.environ if k.startswith(prefix)]:
        del os.environ[key]
    return True


def load_all_secrets_into_env() -> int:
    """Boot hook: reload every secrets file into process env. Returns files loaded."""
    n = 0
    if not SECRETS_DIR.exists():
        return 0
    for tenant_dir in SECRETS_DIR.iterdir():
        if not tenant_dir.is_dir():
            continue
        for path in tenant_dir.glob("*.json"):
            try:
                saved = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            ns, secrets = saved.get("ref", ""), saved.get("secrets") or {}
            if not ns.startswith("vault://") or not isinstance(secrets, dict):
                continue
            for key, val in secrets.items():
                if val:
                    os.environ.setdefault(ref_env(f"{ns}/{key}"), val)
            n += 1
    return n


def test_connection(mailbox_ref: str) -> Dict[str, Any]:
    """Connect + close only (no mail touched). Redacted result."""
    from .email_verification import _get_mailbox

    box = _get_mailbox(mailbox_ref)
    try:
        if hasattr(box, "connect"):
            box.connect()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}"}
    finally:
        try:
            if hasattr(box, "close"):
                box.close()
        except Exception:
            pass


def oauth_authorize_url(provider: str, *, client_id: str, redirect_uri: str,
                        state: str = "") -> str:
    from mail_bridge import build_authorize_url

    provider = provider.lower()
    if provider in ("outlook", "hotmail"):
        return build_authorize_url(
            "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
            client_id=client_id, redirect_uri=redirect_uri,
            scope="Mail.Read Mail.Send offline_access", state=state)
    if provider == "gmail":
        return build_authorize_url(
            "https://accounts.google.com/o/oauth2/v2/auth",
            client_id=client_id, redirect_uri=redirect_uri,
            scope="https://www.googleapis.com/auth/gmail.modify", state=state)
    raise ValueError(f"no oauth setup for provider: {provider}")


def oauth_exchange(provider: str, *, account: str, client_id: str, code: str,
                   redirect_uri: str, client_secret: str = "", http: Any = None) -> Dict[str, str]:
    """Exchange code -> tokens; refresh (+client_id) persisted via save path by caller."""
    from mail_bridge import exchange_code

    provider = provider.lower()
    if provider in ("outlook", "hotmail"):
        endpoint = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
    elif provider == "gmail":
        endpoint = "https://oauth2.googleapis.com/token"
    else:
        raise ValueError(f"no oauth setup for provider: {provider}")
    toks = exchange_code(endpoint, client_id=client_id, client_secret=client_secret,
                         code=code, redirect_uri=redirect_uri, http=http)
    if not toks.get("refresh_token"):
        raise ValueError("oauth exchange returned no refresh_token")
    return {"refresh_token": toks["refresh_token"]}  # access token never returned/stored
