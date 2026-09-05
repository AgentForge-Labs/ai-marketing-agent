CREATE TABLE IF NOT EXISTS policy_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT NOT NULL COLLATE NOCASE,
    version INTEGER NOT NULL,
    source_url TEXT NOT NULL DEFAULT '',
    execution TEXT NOT NULL DEFAULT 'auto_quarantine'
        CHECK (execution IN ('browser_auto','api_auto','auto_full','auto_quarantine')),
    allowed_actions_json TEXT NOT NULL DEFAULT '[]',
    denied_actions_json TEXT NOT NULL DEFAULT '[]',
    captcha_policy TEXT NOT NULL DEFAULT 'abort_and_notify'
        CHECK (captcha_policy IN ('abort_and_notify','auto_ensemble')),
    account_rules_json TEXT NOT NULL DEFAULT '{}',
    quotas_json TEXT NOT NULL DEFAULT '{}',
    disclosure_rules_json TEXT NOT NULL DEFAULT '{}',
    crawler_hash TEXT NOT NULL DEFAULT '',
    checked_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (domain, version)
);

CREATE INDEX IF NOT EXISTS idx_policy_versions_domain ON policy_versions(domain, version);

CREATE TABLE IF NOT EXISTS policy_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    check_id TEXT NOT NULL UNIQUE,
    domain TEXT NOT NULL,
    source_url TEXT NOT NULL DEFAULT '',
    execution TEXT NOT NULL,
    result TEXT NOT NULL CHECK (result IN ('fresh','stale','contradictory','unknown')),
    crawler_hash TEXT NOT NULL DEFAULT '',
    checked_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_policy_checks_domain_time ON policy_checks(domain, checked_at);

CREATE TRIGGER IF NOT EXISTS policy_versions_no_update
BEFORE UPDATE ON policy_versions
BEGIN
    SELECT RAISE(ABORT, 'policy_versions is append-only; insert a new version instead');
END;

CREATE TRIGGER IF NOT EXISTS policy_versions_no_delete
BEFORE DELETE ON policy_versions
BEGIN
    SELECT RAISE(ABORT, 'policy_versions is append-only');
END;

CREATE TRIGGER IF NOT EXISTS policy_checks_no_update
BEFORE UPDATE ON policy_checks
BEGIN
    SELECT RAISE(ABORT, 'policy_checks is append-only');
END;

CREATE TRIGGER IF NOT EXISTS policy_checks_no_delete
BEFORE DELETE ON policy_checks
BEGIN
    SELECT RAISE(ABORT, 'policy_checks is append-only');
END;
