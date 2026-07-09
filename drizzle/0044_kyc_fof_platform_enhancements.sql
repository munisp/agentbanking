-- Platform Enhancements: KYC/KYB/Liveness + Flow of Funds + UI/UX persistence
-- Covers: liveness cooldown, tiered KYC, document expiry, Temporal outbox,
-- settlement batching, fee splitting, float alerts, recurring executor

-- ═══════════════════════════════════════════════════════════════════════════════
-- (A) KYC/KYB/LIVENESS PERSISTENCE
-- ═══════════════════════════════════════════════════════════════════════════════

-- 1. Liveness cooldown (replaces in-memory Map in livenessSecurityEnhancements.ts)
CREATE TABLE IF NOT EXISTS liveness_cooldown (
  user_id       VARCHAR(128) PRIMARY KEY,
  failures      INT NOT NULL DEFAULT 0,
  last_failure  TIMESTAMPTZ,
  locked_until  TIMESTAMPTZ,
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. Device liveness history (replaces in-memory Map)
CREATE TABLE IF NOT EXISTS liveness_device_history (
  id              BIGSERIAL PRIMARY KEY,
  user_id         VARCHAR(128) NOT NULL,
  device_fingerprint VARCHAR(256) NOT NULL,
  camera_res      VARCHAR(32),
  device_model    VARCHAR(128),
  attempts        INT NOT NULL DEFAULT 0,
  last_attempt    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  threshold_adj   DOUBLE PRECISION DEFAULT 0,
  UNIQUE(user_id, device_fingerprint)
);
CREATE INDEX IF NOT EXISTS idx_liveness_device_user ON liveness_device_history (user_id);

-- 3. KYC tiers (CBN tiered limits)
CREATE TABLE IF NOT EXISTS kyc_tiers (
  agent_id        BIGINT PRIMARY KEY,
  tier            INT NOT NULL DEFAULT 1 CHECK (tier BETWEEN 1 AND 3),
  daily_limit     BIGINT NOT NULL DEFAULT 50000,  -- kobo (Tier1=₦50K)
  monthly_limit   BIGINT NOT NULL DEFAULT 300000, -- kobo
  upgraded_at     TIMESTAMPTZ,
  next_review     TIMESTAMPTZ,
  documents_json  JSONB DEFAULT '[]'::jsonb,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4. Document expiry tracking
CREATE TABLE IF NOT EXISTS kyc_document_expiry (
  id              BIGSERIAL PRIMARY KEY,
  agent_id        BIGINT NOT NULL,
  doc_type        VARCHAR(64) NOT NULL,
  doc_number      VARCHAR(128),
  issued_at       DATE,
  expires_at      DATE NOT NULL,
  reminder_sent   BOOLEAN DEFAULT FALSE,
  renewed         BOOLEAN DEFAULT FALSE,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_doc_expiry_agent ON kyc_document_expiry (agent_id);
CREATE INDEX IF NOT EXISTS idx_doc_expiry_expires ON kyc_document_expiry (expires_at);

-- 5. Continuous monitoring (watchlist re-screen results)
CREATE TABLE IF NOT EXISTS kyc_continuous_monitoring (
  id              BIGSERIAL PRIMARY KEY,
  agent_id        BIGINT NOT NULL,
  check_type      VARCHAR(64) NOT NULL, -- PEP, sanctions, adverse_media
  result          VARCHAR(32) NOT NULL, -- clear, hit, pending
  details_json    JSONB,
  checked_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  next_check      TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_continuous_monitor_agent ON kyc_continuous_monitoring (agent_id);
CREATE INDEX IF NOT EXISTS idx_continuous_monitor_next ON kyc_continuous_monitoring (next_check);

-- 6. KYC provider failover log
CREATE TABLE IF NOT EXISTS kyc_provider_log (
  id              BIGSERIAL PRIMARY KEY,
  agent_id        BIGINT NOT NULL,
  provider        VARCHAR(64) NOT NULL, -- smile_id, youverify, manual
  request_type    VARCHAR(64) NOT NULL, -- ocr, liveness, face_match
  success         BOOLEAN NOT NULL,
  latency_ms      INT,
  error_code      VARCHAR(128),
  fallback_used   BOOLEAN DEFAULT FALSE,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ═══════════════════════════════════════════════════════════════════════════════
-- (B) FLOW OF FUNDS PERSISTENCE
-- ═══════════════════════════════════════════════════════════════════════════════

-- 7. Transactional outbox (exactly-once event delivery)
CREATE TABLE IF NOT EXISTS event_outbox (
  id              BIGSERIAL PRIMARY KEY,
  aggregate_type  VARCHAR(64) NOT NULL,
  aggregate_id    VARCHAR(128) NOT NULL,
  event_type      VARCHAR(128) NOT NULL,
  payload         JSONB NOT NULL,
  published       BOOLEAN NOT NULL DEFAULT FALSE,
  retry_count     INT NOT NULL DEFAULT 0,
  max_retries     INT NOT NULL DEFAULT 5,
  next_retry_at   TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  published_at    TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_outbox_unpublished ON event_outbox (published, next_retry_at) WHERE published = FALSE;
CREATE INDEX IF NOT EXISTS idx_outbox_aggregate ON event_outbox (aggregate_type, aggregate_id);

-- 8. Dead letter queue
CREATE TABLE IF NOT EXISTS event_dead_letter (
  id              BIGSERIAL PRIMARY KEY,
  original_event_id BIGINT REFERENCES event_outbox(id),
  event_type      VARCHAR(128) NOT NULL,
  payload         JSONB NOT NULL,
  error_message   TEXT,
  retry_count     INT NOT NULL DEFAULT 0,
  resolved        BOOLEAN NOT NULL DEFAULT FALSE,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  resolved_at     TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_dlq_unresolved ON event_dead_letter (resolved) WHERE resolved = FALSE;

-- 9. Settlement batches (T+0 / T+1)
CREATE TABLE IF NOT EXISTS settlement_batches (
  id              BIGSERIAL PRIMARY KEY,
  batch_ref       VARCHAR(64) UNIQUE NOT NULL,
  settlement_type VARCHAR(32) NOT NULL, -- T0_agent, T1_bank
  status          VARCHAR(32) NOT NULL DEFAULT 'pending', -- pending, processing, settled, failed
  total_amount    BIGINT NOT NULL DEFAULT 0,
  transaction_count INT NOT NULL DEFAULT 0,
  cut_off_time    TIMESTAMPTZ NOT NULL,
  settled_at      TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_settlement_status ON settlement_batches (status);

-- 10. Settlement batch items
CREATE TABLE IF NOT EXISTS settlement_batch_items (
  id              BIGSERIAL PRIMARY KEY,
  batch_id        BIGINT REFERENCES settlement_batches(id),
  transaction_ref VARCHAR(128) NOT NULL,
  agent_id        BIGINT NOT NULL,
  amount          BIGINT NOT NULL,
  fee_amount      BIGINT NOT NULL DEFAULT 0,
  status          VARCHAR(32) NOT NULL DEFAULT 'pending'
);
CREATE INDEX IF NOT EXISTS idx_settlement_items_batch ON settlement_batch_items (batch_id);

-- 11. Fee waterfall splits
CREATE TABLE IF NOT EXISTS fee_waterfall (
  id              BIGSERIAL PRIMARY KEY,
  transaction_ref VARCHAR(128) NOT NULL,
  total_fee       BIGINT NOT NULL,
  platform_share  BIGINT NOT NULL, -- 40%
  agent_share     BIGINT NOT NULL, -- 35%
  super_agent_share BIGINT NOT NULL, -- 20%
  tax_share       BIGINT NOT NULL, -- 5%
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_fee_waterfall_ref ON fee_waterfall (transaction_ref);

-- 12. Float threshold alerts
CREATE TABLE IF NOT EXISTS float_threshold_alerts (
  id              BIGSERIAL PRIMARY KEY,
  agent_id        BIGINT NOT NULL,
  current_balance BIGINT NOT NULL,
  threshold_pct   INT NOT NULL, -- 20 or 10
  alert_type      VARCHAR(32) NOT NULL, -- warning (20%), critical (10%)
  notified_via    VARCHAR(64), -- sms, push, email
  acknowledged    BOOLEAN DEFAULT FALSE,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_float_alerts_agent ON float_threshold_alerts (agent_id);

-- 13. Recurring payment executions
CREATE TABLE IF NOT EXISTS recurring_payment_executions (
  id              BIGSERIAL PRIMARY KEY,
  schedule_id     BIGINT NOT NULL,
  agent_id        BIGINT NOT NULL,
  amount          BIGINT NOT NULL,
  status          VARCHAR(32) NOT NULL DEFAULT 'pending', -- pending, executed, failed, skipped
  execution_time  TIMESTAMPTZ NOT NULL,
  transaction_ref VARCHAR(128),
  error_message   TEXT,
  retry_count     INT DEFAULT 0,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_recurring_exec_schedule ON recurring_payment_executions (schedule_id);
CREATE INDEX IF NOT EXISTS idx_recurring_exec_time ON recurring_payment_executions (execution_time, status);

-- 14. Reconciliation runs
CREATE TABLE IF NOT EXISTS reconciliation_runs (
  id              BIGSERIAL PRIMARY KEY,
  run_date        DATE NOT NULL,
  gl_total        BIGINT NOT NULL,
  tigerbeetle_total BIGINT NOT NULL,
  float_total     BIGINT NOT NULL,
  discrepancy     BIGINT NOT NULL DEFAULT 0,
  status          VARCHAR(32) NOT NULL DEFAULT 'pending', -- pending, matched, discrepancy, resolved
  details_json    JSONB,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_recon_date ON reconciliation_runs (run_date);

-- 15. Middleware health tracking (replaces silent fail-open)
CREATE TABLE IF NOT EXISTS middleware_health_log (
  id              BIGSERIAL PRIMARY KEY,
  service_name    VARCHAR(64) NOT NULL, -- tigerbeetle, fluvio, dapr, lakehouse, redis
  router_name     VARCHAR(128) NOT NULL,
  status          VARCHAR(32) NOT NULL, -- success, timeout, error, unreachable
  latency_ms      INT,
  error_message   TEXT,
  recorded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_mw_health_service ON middleware_health_log (service_name, recorded_at);

-- ═══════════════════════════════════════════════════════════════════════════════
-- (C) UI/UX PERSISTENCE
-- ═══════════════════════════════════════════════════════════════════════════════

-- 16. Offline transaction queue (syncs with mobile)
CREATE TABLE IF NOT EXISTS offline_transaction_queue (
  id              BIGSERIAL PRIMARY KEY,
  agent_id        BIGINT NOT NULL,
  device_id       VARCHAR(128) NOT NULL,
  tx_type         VARCHAR(64) NOT NULL,
  payload         JSONB NOT NULL,
  status          VARCHAR(32) NOT NULL DEFAULT 'queued', -- queued, syncing, synced, failed
  queued_at       TIMESTAMPTZ NOT NULL,
  synced_at       TIMESTAMPTZ,
  conflict_resolution VARCHAR(32), -- client_wins, server_wins, merged
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_offline_queue_agent ON offline_transaction_queue (agent_id, status);

-- 17. User language preferences (i18n)
CREATE TABLE IF NOT EXISTS user_locale_preferences (
  agent_id        BIGINT PRIMARY KEY,
  locale          VARCHAR(10) NOT NULL DEFAULT 'en', -- en, ha, yo, pcm (pidgin)
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 18. Agent proficiency tracking (adaptive UI)
CREATE TABLE IF NOT EXISTS agent_proficiency (
  agent_id        BIGINT PRIMARY KEY,
  level           VARCHAR(16) NOT NULL DEFAULT 'beginner', -- beginner, intermediate, expert
  total_transactions INT NOT NULL DEFAULT 0,
  avg_tx_time_ms  INT,
  preferred_input VARCHAR(32) DEFAULT 'touch', -- touch, keyboard, voice
  shortcuts_enabled BOOLEAN DEFAULT FALSE,
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
