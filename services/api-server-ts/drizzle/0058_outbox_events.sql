-- ─────────────────────────────────────────────────────────────────────────────
-- Migration 0058: Transactional outbox for api-server-ts
-- Ports the transactional-outbox semantics (event_outbox / event_dead_letter)
-- that previously only existed in the stale root server/ tree into the
-- canonical api-server-ts schema. Events are written to outbox_events inside
-- the same DB transaction as the business operation (see
-- server/lib/transactionalOutbox.ts writeToOutboxTx) and published to Kafka
-- asynchronously with bounded exponential-backoff retry; poison events are
-- moved to outbox_dead_letters instead of being silently dropped.
-- ─────────────────────────────────────────────────────────────────────────────

-- 1. Outbox events (written inside withTransaction, published asynchronously)
CREATE TABLE IF NOT EXISTS outbox_events (
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
CREATE INDEX IF NOT EXISTS idx_outbox_events_unpublished
  ON outbox_events (published, next_retry_at) WHERE published = FALSE;
CREATE INDEX IF NOT EXISTS idx_outbox_events_aggregate
  ON outbox_events (aggregate_type, aggregate_id);

-- 2. Dead letters for events that exhausted retries
CREATE TABLE IF NOT EXISTS outbox_dead_letters (
  id                BIGSERIAL PRIMARY KEY,
  original_event_id BIGINT REFERENCES outbox_events(id),
  event_type        VARCHAR(128) NOT NULL,
  payload           JSONB NOT NULL,
  error_message     TEXT,
  retry_count       INT NOT NULL DEFAULT 0,
  resolved          BOOLEAN NOT NULL DEFAULT FALSE,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  resolved_at       TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_outbox_dead_letters_unresolved
  ON outbox_dead_letters (resolved) WHERE resolved = FALSE;
