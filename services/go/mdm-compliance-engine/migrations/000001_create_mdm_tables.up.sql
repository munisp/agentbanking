-- 000001_create_mdm_tables.up.sql
-- MDM Compliance Engine: device registry, heartbeats, compliance events

CREATE TABLE IF NOT EXISTS devices (
    id               VARCHAR(36)  PRIMARY KEY DEFAULT (UUID()),
    device_id        VARCHAR(100) UNIQUE NOT NULL,
    agent_id         VARCHAR(36)  NOT NULL,
    model            VARCHAR(100),
    os_version       VARCHAR(50),
    app_version      VARCHAR(20),
    serial_number    VARCHAR(100),
    imei             VARCHAR(20),
    sim_iccid        VARCHAR(25),
    enrolled_at      BIGINT NOT NULL DEFAULT (UNIX_TIMESTAMP() * 1000),
    last_heartbeat   BIGINT,
    status           ENUM('active','offline','suspended','decommissioned','lost') NOT NULL DEFAULT 'active',
    compliance_score TINYINT NOT NULL DEFAULT 100,
    latitude         DECIMAL(10,8),
    longitude        DECIMAL(11,8),
    created_at       BIGINT NOT NULL DEFAULT (UNIX_TIMESTAMP() * 1000),
    updated_at       BIGINT NOT NULL DEFAULT (UNIX_TIMESTAMP() * 1000),
    INDEX idx_devices_agent (agent_id),
    INDEX idx_devices_status (status),
    INDEX idx_devices_heartbeat (last_heartbeat)
);

CREATE TABLE IF NOT EXISTS device_heartbeats (
    id           VARCHAR(36) PRIMARY KEY DEFAULT (UUID()),
    device_id    VARCHAR(36) NOT NULL REFERENCES devices(id),
    battery_pct  TINYINT,
    signal_rssi  SMALLINT,
    app_version  VARCHAR(20),
    latitude     DECIMAL(10,8),
    longitude    DECIMAL(11,8),
    ip_address   VARCHAR(45),
    received_at  BIGINT NOT NULL DEFAULT (UNIX_TIMESTAMP() * 1000),
    INDEX idx_heartbeats_device (device_id),
    INDEX idx_heartbeats_received (received_at)
);

CREATE TABLE IF NOT EXISTS compliance_events (
    id           VARCHAR(36)  PRIMARY KEY DEFAULT (UUID()),
    device_id    VARCHAR(36)  NOT NULL REFERENCES devices(id),
    event_type   VARCHAR(50)  NOT NULL,
    severity     ENUM('info','warning','critical') NOT NULL DEFAULT 'info',
    description  TEXT,
    resolved     BOOLEAN NOT NULL DEFAULT FALSE,
    resolved_at  BIGINT,
    created_at   BIGINT NOT NULL DEFAULT (UNIX_TIMESTAMP() * 1000),
    INDEX idx_compliance_device (device_id),
    INDEX idx_compliance_type (event_type),
    INDEX idx_compliance_severity (severity),
    INDEX idx_compliance_resolved (resolved)
);

CREATE TABLE IF NOT EXISTS ota_updates (
    id              VARCHAR(36)  PRIMARY KEY DEFAULT (UUID()),
    version         VARCHAR(20)  NOT NULL,
    firmware_url    TEXT         NOT NULL,
    checksum_sha256 VARCHAR(64)  NOT NULL,
    file_size_bytes BIGINT       NOT NULL,
    release_notes   TEXT,
    min_os_version  VARCHAR(20),
    target_models   JSON,
    is_mandatory    BOOLEAN NOT NULL DEFAULT FALSE,
    rollout_pct     TINYINT NOT NULL DEFAULT 100,
    created_at      BIGINT NOT NULL DEFAULT (UNIX_TIMESTAMP() * 1000),
    INDEX idx_ota_version (version)
);

CREATE TABLE IF NOT EXISTS device_ota_assignments (
    id         VARCHAR(36) PRIMARY KEY DEFAULT (UUID()),
    device_id  VARCHAR(36) NOT NULL REFERENCES devices(id),
    ota_id     VARCHAR(36) NOT NULL REFERENCES ota_updates(id),
    status     ENUM('pending','downloading','installing','completed','failed') NOT NULL DEFAULT 'pending',
    started_at BIGINT,
    completed_at BIGINT,
    error_msg  TEXT,
    created_at BIGINT NOT NULL DEFAULT (UNIX_TIMESTAMP() * 1000),
    UNIQUE KEY uq_device_ota (device_id, ota_id),
    INDEX idx_ota_assign_device (device_id),
    INDEX idx_ota_assign_status (status)
);
