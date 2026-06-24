-- Full Platform Production Hardening Migration
-- Covers: compliance screening, service state, stablecoin enhancements,
--         DDoS shield persistence, Permify integration, marketplace integration

-- ── Compliance Screening ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS compliance_screening_results (
    id SERIAL PRIMARY KEY,
    screening_type TEXT NOT NULL,
    subject_name TEXT NOT NULL,
    subject_id TEXT,
    result TEXT NOT NULL,
    risk_score REAL DEFAULT 0,
    matched_lists TEXT[],
    details JSONB,
    screened_by TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sar_reports (
    id SERIAL PRIMARY KEY,
    reference TEXT UNIQUE NOT NULL,
    agent_code TEXT NOT NULL,
    subject_name TEXT NOT NULL,
    subject_id TEXT,
    suspicious_activity TEXT NOT NULL,
    amount NUMERIC,
    currency TEXT DEFAULT 'NGN',
    narrative TEXT NOT NULL,
    supporting_tx_refs TEXT[],
    status TEXT DEFAULT 'filed',
    filed_at TIMESTAMPTZ DEFAULT NOW(),
    submitted_to_nfiu_at TIMESTAMPTZ,
    reviewed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS sanctions_list_cache (
    id SERIAL PRIMARY KEY,
    list_name TEXT NOT NULL,
    entry_name TEXT NOT NULL,
    entry_id TEXT,
    country TEXT,
    aliases TEXT[],
    list_type TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS pep_database (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    country TEXT,
    position TEXT,
    risk_level TEXT DEFAULT 'medium',
    aliases TEXT[],
    active BOOLEAN DEFAULT TRUE,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── Polyglot Service State (shared across Go/Rust/Python) ─────────────────────
CREATE TABLE IF NOT EXISTS service_state (
    key TEXT PRIMARY KEY,
    value JSONB NOT NULL,
    service TEXT NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── DDoS Shield Persistence ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ddos_ip_reputations (
    ip TEXT PRIMARY KEY,
    reputation_score REAL NOT NULL,
    total_requests BIGINT DEFAULT 0,
    blocked_requests BIGINT DEFAULT 0,
    last_seen TIMESTAMPTZ DEFAULT NOW(),
    country TEXT,
    is_tor BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS ddos_permanent_blocklist (
    ip TEXT PRIMARY KEY,
    reason TEXT NOT NULL,
    blocked_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ddos_threat_intel (
    ip TEXT PRIMARY KEY,
    threat_type TEXT NOT NULL,
    confidence REAL,
    source TEXT,
    first_seen TIMESTAMPTZ DEFAULT NOW(),
    last_seen TIMESTAMPTZ DEFAULT NOW()
);

-- ── Permify Relationship Tuples (local cache for audit) ──────────────────────
CREATE TABLE IF NOT EXISTS permify_relationship_audit (
    id SERIAL PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    relation TEXT NOT NULL,
    subject_type TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    action TEXT NOT NULL DEFAULT 'write',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── Indexes ──────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_screening_results_name ON compliance_screening_results(subject_name);
CREATE INDEX IF NOT EXISTS idx_screening_results_type ON compliance_screening_results(screening_type, created_at);
CREATE INDEX IF NOT EXISTS idx_sar_reports_ref ON sar_reports(reference);
CREATE INDEX IF NOT EXISTS idx_sar_reports_status ON sar_reports(status, filed_at);
CREATE INDEX IF NOT EXISTS idx_sanctions_entry_name ON sanctions_list_cache(entry_name);
CREATE INDEX IF NOT EXISTS idx_sanctions_list_name ON sanctions_list_cache(list_name);
CREATE INDEX IF NOT EXISTS idx_pep_name ON pep_database(name);
CREATE INDEX IF NOT EXISTS idx_service_state_service ON service_state(service);
CREATE INDEX IF NOT EXISTS idx_ddos_ip_last_seen ON ddos_ip_reputations(last_seen);
CREATE INDEX IF NOT EXISTS idx_ddos_blocklist_blocked ON ddos_permanent_blocklist(blocked_at);
CREATE INDEX IF NOT EXISTS idx_permify_audit_entity ON permify_relationship_audit(entity_type, entity_id);
