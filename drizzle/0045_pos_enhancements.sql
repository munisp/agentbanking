-- POS Enhancements Migration
-- Adds tables for DUKPT/HSM, P2PE, PTSP switching, AI routing,
-- self-healing, voice POS, predictive float, behavioral biometrics,
-- and operational improvements (EOD, geo-velocity, offline limits)

-- ── DUKPT/HSM Key Management ─────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS dukpt_keys (
    id SERIAL PRIMARY KEY,
    terminal_id VARCHAR(64) NOT NULL,
    key_type VARCHAR(8) NOT NULL, -- TMK, TPK, TAK
    ksn VARCHAR(40) NOT NULL,
    enc_key_block TEXT NOT NULL,
    key_version INT DEFAULT 1,
    status VARCHAR(16) DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    UNIQUE(terminal_id, key_type, ksn)
);

CREATE TABLE IF NOT EXISTS key_injection_log (
    id SERIAL PRIMARY KEY,
    terminal_id VARCHAR(64) NOT NULL,
    key_type VARCHAR(8) NOT NULL,
    action VARCHAR(32) NOT NULL,
    performed_by VARCHAR(128),
    ip_address VARCHAR(45),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS master_keys (
    id SERIAL PRIMARY KEY,
    key_id VARCHAR(64) UNIQUE NOT NULL,
    enc_value TEXT NOT NULL,
    algorithm VARCHAR(16) DEFAULT 'AES-256',
    status VARCHAR(16) DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    rotated_at TIMESTAMPTZ
);

-- ── P2PE Decryption ──────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS p2pe_decrypt_log (
    id SERIAL PRIMARY KEY,
    terminal_id VARCHAR(64) NOT NULL,
    ksn VARCHAR(40) NOT NULL,
    data_type VARCHAR(16) NOT NULL,
    card_scheme VARCHAR(16),
    masked_pan VARCHAR(19),
    success BOOLEAN NOT NULL,
    error_msg TEXT,
    latency_ms INT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS pin_translate_log (
    id SERIAL PRIMARY KEY,
    terminal_id VARCHAR(64) NOT NULL,
    ksn VARCHAR(40) NOT NULL,
    destination VARCHAR(32),
    success BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── PTSP Switch ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS switch_transactions (
    id SERIAL PRIMARY KEY,
    terminal_id VARCHAR(64) NOT NULL,
    merchant_id VARCHAR(64),
    amount_kobo BIGINT NOT NULL,
    currency VARCHAR(3) DEFAULT 'NGN',
    card_scheme VARCHAR(16),
    processing_code VARCHAR(6),
    stan VARCHAR(12),
    rrn VARCHAR(24),
    switch_used VARCHAR(32),
    response_code VARCHAR(4),
    auth_code VARCHAR(12),
    fee_kobo BIGINT DEFAULT 0,
    latency_ms INT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS switch_routes (
    id SERIAL PRIMARY KEY,
    name VARCHAR(32) UNIQUE NOT NULL,
    endpoint TEXT NOT NULL,
    success_rate DECIMAL(5,4) DEFAULT 0.95,
    avg_latency_ms INT DEFAULT 500,
    fee_rate_bps DECIMAL(6,2) DEFAULT 10.0,
    status VARCHAR(16) DEFAULT 'active',
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS switch_routing_rules (
    id SERIAL PRIMARY KEY,
    card_scheme VARCHAR(16),
    amount_min BIGINT DEFAULT 0,
    amount_max BIGINT DEFAULT 999999999,
    preferred_switch VARCHAR(32),
    fallback_switch VARCHAR(32),
    priority INT DEFAULT 1
);

-- ── AI Transaction Routing ───────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS route_performance (
    id SERIAL PRIMARY KEY,
    switch_name VARCHAR(32) NOT NULL,
    card_scheme VARCHAR(16),
    hour_of_day INT,
    success_count INT DEFAULT 0,
    failure_count INT DEFAULT 0,
    avg_latency_ms DECIMAL(8,2) DEFAULT 500,
    p95_latency_ms INT DEFAULT 1000,
    fee_rate_bps DECIMAL(6,2) DEFAULT 10,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(switch_name, card_scheme, hour_of_day)
);

CREATE TABLE IF NOT EXISTS routing_decisions (
    id SERIAL PRIMARY KEY,
    terminal_id VARCHAR(64),
    card_scheme VARCHAR(16),
    amount_kobo BIGINT,
    chosen_switch VARCHAR(32),
    score DECIMAL(6,4),
    reason TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── Self-Healing ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS self_healing_log (
    id SERIAL PRIMARY KEY,
    action_id VARCHAR(64) UNIQUE NOT NULL,
    terminal_id VARCHAR(64) NOT NULL,
    issue_detected VARCHAR(64) NOT NULL,
    severity VARCHAR(16) NOT NULL,
    action_taken VARCHAR(128) NOT NULL,
    success BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── Voice POS ────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS voice_sessions (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(64) UNIQUE NOT NULL,
    agent_id VARCHAR(64) NOT NULL,
    language VARCHAR(8) NOT NULL,
    transcript TEXT,
    intent VARCHAR(64),
    entities JSONB,
    confidence DECIMAL(4,3),
    status VARCHAR(16) DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS voice_intents (
    id SERIAL PRIMARY KEY,
    intent VARCHAR(64) NOT NULL,
    language VARCHAR(8) NOT NULL,
    patterns TEXT[] NOT NULL,
    response_template TEXT,
    requires_confirmation BOOLEAN DEFAULT true
);

-- ── Predictive Float ─────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS float_predictions (
    id SERIAL PRIMARY KEY,
    terminal_id VARCHAR(64) NOT NULL,
    prediction_date DATE NOT NULL,
    predicted_demand_kobo BIGINT NOT NULL,
    confidence DECIMAL(4,3),
    features JSONB,
    actual_demand_kobo BIGINT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(terminal_id, prediction_date)
);

CREATE TABLE IF NOT EXISTS float_alerts (
    id SERIAL PRIMARY KEY,
    terminal_id VARCHAR(64) NOT NULL,
    alert_type VARCHAR(32) NOT NULL,
    current_float_kobo BIGINT,
    predicted_demand_kobo BIGINT,
    shortfall_kobo BIGINT,
    recommended_topup_kobo BIGINT,
    status VARCHAR(16) DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS demand_history (
    id SERIAL PRIMARY KEY,
    terminal_id VARCHAR(64) NOT NULL,
    tx_date DATE NOT NULL,
    hour_of_day INT,
    day_of_week INT,
    total_cashout_kobo BIGINT DEFAULT 0,
    total_cashin_kobo BIGINT DEFAULT 0,
    tx_count INT DEFAULT 0,
    is_market_day BOOLEAN DEFAULT false,
    is_salary_period BOOLEAN DEFAULT false,
    UNIQUE(terminal_id, tx_date, hour_of_day)
);

-- ── Behavioral Biometrics ────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS agent_touch_profiles (
    id SERIAL PRIMARY KEY,
    agent_id VARCHAR(64) UNIQUE NOT NULL,
    avg_keypress_ms DECIMAL(8,2),
    std_keypress_ms DECIMAL(8,2),
    avg_pressure DECIMAL(4,3),
    std_pressure DECIMAL(4,3),
    avg_hold_time_ms DECIMAL(8,2),
    typing_rhythm_signature JSONB,
    sample_count INT DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS biometric_events (
    id SERIAL PRIMARY KEY,
    agent_id VARCHAR(64) NOT NULL,
    terminal_id VARCHAR(64) NOT NULL,
    event_type VARCHAR(32) NOT NULL,
    risk_score DECIMAL(4,3),
    features JSONB,
    decision VARCHAR(16) DEFAULT 'allow',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── EOD Reconciliation ───────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS pos_eod_reconciliation (
    id SERIAL PRIMARY KEY,
    terminal_id VARCHAR(64) NOT NULL,
    reconciliation_date DATE NOT NULL,
    total_cash_in_kobo BIGINT DEFAULT 0,
    total_cash_out_kobo BIGINT DEFAULT 0,
    total_fees_kobo BIGINT DEFAULT 0,
    tx_count INT DEFAULT 0,
    discrepancy_kobo BIGINT DEFAULT 0,
    status VARCHAR(16) DEFAULT 'pending', -- pending, balanced, discrepancy, forced
    forced_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(terminal_id, reconciliation_date)
);

-- ── Geo-Velocity Checks ─────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS pos_geo_velocity_log (
    id SERIAL PRIMARY KEY,
    terminal_id VARCHAR(64) NOT NULL,
    latitude DECIMAL(10,7),
    longitude DECIMAL(10,7),
    previous_lat DECIMAL(10,7),
    previous_lng DECIMAL(10,7),
    distance_km DECIMAL(10,3),
    time_diff_seconds INT,
    velocity_kmh DECIMAL(10,3),
    flagged BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── Offline Transaction Limits ───────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS pos_offline_limits (
    id SERIAL PRIMARY KEY,
    terminal_id VARCHAR(64) UNIQUE NOT NULL,
    max_offline_tx_count INT DEFAULT 20,
    max_offline_amount_kobo BIGINT DEFAULT 50000000, -- 500K NGN
    current_offline_count INT DEFAULT 0,
    current_offline_amount_kobo BIGINT DEFAULT 0,
    last_sync_at TIMESTAMPTZ DEFAULT NOW(),
    floor_limit_kobo BIGINT DEFAULT 500000 -- 5K per tx
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_dukpt_keys_terminal ON dukpt_keys(terminal_id, status);
CREATE INDEX IF NOT EXISTS idx_switch_tx_terminal ON switch_transactions(terminal_id, created_at);
CREATE INDEX IF NOT EXISTS idx_routing_decisions_terminal ON routing_decisions(terminal_id, created_at);
CREATE INDEX IF NOT EXISTS idx_self_healing_terminal ON self_healing_log(terminal_id, created_at);
CREATE INDEX IF NOT EXISTS idx_voice_sessions_agent ON voice_sessions(agent_id, created_at);
CREATE INDEX IF NOT EXISTS idx_float_predictions_terminal ON float_predictions(terminal_id, prediction_date);
CREATE INDEX IF NOT EXISTS idx_biometric_events_agent ON biometric_events(agent_id, created_at);
CREATE INDEX IF NOT EXISTS idx_eod_terminal_date ON pos_eod_reconciliation(terminal_id, reconciliation_date);
CREATE INDEX IF NOT EXISTS idx_geo_velocity_terminal ON pos_geo_velocity_log(terminal_id, created_at);
