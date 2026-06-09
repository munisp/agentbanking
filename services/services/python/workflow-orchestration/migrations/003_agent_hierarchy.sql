-- ============================================================================
-- Agent Hierarchy & Override Commission Database Migration
-- Remittance Platform V11.0
-- 
-- This migration creates all tables needed for the Agent Hierarchy Workflow.
-- 
-- Author: Manus AI
-- Date: November 11, 2025
-- ============================================================================

-- Table 1: Agent Hierarchy
-- Stores the hierarchical relationship between agents (adjacency list model)
CREATE TABLE IF NOT EXISTS agent_hierarchy (
    agent_id UUID PRIMARY KEY,
    upline_agent_id UUID,
    hierarchy_level INT NOT NULL DEFAULT 0,
    recruitment_date TIMESTAMP NOT NULL DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (agent_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (upline_agent_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_agent_hierarchy_upline ON agent_hierarchy(upline_agent_id);
CREATE INDEX idx_agent_hierarchy_level ON agent_hierarchy(hierarchy_level);
CREATE INDEX idx_agent_hierarchy_active ON agent_hierarchy(is_active);
CREATE INDEX idx_agent_hierarchy_recruitment_date ON agent_hierarchy(recruitment_date);


-- Table 2: Override Commissions
-- Tracks all override commission transactions
CREATE TABLE IF NOT EXISTS override_commissions (
    id VARCHAR(255) PRIMARY KEY,
    upline_agent_id UUID NOT NULL,
    downline_agent_id UUID NOT NULL,
    downline_transaction_id VARCHAR(255) NOT NULL,
    downline_commission_amount DECIMAL(15,2) NOT NULL,
    override_level INT NOT NULL CHECK (override_level BETWEEN 1 AND 5),
    override_percentage DECIMAL(5,2) NOT NULL,
    override_amount DECIMAL(15,2) NOT NULL,
    is_capped BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    FOREIGN KEY (upline_agent_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (downline_agent_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_override_commissions_upline ON override_commissions(upline_agent_id);
CREATE INDEX idx_override_commissions_downline ON override_commissions(downline_agent_id);
CREATE INDEX idx_override_commissions_transaction ON override_commissions(downline_transaction_id);
CREATE INDEX idx_override_commissions_created ON override_commissions(created_at);
CREATE INDEX idx_override_commissions_level ON override_commissions(override_level);


-- Table 3: Team Performance
-- Aggregated performance metrics for each agent's team
CREATE TABLE IF NOT EXISTS team_performance (
    agent_id UUID PRIMARY KEY,
    total_downline_agents INT DEFAULT 0,
    level_1_count INT DEFAULT 0,
    level_2_count INT DEFAULT 0,
    level_3_count INT DEFAULT 0,
    level_4_count INT DEFAULT 0,
    level_5_count INT DEFAULT 0,
    total_override_commission DECIMAL(15,2) DEFAULT 0.00,
    last_updated TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (agent_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_team_performance_downline ON team_performance(total_downline_agents DESC);
CREATE INDEX idx_team_performance_commission ON team_performance(total_override_commission DESC);
CREATE INDEX idx_team_performance_updated ON team_performance(last_updated);


-- Table 4: Recruitment Bonuses
-- Tracks recruitment bonuses (₦5,000 for every 10 recruits)
CREATE TABLE IF NOT EXISTS recruitment_bonuses (
    id VARCHAR(255) PRIMARY KEY,
    upline_agent_id UUID NOT NULL,
    recruited_agent_id UUID NOT NULL,
    recruitment_milestone INT NOT NULL,  -- 10, 20, 30, etc.
    bonus_amount DECIMAL(15,2) NOT NULL DEFAULT 5000.00,
    credited BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    FOREIGN KEY (upline_agent_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (recruited_agent_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_recruitment_bonuses_upline ON recruitment_bonuses(upline_agent_id);
CREATE INDEX idx_recruitment_bonuses_milestone ON recruitment_bonuses(recruitment_milestone);
CREATE INDEX idx_recruitment_bonuses_created ON recruitment_bonuses(created_at);


-- Table 5: Team Messages
-- Stores messages sent from upline agents to their teams
CREATE TABLE IF NOT EXISTS team_messages (
    id VARCHAR(255) PRIMARY KEY,
    sender_agent_id UUID NOT NULL,
    target_level INT,  -- NULL = all levels, 1 = only L1, etc.
    message TEXT NOT NULL,
    recipients_count INT DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    FOREIGN KEY (sender_agent_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_team_messages_sender ON team_messages(sender_agent_id);
CREATE INDEX idx_team_messages_created ON team_messages(created_at);


-- Table 6: Team Reports
-- Stores generated team performance reports
CREATE TABLE IF NOT EXISTS team_reports (
    id VARCHAR(255) PRIMARY KEY,
    agent_id UUID NOT NULL,
    report_period VARCHAR(50) NOT NULL,  -- daily, weekly, monthly
    report_url TEXT,
    report_data JSONB,
    generated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    FOREIGN KEY (agent_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_team_reports_agent ON team_reports(agent_id);
CREATE INDEX idx_team_reports_period ON team_reports(report_period);
CREATE INDEX idx_team_reports_generated ON team_reports(generated_at);


-- ============================================================================
-- Materialized Views for Performance Optimization
-- ============================================================================

-- Materialized View 1: Hierarchy Leaderboard
-- Top agents by downline count and override commission
CREATE MATERIALIZED VIEW IF NOT EXISTS hierarchy_leaderboard AS
SELECT 
    tp.agent_id,
    u.full_name,
    u.phone_number,
    ah.hierarchy_level,
    tp.total_downline_agents,
    tp.level_1_count,
    tp.total_override_commission,
    RANK() OVER (ORDER BY tp.total_downline_agents DESC, tp.total_override_commission DESC) as rank
FROM team_performance tp
JOIN users u ON tp.agent_id = u.id
JOIN agent_hierarchy ah ON tp.agent_id = ah.agent_id
WHERE tp.total_downline_agents > 0
ORDER BY tp.total_downline_agents DESC, tp.total_override_commission DESC
LIMIT 100;

CREATE UNIQUE INDEX idx_hierarchy_leaderboard_agent ON hierarchy_leaderboard(agent_id);


-- Materialized View 2: Monthly Override Commission Summary
-- Monthly override commission by agent
CREATE MATERIALIZED VIEW IF NOT EXISTS monthly_override_summary AS
SELECT 
    upline_agent_id,
    DATE_TRUNC('month', created_at) as month,
    COUNT(*) as commission_count,
    SUM(override_amount) as total_override_amount,
    AVG(override_amount) as avg_override_amount,
    MAX(override_amount) as max_override_amount
FROM override_commissions
GROUP BY upline_agent_id, DATE_TRUNC('month', created_at)
ORDER BY month DESC, total_override_amount DESC;

CREATE INDEX idx_monthly_override_summary_agent ON monthly_override_summary(upline_agent_id);
CREATE INDEX idx_monthly_override_summary_month ON monthly_override_summary(month);


-- ============================================================================
-- Functions and Triggers
-- ============================================================================

-- Function 1: Refresh Hierarchy Leaderboard
CREATE OR REPLACE FUNCTION refresh_hierarchy_leaderboard()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY hierarchy_leaderboard;
END;
$$ LANGUAGE plpgsql;


-- Function 2: Refresh Monthly Override Summary
CREATE OR REPLACE FUNCTION refresh_monthly_override_summary()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY monthly_override_summary;
END;
$$ LANGUAGE plpgsql;


-- Function 3: Calculate Total Downline Agents
-- Recursive function to count all downline agents
CREATE OR REPLACE FUNCTION calculate_total_downline(p_agent_id UUID)
RETURNS INT AS $$
DECLARE
    v_count INT;
BEGIN
    WITH RECURSIVE downline_tree AS (
        SELECT agent_id
        FROM agent_hierarchy
        WHERE upline_agent_id = p_agent_id
        
        UNION ALL
        
        SELECT ah.agent_id
        FROM agent_hierarchy ah
        INNER JOIN downline_tree dt ON ah.upline_agent_id = dt.agent_id
    )
    SELECT COUNT(*) INTO v_count FROM downline_tree;
    
    RETURN v_count;
END;
$$ LANGUAGE plpgsql;


-- Function 4: Get Upline Path
-- Returns array of upline agent IDs from root to agent
CREATE OR REPLACE FUNCTION get_upline_path(p_agent_id UUID)
RETURNS UUID[] AS $$
DECLARE
    v_path UUID[];
BEGIN
    WITH RECURSIVE upline_tree AS (
        SELECT agent_id, upline_agent_id, ARRAY[agent_id] as path
        FROM agent_hierarchy
        WHERE agent_id = p_agent_id
        
        UNION ALL
        
        SELECT ah.agent_id, ah.upline_agent_id, ah.agent_id || ut.path
        FROM agent_hierarchy ah
        INNER JOIN upline_tree ut ON ah.agent_id = ut.upline_agent_id
    )
    SELECT path INTO v_path FROM upline_tree WHERE upline_agent_id IS NULL;
    
    RETURN v_path;
END;
$$ LANGUAGE plpgsql;


-- Trigger 1: Auto-update Team Performance on New Recruitment
CREATE OR REPLACE FUNCTION update_team_performance_on_recruitment()
RETURNS TRIGGER AS $$
BEGIN
    -- Update upline agent's team performance
    IF NEW.upline_agent_id IS NOT NULL THEN
        INSERT INTO team_performance (agent_id, total_downline_agents, level_1_count)
        VALUES (NEW.upline_agent_id, 1, 1)
        ON CONFLICT (agent_id) DO UPDATE SET
            total_downline_agents = team_performance.total_downline_agents + 1,
            level_1_count = team_performance.level_1_count + 1,
            last_updated = NOW();
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_team_performance_on_recruitment
AFTER INSERT ON agent_hierarchy
FOR EACH ROW
EXECUTE FUNCTION update_team_performance_on_recruitment();


-- Trigger 2: Auto-update Team Performance on Override Commission
CREATE OR REPLACE FUNCTION update_team_performance_on_override()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE team_performance
    SET total_override_commission = total_override_commission + NEW.override_amount,
        last_updated = NOW()
    WHERE agent_id = NEW.upline_agent_id;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_team_performance_on_override
AFTER INSERT ON override_commissions
FOR EACH ROW
EXECUTE FUNCTION update_team_performance_on_override();


-- ============================================================================
-- Sample Data for Testing (Optional - Remove in Production)
-- ============================================================================

-- Insert sample hierarchy (3 levels)
-- INSERT INTO agent_hierarchy (agent_id, upline_agent_id, hierarchy_level, recruitment_date)
-- VALUES 
--     ('agent-001', NULL, 0, NOW()),  -- Root agent
--     ('agent-002', 'agent-001', 1, NOW()),  -- Level 1
--     ('agent-003', 'agent-001', 1, NOW()),  -- Level 1
--     ('agent-004', 'agent-002', 2, NOW()),  -- Level 2
--     ('agent-005', 'agent-002', 2, NOW());  -- Level 2


-- ============================================================================
-- Indexes for Query Performance
-- ============================================================================

-- Composite index for common queries
CREATE INDEX idx_agent_hierarchy_upline_level ON agent_hierarchy(upline_agent_id, hierarchy_level);
CREATE INDEX idx_override_commissions_upline_created ON override_commissions(upline_agent_id, created_at);


-- ============================================================================
-- Constraints and Validation
-- ============================================================================

-- Constraint: Prevent self-referencing (agent cannot be their own upline)
ALTER TABLE agent_hierarchy 
ADD CONSTRAINT chk_no_self_reference 
CHECK (agent_id != upline_agent_id);

-- Constraint: Hierarchy level must be non-negative
ALTER TABLE agent_hierarchy 
ADD CONSTRAINT chk_hierarchy_level_positive 
CHECK (hierarchy_level >= 0);

-- Constraint: Override percentage must be between 0 and 100
ALTER TABLE override_commissions 
ADD CONSTRAINT chk_override_percentage_valid 
CHECK (override_percentage >= 0 AND override_percentage <= 100);

-- Constraint: Override amount must be non-negative
ALTER TABLE override_commissions 
ADD CONSTRAINT chk_override_amount_positive 
CHECK (override_amount >= 0);


-- ============================================================================
-- Grant Permissions (Adjust for Your Environment)
-- ============================================================================

-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO workflow_service;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO workflow_service;
-- GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO workflow_service;


-- ============================================================================
-- Migration Complete
-- ============================================================================

SELECT 'Agent Hierarchy migration completed successfully' AS status;

-- Display table statistics
SELECT 
    'agent_hierarchy' as table_name,
    COUNT(*) as row_count
FROM agent_hierarchy
UNION ALL
SELECT 
    'override_commissions' as table_name,
    COUNT(*) as row_count
FROM override_commissions
UNION ALL
SELECT 
    'team_performance' as table_name,
    COUNT(*) as row_count
FROM team_performance;

