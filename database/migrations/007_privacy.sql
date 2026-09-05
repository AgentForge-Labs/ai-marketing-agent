CREATE TABLE IF NOT EXISTS consents (
    tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    subject_id TEXT NOT NULL,
    purpose TEXT NOT NULL,
    granted INTEGER NOT NULL DEFAULT 1 CHECK (granted IN (0,1)),
    decided_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, subject_id, purpose)
);

CREATE INDEX IF NOT EXISTS idx_consents_decided ON consents(decided_at);
