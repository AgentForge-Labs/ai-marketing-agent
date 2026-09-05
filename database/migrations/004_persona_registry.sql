CREATE TABLE IF NOT EXISTS personas (
    persona_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL DEFAULT '',
    brand_id TEXT NOT NULL DEFAULT '',
    display_name TEXT NOT NULL DEFAULT '',
    handle_strategy TEXT NOT NULL DEFAULT '',
    locale TEXT NOT NULL DEFAULT '',
    timezone TEXT NOT NULL DEFAULT 'UTC',
    voice_profile_json TEXT NOT NULL DEFAULT '{}',
    topics_json TEXT NOT NULL DEFAULT '[]',
    disclosure_profile_json TEXT NOT NULL DEFAULT '{}',
    allowed_channel_classes_json TEXT NOT NULL DEFAULT '[]',
    account_refs_json TEXT NOT NULL DEFAULT '[]',
    session_policy TEXT NOT NULL DEFAULT '',
    content_history_ref TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','suspended','dead')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_personas_tenant ON personas(tenant_id, status);

CREATE TABLE IF NOT EXISTS accounts (
    account_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL DEFAULT '',
    site_id TEXT NOT NULL,
    persona_id TEXT REFERENCES personas(persona_id) ON DELETE SET NULL,
    credential_ref TEXT NOT NULL DEFAULT '',
    session_ref TEXT NOT NULL DEFAULT '',
    totp_ref TEXT NOT NULL DEFAULT '',
    ip_ref TEXT NOT NULL DEFAULT '',
    profile_ref TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','suspended','dead','quarantined')),
    last_verified_at TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_accounts_site ON accounts(site_id, status);
CREATE INDEX IF NOT EXISTS idx_accounts_persona ON accounts(persona_id);

CREATE TRIGGER IF NOT EXISTS accounts_no_secret_plaintext
BEFORE INSERT ON accounts
BEGIN
    SELECT CASE
        WHEN NEW.credential_ref NOT LIKE 'vault://%' AND NEW.credential_ref <> ''
        THEN RAISE(ABORT, 'credential_ref must be a vault:// reference')
        WHEN NEW.session_ref NOT LIKE 'vault://%' AND NEW.session_ref <> ''
        THEN RAISE(ABORT, 'session_ref must be a vault:// reference')
        WHEN NEW.totp_ref NOT LIKE 'vault://%' AND NEW.totp_ref <> ''
        THEN RAISE(ABORT, 'totp_ref must be a vault:// reference')
    END;
END;
