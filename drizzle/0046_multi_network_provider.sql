-- Multi-Network Provider Enhancement Migration
-- Adds tables for SIM failover engine, carrier-aware routing, and telemetry persistence

-- SIM slot real-time status (Rust multi-sim-failover service)
CREATE TABLE IF NOT EXISTS sim_slot_status (
    terminal_id TEXT NOT NULL,
    slot_index INT NOT NULL,
    carrier_code TEXT NOT NULL DEFAULT '',
    carrier_name TEXT NOT NULL DEFAULT '',
    iccid TEXT NOT NULL DEFAULT '',
    signal_dbm INT NOT NULL DEFAULT -85,
    network_type TEXT NOT NULL DEFAULT 'unknown',
    is_active BOOLEAN NOT NULL DEFAULT true,
    is_data_preferred BOOLEAN NOT NULL DEFAULT false,
    score INT NOT NULL DEFAULT 50,
    last_probe_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (terminal_id, slot_index)
);

-- SIM signal history for trend analysis and scoring
CREATE TABLE IF NOT EXISTS sim_signal_history (
    id BIGSERIAL PRIMARY KEY,
    terminal_id TEXT NOT NULL,
    agent_code TEXT NOT NULL DEFAULT '',
    slot_index INT NOT NULL,
    carrier_code TEXT NOT NULL,
    signal_dbm INT NOT NULL,
    latency_ms DOUBLE PRECISION NOT NULL DEFAULT 0,
    packet_loss_pct DOUBLE PRECISION NOT NULL DEFAULT 0,
    network_type TEXT NOT NULL DEFAULT 'unknown',
    score INT NOT NULL DEFAULT 0,
    probed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sim_history_terminal_time ON sim_signal_history (terminal_id, probed_at DESC);
CREATE INDEX IF NOT EXISTS idx_sim_history_carrier ON sim_signal_history (carrier_code, probed_at DESC);

-- SIM failover events log
CREATE TABLE IF NOT EXISTS sim_failover_events (
    id TEXT PRIMARY KEY,
    terminal_id TEXT NOT NULL,
    from_slot INT NOT NULL,
    to_slot INT NOT NULL,
    from_carrier TEXT NOT NULL DEFAULT '',
    to_carrier TEXT NOT NULL DEFAULT '',
    reason TEXT NOT NULL DEFAULT '',
    trigger_signal_dbm INT NOT NULL DEFAULT 0,
    trigger_latency_ms DOUBLE PRECISION NOT NULL DEFAULT 0,
    success BOOLEAN NOT NULL DEFAULT true,
    switched_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sim_failover_terminal ON sim_failover_events (terminal_id, switched_at DESC);

-- SIM failover policies per terminal
CREATE TABLE IF NOT EXISTS sim_failover_policies (
    terminal_id TEXT PRIMARY KEY,
    min_signal_dbm INT NOT NULL DEFAULT -90,
    max_latency_ms INT NOT NULL DEFAULT 500,
    max_packet_loss_pct DOUBLE PRECISION NOT NULL DEFAULT 10.0,
    max_consecutive_failures INT NOT NULL DEFAULT 3,
    prefer_reliability_for_financial BOOLEAN NOT NULL DEFAULT true,
    auto_failover_enabled BOOLEAN NOT NULL DEFAULT true,
    cooldown_seconds INT NOT NULL DEFAULT 60,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Telemetry aggregator persistence (replaces in-memory HashMap/Vec)
CREATE TABLE IF NOT EXISTS telemetry_agent_scores (
    agent_code TEXT PRIMARY KEY,
    score DOUBLE PRECISION NOT NULL DEFAULT 0,
    latency_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    jitter_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    bandwidth_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    loss_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    signal_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    tier TEXT NOT NULL DEFAULT '',
    grade TEXT NOT NULL DEFAULT '',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS telemetry_carrier_stats (
    carrier TEXT PRIMARY KEY,
    country TEXT NOT NULL DEFAULT 'NG',
    agent_count BIGINT NOT NULL DEFAULT 0,
    avg_quality_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    avg_latency_ms DOUBLE PRECISION NOT NULL DEFAULT 0,
    avg_bandwidth_kbps DOUBLE PRECISION NOT NULL DEFAULT 0,
    avg_packet_loss_pct DOUBLE PRECISION NOT NULL DEFAULT 0,
    sla_compliance_pct DOUBLE PRECISION NOT NULL DEFAULT 0,
    uptime_pct DOUBLE PRECISION NOT NULL DEFAULT 0,
    rank INT NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS telemetry_anomalies (
    id TEXT PRIMARY KEY,
    anomaly_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    agent_code TEXT NOT NULL,
    carrier TEXT NOT NULL,
    region TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    metric_value DOUBLE PRECISION NOT NULL DEFAULT 0,
    threshold DOUBLE PRECISION NOT NULL DEFAULT 0,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_telemetry_anomalies_time ON telemetry_anomalies (detected_at DESC);
