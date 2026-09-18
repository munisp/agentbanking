-- 0062_onboarding_pipeline.sql
-- Persistent onboarding pipeline state. The customerOnboardingPipeline router
-- previously computed pipeline position in memory (derived ad hoc per request)
-- and never persisted stage transitions, so restarts lost progress and
-- concurrent transitions could not be detected.

CREATE TABLE IF NOT EXISTS onboarding_pipeline_state (
    id               SERIAL PRIMARY KEY,
    tenant_id        INTEGER,
    entity_type      VARCHAR(32) NOT NULL,          -- 'customer' | 'agent'
    entity_id        VARCHAR(64) NOT NULL,
    current_stage    VARCHAR(32) NOT NULL DEFAULT 'registration',
    stages_completed JSONB NOT NULL DEFAULT '[]',
    status           VARCHAR(20) NOT NULL DEFAULT 'in_progress', -- in_progress | completed | cancelled
    updated_by       VARCHAR(64),
    notes            TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- One pipeline row per entity (tenant-scoped when tenant known)
CREATE UNIQUE INDEX IF NOT EXISTS ops_entity_uniq
    ON onboarding_pipeline_state (entity_type, entity_id, (COALESCE(tenant_id, 0)));

CREATE INDEX IF NOT EXISTS ops_stage_idx
    ON onboarding_pipeline_state (current_stage);

CREATE INDEX IF NOT EXISTS ops_tenant_idx
    ON onboarding_pipeline_state (tenant_id);
