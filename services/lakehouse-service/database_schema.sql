-- PostgreSQL Database Schema for Lakehouse Authentication
-- Version: 1.0.0
-- Created: 2025-10-25

-- ============================================================================
-- EXTENSIONS
-- ============================================================================

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable pgcrypto for additional encryption functions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================================
-- ENUMS
-- ============================================================================

-- User roles enum
CREATE TYPE user_role AS ENUM ('admin', 'data_engineer', 'analyst', 'viewer');

-- MFA method enum
CREATE TYPE mfa_method AS ENUM ('totp', 'sms', 'email');

-- Token type enum
CREATE TYPE token_type AS ENUM ('access', 'refresh', 'mfa');

-- ============================================================================
-- TABLES
-- ============================================================================

-- Users table
CREATE TABLE users (
    user_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    role user_role NOT NULL DEFAULT 'viewer',
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    
    -- MFA fields
    mfa_enabled BOOLEAN DEFAULT FALSE,
    mfa_method mfa_method DEFAULT 'totp',
    mfa_secret VARCHAR(255),  -- Encrypted TOTP secret
    mfa_backup_codes TEXT[],  -- Array of backup codes
    
    -- Profile fields
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    phone VARCHAR(20),
    department VARCHAR(100),
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP WITH TIME ZONE,
    password_changed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Security fields
    failed_login_attempts INTEGER DEFAULT 0,
    locked_until TIMESTAMP WITH TIME ZONE,
    
    -- Metadata
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Refresh tokens table
CREATE TABLE refresh_tokens (
    token_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL UNIQUE,  -- SHA256 hash of token
    
    -- Device information
    device_name VARCHAR(255),
    device_type VARCHAR(50),  -- web, mobile, desktop
    ip_address INET,
    user_agent TEXT,
    
    -- Token lifecycle
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    last_used_at TIMESTAMP WITH TIME ZONE,
    is_revoked BOOLEAN DEFAULT FALSE,
    revoked_at TIMESTAMP WITH TIME ZONE,
    revoked_reason VARCHAR(255)
);

-- Audit logs table
CREATE TABLE audit_logs (
    log_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(user_id) ON DELETE SET NULL,
    username VARCHAR(50),
    
    -- Action details
    action VARCHAR(50) NOT NULL,  -- login, logout, create, read, update, delete
    resource_type VARCHAR(50),    -- table, query, pipeline, etc.
    resource_id VARCHAR(255),
    endpoint VARCHAR(255),
    
    -- Request details
    method VARCHAR(10),           -- GET, POST, PUT, DELETE
    status_code INTEGER,
    ip_address INET,
    user_agent TEXT,
    
    -- Result
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    
    -- Metadata
    metadata JSONB DEFAULT '{}'::jsonb,
    
    -- Timestamp
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- MFA attempts table (for rate limiting)
CREATE TABLE mfa_attempts (
    attempt_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    
    -- Attempt details
    code_entered VARCHAR(10),
    success BOOLEAN DEFAULT FALSE,
    ip_address INET,
    
    -- Timestamp
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Password reset tokens table
CREATE TABLE password_reset_tokens (
    token_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL UNIQUE,
    
    -- Token lifecycle
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    used_at TIMESTAMP WITH TIME ZONE,
    is_used BOOLEAN DEFAULT FALSE
);

-- API keys table (for service-to-service authentication)
CREATE TABLE api_keys (
    key_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    
    -- Key details
    key_hash VARCHAR(255) NOT NULL UNIQUE,  -- SHA256 hash of key
    key_prefix VARCHAR(10) NOT NULL,        -- First 8 chars for identification
    name VARCHAR(100) NOT NULL,
    description TEXT,
    
    -- Permissions
    scopes TEXT[] DEFAULT '{}',  -- Array of permission scopes
    
    -- Key lifecycle
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE,
    last_used_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Metadata
    metadata JSONB DEFAULT '{}'::jsonb
);

-- ============================================================================
-- INDEXES
-- ============================================================================

-- Users indexes
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_is_active ON users(is_active);
CREATE INDEX idx_users_created_at ON users(created_at);

-- Refresh tokens indexes
CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX idx_refresh_tokens_token_hash ON refresh_tokens(token_hash);
CREATE INDEX idx_refresh_tokens_expires_at ON refresh_tokens(expires_at);
CREATE INDEX idx_refresh_tokens_is_revoked ON refresh_tokens(is_revoked);

-- Audit logs indexes
CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_username ON audit_logs(username);
CREATE INDEX idx_audit_logs_action ON audit_logs(action);
CREATE INDEX idx_audit_logs_resource_type ON audit_logs(resource_type);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at);
CREATE INDEX idx_audit_logs_metadata ON audit_logs USING gin(metadata);

-- MFA attempts indexes
CREATE INDEX idx_mfa_attempts_user_id ON mfa_attempts(user_id);
CREATE INDEX idx_mfa_attempts_created_at ON mfa_attempts(created_at);

-- Password reset tokens indexes
CREATE INDEX idx_password_reset_tokens_user_id ON password_reset_tokens(user_id);
CREATE INDEX idx_password_reset_tokens_token_hash ON password_reset_tokens(token_hash);
CREATE INDEX idx_password_reset_tokens_expires_at ON password_reset_tokens(expires_at);

-- API keys indexes
CREATE INDEX idx_api_keys_user_id ON api_keys(user_id);
CREATE INDEX idx_api_keys_key_hash ON api_keys(key_hash);
CREATE INDEX idx_api_keys_key_prefix ON api_keys(key_prefix);
CREATE INDEX idx_api_keys_is_active ON api_keys(is_active);

-- ============================================================================
-- TRIGGERS
-- ============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for users table
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- FUNCTIONS
-- ============================================================================

-- Function to clean up expired tokens
CREATE OR REPLACE FUNCTION cleanup_expired_tokens()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM refresh_tokens
    WHERE expires_at < CURRENT_TIMESTAMP
    AND is_revoked = FALSE;
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Function to clean up old audit logs (older than 90 days)
CREATE OR REPLACE FUNCTION cleanup_old_audit_logs()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM audit_logs
    WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '90 days';
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Function to revoke all user tokens
CREATE OR REPLACE FUNCTION revoke_all_user_tokens(p_user_id UUID)
RETURNS INTEGER AS $$
DECLARE
    revoked_count INTEGER;
BEGIN
    UPDATE refresh_tokens
    SET is_revoked = TRUE,
        revoked_at = CURRENT_TIMESTAMP,
        revoked_reason = 'User logout all devices'
    WHERE user_id = p_user_id
    AND is_revoked = FALSE;
    
    GET DIAGNOSTICS revoked_count = ROW_COUNT;
    RETURN revoked_count;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- INITIAL DATA
-- ============================================================================

-- Insert demo users (passwords are hashed with bcrypt)
-- Note: In production, use proper password hashing
INSERT INTO users (username, email, hashed_password, role, first_name, last_name, is_verified) VALUES
    ('admin', 'admin@agentbanking.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYzpLHJ4tja', 'admin', 'Admin', 'User', TRUE),
    ('data_engineer', 'engineer@agentbanking.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYzpLHJ4tja', 'data_engineer', 'Data', 'Engineer', TRUE),
    ('analyst', 'analyst@agentbanking.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYzpLHJ4tja', 'analyst', 'Data', 'Analyst', TRUE),
    ('viewer', 'viewer@agentbanking.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYzpLHJ4tja', 'viewer', 'Guest', 'Viewer', TRUE);

-- ============================================================================
-- VIEWS
-- ============================================================================

-- View for active users with recent login
CREATE VIEW active_users AS
SELECT 
    user_id,
    username,
    email,
    role,
    last_login,
    created_at
FROM users
WHERE is_active = TRUE
ORDER BY last_login DESC NULLS LAST;

-- View for audit log summary
CREATE VIEW audit_log_summary AS
SELECT 
    username,
    action,
    resource_type,
    COUNT(*) as action_count,
    MAX(created_at) as last_action
FROM audit_logs
WHERE created_at > CURRENT_TIMESTAMP - INTERVAL '7 days'
GROUP BY username, action, resource_type
ORDER BY action_count DESC;

-- ============================================================================
-- GRANTS (adjust based on your application user)
-- ============================================================================

-- Create application user (if not exists)
-- CREATE USER lakehouse_app WITH PASSWORD 'your_secure_password';

-- Grant permissions
-- GRANT CONNECT ON DATABASE lakehouse_db TO lakehouse_app;
-- GRANT USAGE ON SCHEMA public TO lakehouse_app;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO lakehouse_app;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO lakehouse_app;

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE users IS 'User accounts with authentication and profile information';
COMMENT ON TABLE refresh_tokens IS 'Refresh tokens for JWT authentication with device tracking';
COMMENT ON TABLE audit_logs IS 'Audit trail of all user actions and API requests';
COMMENT ON TABLE mfa_attempts IS 'Multi-factor authentication attempts for rate limiting';
COMMENT ON TABLE password_reset_tokens IS 'Tokens for password reset functionality';
COMMENT ON TABLE api_keys IS 'API keys for service-to-service authentication';

COMMENT ON COLUMN users.mfa_secret IS 'Encrypted TOTP secret for multi-factor authentication';
COMMENT ON COLUMN users.mfa_backup_codes IS 'Array of one-time backup codes for MFA recovery';
COMMENT ON COLUMN users.failed_login_attempts IS 'Counter for failed login attempts (resets on success)';
COMMENT ON COLUMN users.locked_until IS 'Account lock timestamp after too many failed attempts';

-- ============================================================================
-- MAINTENANCE QUERIES
-- ============================================================================

-- Run these periodically (or set up as cron jobs)

-- Clean up expired tokens
-- SELECT cleanup_expired_tokens();

-- Clean up old audit logs
-- SELECT cleanup_old_audit_logs();

-- Revoke all tokens for a user
-- SELECT revoke_all_user_tokens('user_id_here');

-- ============================================================================
-- USEFUL QUERIES
-- ============================================================================

-- Get user with active tokens
-- SELECT u.username, COUNT(rt.token_id) as active_tokens
-- FROM users u
-- LEFT JOIN refresh_tokens rt ON u.user_id = rt.user_id AND rt.is_revoked = FALSE
-- GROUP BY u.user_id, u.username;

-- Get recent audit logs for a user
-- SELECT * FROM audit_logs
-- WHERE username = 'admin'
-- ORDER BY created_at DESC
-- LIMIT 100;

-- Get MFA-enabled users
-- SELECT username, email, mfa_method
-- FROM users
-- WHERE mfa_enabled = TRUE;

-- Get locked accounts
-- SELECT username, email, locked_until
-- FROM users
-- WHERE locked_until > CURRENT_TIMESTAMP;

