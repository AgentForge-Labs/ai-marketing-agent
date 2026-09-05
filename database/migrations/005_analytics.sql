CREATE TABLE IF NOT EXISTS channel_scores (
    channel_id TEXT PRIMARY KEY,
    attempts INTEGER NOT NULL DEFAULT 0,
    successes INTEGER NOT NULL DEFAULT 0,
    conversions INTEGER NOT NULL DEFAULT 0,
    total_cost REAL NOT NULL DEFAULT 0.0,
    total_value REAL NOT NULL DEFAULT 0.0,
    score REAL NOT NULL DEFAULT 0.0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversion_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id TEXT NOT NULL,
    campaign_id TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL,
    value REAL NOT NULL DEFAULT 0.0,
    occurred_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_conversion_channel ON conversion_events(channel_id, occurred_at);
