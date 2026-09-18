-- Insider Threat Persistence Tables
-- Eliminates all in-memory state from TypeScript middleware
-- Step-up tokens, admin sessions, and staff velocity actions are now PostgreSQL-backed

CREATE TABLE IF NOT EXISTS insider_step_up_tokens (
  token       VARCHAR(128) PRIMARY KEY,
  agent_id    BIGINT NOT NULL,
  expires_at  TIMESTAMPTZ NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_step_up_tokens_agent ON insider_step_up_tokens (agent_id);
CREATE INDEX IF NOT EXISTS idx_step_up_tokens_expires ON insider_step_up_tokens (expires_at);

CREATE TABLE IF NOT EXISTS insider_admin_sessions (
  agent_id       BIGINT PRIMARY KEY,
  last_activity  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS insider_staff_actions (
  id          BIGSERIAL PRIMARY KEY,
  agent_id    BIGINT NOT NULL,
  action      VARCHAR(128) NOT NULL,
  amount      DOUBLE PRECISION NOT NULL DEFAULT 0,
  recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_staff_actions_agent ON insider_staff_actions (agent_id, recorded_at);
CREATE INDEX IF NOT EXISTS idx_staff_actions_recorded ON insider_staff_actions (recorded_at);
