CREATE TABLE IF NOT EXISTS site_registry (
    rank INTEGER PRIMARY KEY CHECK (rank > 0),
    site TEXT NOT NULL,
    domain TEXT NOT NULL COLLATE NOCASE,
    channel_type TEXT NOT NULL,
    homepage_url TEXT NOT NULL,
    register_submit_url TEXT NOT NULL,
    login_url TEXT NOT NULL,
    url_confidence TEXT NOT NULL DEFAULT '',
    automation_fit TEXT NOT NULL DEFAULT '',
    preferred_automation_route TEXT NOT NULL DEFAULT '',
    runtime_mode TEXT NOT NULL DEFAULT '',
    risk_reviewed_at TEXT NOT NULL DEFAULT '',
    action_risk_model TEXT NOT NULL,
    raw_json TEXT NOT NULL,
    source_hash TEXT NOT NULL,
    imported_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_site_registry_domain ON site_registry(domain);

CREATE TABLE IF NOT EXISTS channel_action_risk (
    channel_rank INTEGER NOT NULL REFERENCES site_registry(rank) ON DELETE CASCADE,
    action TEXT NOT NULL,
    main_risk TEXT NOT NULL CHECK (main_risk IN ('Low','Moderate','High','Very High','Critical','N/A')),
    best_medium TEXT NOT NULL,
    medium_risks_json TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    raw_cell TEXT NOT NULL,
    source_hash TEXT NOT NULL,
    imported_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (channel_rank, action)
);

CREATE INDEX IF NOT EXISTS idx_channel_action_risk_action ON channel_action_risk(action, main_risk);

CREATE TABLE IF NOT EXISTS risk_decision (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_id TEXT NOT NULL UNIQUE,
    channel_rank INTEGER NOT NULL REFERENCES site_registry(rank) ON DELETE RESTRICT,
    site TEXT NOT NULL,
    domain TEXT NOT NULL,
    requested_action TEXT NOT NULL,
    normalized_action TEXT NOT NULL,
    main_risk TEXT NOT NULL,
    selected_medium TEXT NOT NULL,
    execution_mode TEXT NOT NULL,
    should_execute INTEGER NOT NULL CHECK (should_execute IN (0,1)),
    reason TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    medium_risks_json TEXT NOT NULL,
    decided_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_risk_decision_channel_time ON risk_decision(channel_rank, decided_at);
CREATE INDEX IF NOT EXISTS idx_risk_decision_mode_time ON risk_decision(execution_mode, decided_at);

CREATE TRIGGER IF NOT EXISTS risk_decision_no_update
BEFORE UPDATE ON risk_decision
BEGIN
    SELECT RAISE(ABORT, 'risk_decision is append-only');
END;

CREATE TRIGGER IF NOT EXISTS risk_decision_no_delete
BEFORE DELETE ON risk_decision
BEGIN
    SELECT RAISE(ABORT, 'risk_decision is append-only');
END;

CREATE TABLE IF NOT EXISTS url_preflight_observation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    observation_id TEXT NOT NULL UNIQUE,
    channel_rank INTEGER NOT NULL REFERENCES site_registry(rank) ON DELETE RESTRICT,
    url_kind TEXT NOT NULL CHECK (url_kind IN ('homepage','register_submit','login')),
    requested_url TEXT NOT NULL,
    normalized_url TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('reachable','redirected','http_error','network_error','blocked')),
    http_status INTEGER,
    final_url TEXT NOT NULL DEFAULT '',
    error TEXT NOT NULL DEFAULT '',
    observed_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_url_preflight_channel_time ON url_preflight_observation(channel_rank, observed_at);

CREATE TRIGGER IF NOT EXISTS url_preflight_no_update
BEFORE UPDATE ON url_preflight_observation
BEGIN
    SELECT RAISE(ABORT, 'url_preflight_observation is append-only');
END;

CREATE TRIGGER IF NOT EXISTS url_preflight_no_delete
BEFORE DELETE ON url_preflight_observation
BEGIN
    SELECT RAISE(ABORT, 'url_preflight_observation is append-only');
END;
