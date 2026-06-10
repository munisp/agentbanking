-- ============================================================================
-- Referral Program Database Migration
-- Remittance Platform V11.0
-- 
-- This migration creates all tables needed for the Referral Program Workflow.
-- 
-- Author: Manus AI
-- Date: November 11, 2025
-- ============================================================================

-- Table 1: Referral Codes
-- Stores unique referral codes for each user
CREATE TABLE IF NOT EXISTS referral_codes (
    id VARCHAR(255) PRIMARY KEY,
    user_id UUID NOT NULL,
    user_type VARCHAR(50) NOT NULL CHECK (user_type IN ('customer', 'agent')),
    referral_code VARCHAR(8) UNIQUE NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_referral_codes_user_id ON referral_codes(user_id);
CREATE INDEX idx_referral_codes_code ON referral_codes(referral_code);


-- Table 2: Referral Events
-- Tracks all referral events (signup, activation)
CREATE TABLE IF NOT EXISTS referral_events (
    id VARCHAR(255) PRIMARY KEY,
    referrer_id UUID NOT NULL,
    referral_code VARCHAR(8) NOT NULL,
    new_user_id UUID NOT NULL,
    new_user_type VARCHAR(50) NOT NULL CHECK (new_user_type IN ('customer', 'agent')),
    event_type VARCHAR(50) NOT NULL CHECK (event_type IN ('signed_up', 'activated')),
    event_timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    reward_amount DECIMAL(15,2) DEFAULT 0.00,
    reward_credited BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (referrer_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (new_user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_referral_events_referrer ON referral_events(referrer_id);
CREATE INDEX idx_referral_events_new_user ON referral_events(new_user_id);
CREATE INDEX idx_referral_events_code ON referral_events(referral_code);
CREATE INDEX idx_referral_events_type ON referral_events(event_type);
CREATE INDEX idx_referral_events_timestamp ON referral_events(event_timestamp);


-- Table 3: Referral Analytics
-- Aggregated analytics for each referrer (for leaderboard)
CREATE TABLE IF NOT EXISTS referral_analytics (
    user_id UUID PRIMARY KEY,
    total_referrals INT DEFAULT 0,
    activated_referrals INT DEFAULT 0,
    total_rewards_earned DECIMAL(15,2) DEFAULT 0.00,
    last_referral_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_referral_analytics_total ON referral_analytics(total_referrals DESC);
CREATE INDEX idx_referral_analytics_activated ON referral_analytics(activated_referrals DESC);
CREATE INDEX idx_referral_analytics_rewards ON referral_analytics(total_rewards_earned DESC);


-- Table 4: User Devices (for fraud detection)
CREATE TABLE IF NOT EXISTS user_devices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    device_id VARCHAR(255) NOT NULL,
    device_type VARCHAR(50),
    device_model VARCHAR(100),
    os_version VARCHAR(50),
    app_version VARCHAR(50),
    first_seen_at TIMESTAMP NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMP NOT NULL DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_user_devices_user_id ON user_devices(user_id);
CREATE INDEX idx_user_devices_device_id ON user_devices(device_id);


-- Table 5: User Sessions (for fraud detection)
CREATE TABLE IF NOT EXISTS user_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    session_token VARCHAR(255) UNIQUE NOT NULL,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_user_sessions_user_id ON user_sessions(user_id);
CREATE INDEX idx_user_sessions_ip ON user_sessions(ip_address);
CREATE INDEX idx_user_sessions_created ON user_sessions(created_at);


-- Add referral_badge column to users table (if not exists)
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'users' AND column_name = 'referral_badge'
    ) THEN
        ALTER TABLE users ADD COLUMN referral_badge VARCHAR(50);
    END IF;
END $$;


-- Create materialized view for leaderboard (performance optimization)
CREATE MATERIALIZED VIEW IF NOT EXISTS referral_leaderboard AS
SELECT 
    ra.user_id,
    u.full_name,
    u.phone_number,
    ra.total_referrals,
    ra.activated_referrals,
    ra.total_rewards_earned,
    u.referral_badge,
    RANK() OVER (ORDER BY ra.activated_referrals DESC, ra.total_referrals DESC) as rank
FROM referral_analytics ra
JOIN users u ON ra.user_id = u.id
WHERE ra.activated_referrals > 0
ORDER BY ra.activated_referrals DESC, ra.total_referrals DESC
LIMIT 100;

CREATE UNIQUE INDEX idx_referral_leaderboard_user ON referral_leaderboard(user_id);


-- Function to refresh leaderboard (called by scheduled job)
CREATE OR REPLACE FUNCTION refresh_referral_leaderboard()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY referral_leaderboard;
END;
$$ LANGUAGE plpgsql;


-- Sample data for testing (optional, remove in production)
-- INSERT INTO referral_codes (id, user_id, user_type, referral_code, created_at, expires_at)
-- VALUES 
--     ('ref-test-001', 'user-001', 'customer', 'TEST1234', NOW(), NOW() + INTERVAL '365 days'),
--     ('ref-test-002', 'user-002', 'agent', 'AGENT567', NOW(), NOW() + INTERVAL '365 days');


-- Grant permissions (adjust as needed for your environment)
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO workflow_service;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO workflow_service;


-- Migration complete
SELECT 'Referral Program migration completed successfully' AS status;

