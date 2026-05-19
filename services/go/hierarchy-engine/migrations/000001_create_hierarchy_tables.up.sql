-- 000001_create_hierarchy_tables.up.sql
-- Hierarchy Engine: bank → branch → agent → sub-agent tree

CREATE TABLE IF NOT EXISTS institutions (
    id            VARCHAR(36)  PRIMARY KEY DEFAULT (UUID()),
    name          VARCHAR(255) NOT NULL,
    cbn_code      VARCHAR(20)  UNIQUE NOT NULL,
    license_type  ENUM('commercial_bank','microfinance','mobile_money','agent_network') NOT NULL,
    status        ENUM('active','suspended','revoked') NOT NULL DEFAULT 'active',
    created_at    BIGINT NOT NULL DEFAULT (UNIX_TIMESTAMP() * 1000),
    updated_at    BIGINT NOT NULL DEFAULT (UNIX_TIMESTAMP() * 1000)
);

CREATE TABLE IF NOT EXISTS branches (
    id             VARCHAR(36)  PRIMARY KEY DEFAULT (UUID()),
    institution_id VARCHAR(36)  NOT NULL REFERENCES institutions(id),
    name           VARCHAR(255) NOT NULL,
    branch_code    VARCHAR(20)  UNIQUE NOT NULL,
    state          VARCHAR(50)  NOT NULL,
    lga            VARCHAR(100),
    address        TEXT,
    manager_id     VARCHAR(36),
    status         ENUM('active','suspended','closed') NOT NULL DEFAULT 'active',
    created_at     BIGINT NOT NULL DEFAULT (UNIX_TIMESTAMP() * 1000),
    updated_at     BIGINT NOT NULL DEFAULT (UNIX_TIMESTAMP() * 1000),
    INDEX idx_branches_institution (institution_id),
    INDEX idx_branches_state (state)
);

CREATE TABLE IF NOT EXISTS agents (
    id              VARCHAR(36)  PRIMARY KEY DEFAULT (UUID()),
    branch_id       VARCHAR(36)  NOT NULL REFERENCES branches(id),
    agent_code      VARCHAR(20)  UNIQUE NOT NULL,
    business_name   VARCHAR(255) NOT NULL,
    owner_name      VARCHAR(255) NOT NULL,
    phone           VARCHAR(20)  NOT NULL,
    bvn             VARCHAR(11),
    nin             VARCHAR(11),
    tier            TINYINT NOT NULL DEFAULT 1 COMMENT '1=Basic 2=Standard 3=Premium',
    float_balance   BIGINT NOT NULL DEFAULT 0 COMMENT 'Kobo',
    daily_limit     BIGINT NOT NULL DEFAULT 50000000 COMMENT 'Kobo — CBN Tier 1 default',
    status          ENUM('active','suspended','deactivated','pending_kyc') NOT NULL DEFAULT 'pending_kyc',
    last_active_at  BIGINT,
    created_at      BIGINT NOT NULL DEFAULT (UNIX_TIMESTAMP() * 1000),
    updated_at      BIGINT NOT NULL DEFAULT (UNIX_TIMESTAMP() * 1000),
    INDEX idx_agents_branch (branch_id),
    INDEX idx_agents_status (status),
    INDEX idx_agents_tier (tier)
);

CREATE TABLE IF NOT EXISTS agent_sub_agents (
    id          VARCHAR(36) PRIMARY KEY DEFAULT (UUID()),
    agent_id    VARCHAR(36) NOT NULL REFERENCES agents(id),
    sub_agent_id VARCHAR(36) NOT NULL REFERENCES agents(id),
    created_at  BIGINT NOT NULL DEFAULT (UNIX_TIMESTAMP() * 1000),
    UNIQUE KEY uq_agent_sub (agent_id, sub_agent_id)
);

CREATE TABLE IF NOT EXISTS hierarchy_audit_log (
    id          VARCHAR(36)  PRIMARY KEY DEFAULT (UUID()),
    entity_type VARCHAR(50)  NOT NULL,
    entity_id   VARCHAR(36)  NOT NULL,
    action      VARCHAR(50)  NOT NULL,
    actor_id    VARCHAR(36)  NOT NULL,
    old_value   JSON,
    new_value   JSON,
    created_at  BIGINT NOT NULL DEFAULT (UNIX_TIMESTAMP() * 1000),
    INDEX idx_audit_entity (entity_type, entity_id),
    INDEX idx_audit_actor (actor_id)
);
