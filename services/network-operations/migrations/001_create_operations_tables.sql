-- Migration: Create Operations Tables for Canary Releases, A/B Tests, and Incidents
-- Timestamp: 2026-05-04
-- Description: Creates tables for network-operations service to track canary releases, A/B tests, and operational incidents

-- Create canary_releases table
CREATE TABLE IF NOT EXISTS canary_releases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service VARCHAR(255) NOT NULL,
    version VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'active', -- "active", "paused", "completed", "rolled_back"
    traffic_percentage INTEGER DEFAULT 0 CHECK (traffic_percentage >= 0 AND traffic_percentage <= 100),
    metrics JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    created_by VARCHAR(255),
    updated_by VARCHAR(255)
);

-- Create index on service and status for faster queries
CREATE INDEX idx_canary_releases_service_status ON canary_releases(service, status);
CREATE INDEX idx_canary_releases_created_at ON canary_releases(created_at DESC);

-- Create ab_tests table
CREATE TABLE IF NOT EXISTS ab_tests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'running', -- "running", "completed", "paused"
    variant_a VARCHAR(255) NOT NULL,
    variant_b VARCHAR(255) NOT NULL,
    traffic_split INTEGER DEFAULT 50 CHECK (traffic_split >= 0 AND traffic_split <= 100),
    results_a JSONB DEFAULT '{}',
    results_b JSONB DEFAULT '{}',
    started_at TIMESTAMP DEFAULT NOW(),
    ended_at TIMESTAMP,
    created_by VARCHAR(255),
    updated_by VARCHAR(255)
);

-- Create index on status and started_at for queries
CREATE INDEX idx_ab_tests_status ON ab_tests(status);
CREATE INDEX idx_ab_tests_started_at ON ab_tests(started_at DESC);

-- Create incidents table
CREATE TABLE IF NOT EXISTS incidents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    severity VARCHAR(50) NOT NULL CHECK (severity IN ('critical', 'high', 'medium', 'low')),
    status VARCHAR(50) NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'investigating', 'resolved')),
    service VARCHAR(255),
    assigned_to VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    resolved_at TIMESTAMP,
    created_by VARCHAR(255),
    updated_by VARCHAR(255)
);

-- Create indexes for incident queries
CREATE INDEX idx_incidents_status ON incidents(status);
CREATE INDEX idx_incidents_severity ON incidents(severity);
CREATE INDEX idx_incidents_service ON incidents(service);
CREATE INDEX idx_incidents_created_at ON incidents(created_at DESC);

-- Create incident_updates table
CREATE TABLE IF NOT EXISTS incident_updates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id UUID NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    timestamp TIMESTAMP DEFAULT NOW(),
    message TEXT NOT NULL,
    author VARCHAR(255) NOT NULL
);

-- Create index on incident_id for faster lookups
CREATE INDEX idx_incident_updates_incident_id ON incident_updates(incident_id);
CREATE INDEX idx_incident_updates_timestamp ON incident_updates(timestamp DESC);

-- Add comments for documentation
COMMENT ON TABLE canary_releases IS 'Tracks canary deployments across services with traffic percentage and metrics';
COMMENT ON TABLE ab_tests IS 'Tracks A/B testing across features with variant metrics and traffic split';
COMMENT ON TABLE incidents IS 'Operational incidents tracked by severity and status';
COMMENT ON TABLE incident_updates IS 'Timeline of updates for each incident';
