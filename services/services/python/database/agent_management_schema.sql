-- Remittance Platform - Complete Agent Management Database Schema
-- Implements hierarchical agent structure and comprehensive commission system

-- Create extension for UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "postgis" CASCADE;

-- =====================================================
-- AGENT MANAGEMENT TABLES
-- =====================================================

-- Agent Tiers Enum
CREATE TYPE agent_tier AS ENUM ('super_agent', 'senior_agent', 'agent', 'sub_agent', 'trainee');
CREATE TYPE agent_status AS ENUM ('active', 'inactive', 'suspended', 'pending_approval', 'terminated');
CREATE TYPE kyc_status AS ENUM ('not_started', 'in_progress', 'completed', 'rejected', 'expired');

-- Main Agents Table
CREATE TABLE agents (
    id VARCHAR(50) PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    phone VARCHAR(20) UNIQUE NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    middle_name VARCHAR(100),
    date_of_birth DATE,
    gender VARCHAR(10),
    
    -- Agent Hierarchy
    tier agent_tier NOT NULL DEFAULT 'agent',
    parent_agent_id VARCHAR(50) REFERENCES agents(id),
    hierarchy_level INTEGER DEFAULT 1,
    territory_id UUID,
    
    -- Status and Verification
    status agent_status DEFAULT 'pending_approval',
    kyc_status kyc_status DEFAULT 'not_started',
    kyc_completed_at TIMESTAMP,
    
    -- Contact Information
    address JSONB,
    emergency_contact JSONB,
    
    -- Business Information
    business_name VARCHAR(200),
    business_registration_number VARCHAR(100),
    tax_identification_number VARCHAR(100),
    
    -- Banking Information
    bank_account_number VARCHAR(50),
    bank_name VARCHAR(100),
    bank_routing_number VARCHAR(20),
    
    -- Operational Data
    max_transaction_limit DECIMAL(15,2) DEFAULT 100000.00,
    daily_transaction_limit DECIMAL(15,2) DEFAULT 500000.00,
    monthly_transaction_limit DECIMAL(15,2) DEFAULT 10000000.00,
    
    -- Metadata
    onboarding_completed_at TIMESTAMP,
    last_login_at TIMESTAMP,
    created_by VARCHAR(50),
    approved_by VARCHAR(50),
    approved_at TIMESTAMP,
    
    -- Audit Fields
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT agents_hierarchy_level_check CHECK (hierarchy_level >= 1 AND hierarchy_level <= 10)
);

-- Agent Territories Table
CREATE TABLE agent_territories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(200) NOT NULL,
    code VARCHAR(20) UNIQUE NOT NULL,
    description TEXT,
    
    -- Geographic Data
    country VARCHAR(100) NOT NULL,
    state_province VARCHAR(100),
    city VARCHAR(100),
    postal_code VARCHAR(20),
    coordinates POINT,
    boundary POLYGON,
    
    -- Hierarchy
    parent_territory_id UUID REFERENCES agent_territories(id),
    territory_level INTEGER DEFAULT 1,
    
    -- Operational Data
    max_agents INTEGER DEFAULT 100,
    current_agent_count INTEGER DEFAULT 0,
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Audit Fields
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Agent Hierarchy Relationships (Materialized Path for efficient queries)
CREATE TABLE agent_hierarchy (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id VARCHAR(50) NOT NULL REFERENCES agents(id),
    ancestor_id VARCHAR(50) NOT NULL REFERENCES agents(id),
    depth INTEGER NOT NULL,
    path TEXT NOT NULL,
    
    -- Audit Fields
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(agent_id, ancestor_id)
);

-- Agent Documents Table
CREATE TABLE agent_documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id VARCHAR(50) NOT NULL REFERENCES agents(id),
    document_type VARCHAR(50) NOT NULL,
    document_name VARCHAR(200) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    file_size INTEGER,
    mime_type VARCHAR(100),
    
    -- Verification Status
    verification_status VARCHAR(20) DEFAULT 'pending',
    verified_by VARCHAR(50),
    verified_at TIMESTAMP,
    verification_notes TEXT,
    
    -- Document Metadata
    document_number VARCHAR(100),
    issue_date DATE,
    expiry_date DATE,
    issuing_authority VARCHAR(200),
    
    -- Audit Fields
    uploaded_by VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- COMMISSION SYSTEM TABLES
-- =====================================================

-- Commission Types and Structures
CREATE TYPE commission_type AS ENUM ('percentage', 'fixed', 'tiered', 'hybrid');
CREATE TYPE commission_frequency AS ENUM ('per_transaction', 'daily', 'weekly', 'monthly');
CREATE TYPE payout_status AS ENUM ('pending', 'processing', 'completed', 'failed', 'cancelled');

-- Commission Rules Table
CREATE TABLE commission_rules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    rule_name VARCHAR(200) NOT NULL,
    description TEXT,
    
    -- Rule Criteria
    agent_tier agent_tier,
    transaction_type VARCHAR(50),
    transaction_channel VARCHAR(50),
    min_amount DECIMAL(15,2),
    max_amount DECIMAL(15,2),
    territory_id UUID REFERENCES agent_territories(id),
    
    -- Commission Structure
    commission_type commission_type NOT NULL,
    commission_value DECIMAL(10,4) NOT NULL,
    fixed_amount DECIMAL(15,2),
    percentage_rate DECIMAL(5,4),
    
    -- Tiered Commission (JSON structure for complex tiers)
    tier_structure JSONB,
    
    -- Frequency and Limits
    frequency commission_frequency DEFAULT 'per_transaction',
    max_commission_per_transaction DECIMAL(15,2),
    max_commission_per_day DECIMAL(15,2),
    max_commission_per_month DECIMAL(15,2),
    
    -- Hierarchy Commission (for super agents)
    hierarchy_commission_enabled BOOLEAN DEFAULT FALSE,
    hierarchy_commission_rate DECIMAL(5,4),
    hierarchy_max_levels INTEGER DEFAULT 1,
    
    -- Rule Status and Validity
    is_active BOOLEAN DEFAULT TRUE,
    effective_from TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    effective_until TIMESTAMP,
    priority INTEGER DEFAULT 100,
    
    -- Audit Fields
    created_by VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Commission Calculations Table (Real-time commission tracking)
CREATE TABLE commission_calculations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    transaction_id VARCHAR(100) NOT NULL,
    agent_id VARCHAR(50) NOT NULL REFERENCES agents(id),
    rule_id UUID NOT NULL REFERENCES commission_rules(id),
    
    -- Transaction Details
    transaction_amount DECIMAL(15,2) NOT NULL,
    transaction_type VARCHAR(50) NOT NULL,
    transaction_channel VARCHAR(50),
    transaction_date TIMESTAMP NOT NULL,
    
    -- Commission Calculation
    commission_amount DECIMAL(15,2) NOT NULL,
    commission_rate DECIMAL(5,4),
    calculation_method VARCHAR(50) NOT NULL,
    calculation_details JSONB,
    
    -- Hierarchy Commission (if applicable)
    parent_agent_id VARCHAR(50) REFERENCES agents(id),
    parent_commission_amount DECIMAL(15,2) DEFAULT 0.00,
    hierarchy_level INTEGER,
    
    -- Status and Processing
    status VARCHAR(20) DEFAULT 'calculated',
    processed_at TIMESTAMP,
    included_in_payout_id UUID,
    
    -- Audit Fields
    calculated_by VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_commission_calculations_agent_date (agent_id, transaction_date),
    INDEX idx_commission_calculations_transaction (transaction_id),
    INDEX idx_commission_calculations_status (status)
);

-- Commission Payouts Table
CREATE TABLE commission_payouts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    payout_reference VARCHAR(100) UNIQUE NOT NULL,
    agent_id VARCHAR(50) NOT NULL REFERENCES agents(id),
    
    -- Payout Period
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    payout_frequency VARCHAR(20) NOT NULL,
    
    -- Payout Amounts
    gross_commission DECIMAL(15,2) NOT NULL,
    tax_amount DECIMAL(15,2) DEFAULT 0.00,
    deductions DECIMAL(15,2) DEFAULT 0.00,
    net_payout DECIMAL(15,2) NOT NULL,
    
    -- Transaction Summary
    transaction_count INTEGER NOT NULL,
    total_transaction_volume DECIMAL(15,2) NOT NULL,
    commission_rate_avg DECIMAL(5,4),
    
    -- Payout Details
    payout_method VARCHAR(50) DEFAULT 'bank_transfer',
    bank_account_number VARCHAR(50),
    bank_name VARCHAR(100),
    payout_reference_external VARCHAR(200),
    
    -- Status and Processing
    status payout_status DEFAULT 'pending',
    scheduled_date DATE,
    processed_date DATE,
    completed_date DATE,
    failure_reason TEXT,
    
    -- Approval Workflow
    approved_by VARCHAR(50),
    approved_at TIMESTAMP,
    approval_notes TEXT,
    
    -- Audit Fields
    created_by VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_commission_payouts_agent_period (agent_id, period_start, period_end),
    INDEX idx_commission_payouts_status (status),
    INDEX idx_commission_payouts_scheduled (scheduled_date, status)
);

-- Commission Disputes Table
CREATE TABLE commission_disputes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    dispute_reference VARCHAR(100) UNIQUE NOT NULL,
    agent_id VARCHAR(50) NOT NULL REFERENCES agents(id),
    
    -- Dispute Details
    dispute_type VARCHAR(50) NOT NULL,
    related_transaction_id VARCHAR(100),
    related_payout_id UUID REFERENCES commission_payouts(id),
    related_calculation_id UUID REFERENCES commission_calculations(id),
    
    -- Dispute Information
    disputed_amount DECIMAL(15,2) NOT NULL,
    claimed_amount DECIMAL(15,2) NOT NULL,
    dispute_reason TEXT NOT NULL,
    supporting_documents JSONB,
    
    -- Resolution
    status VARCHAR(20) DEFAULT 'open',
    assigned_to VARCHAR(50),
    resolution TEXT,
    resolved_amount DECIMAL(15,2),
    resolved_at TIMESTAMP,
    resolution_notes TEXT,
    
    -- Audit Fields
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_commission_disputes_agent (agent_id),
    INDEX idx_commission_disputes_status (status)
);

-- =====================================================
-- AGENT ONBOARDING TABLES
-- =====================================================

CREATE TYPE onboarding_status AS ENUM ('not_started', 'in_progress', 'documents_pending', 'verification_pending', 'approved', 'rejected');
CREATE TYPE onboarding_step AS ENUM ('personal_info', 'business_info', 'documents_upload', 'kyc_verification', 'bank_details', 'territory_assignment', 'training_completion', 'final_approval');

-- Agent Onboarding Workflows Table
CREATE TABLE agent_onboarding (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id VARCHAR(50) NOT NULL REFERENCES agents(id),
    onboarding_reference VARCHAR(100) UNIQUE NOT NULL,
    
    -- Onboarding Status
    overall_status onboarding_status DEFAULT 'not_started',
    current_step onboarding_step DEFAULT 'personal_info',
    completion_percentage INTEGER DEFAULT 0,
    
    -- Step Completion Tracking
    steps_completed JSONB DEFAULT '[]',
    steps_data JSONB DEFAULT '{}',
    
    -- Workflow Metadata
    started_at TIMESTAMP,
    expected_completion_date DATE,
    actual_completion_date DATE,
    
    -- Assignment and Review
    assigned_reviewer VARCHAR(50),
    reviewed_by VARCHAR(50),
    reviewed_at TIMESTAMP,
    review_notes TEXT,
    
    -- Rejection/Approval Details
    rejection_reason TEXT,
    rejection_date TIMESTAMP,
    approval_date TIMESTAMP,
    approved_by VARCHAR(50),
    
    -- Audit Fields
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_agent_onboarding_status (overall_status),
    INDEX idx_agent_onboarding_agent (agent_id)
);

-- Agent Training and Certification Table
CREATE TABLE agent_training (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id VARCHAR(50) NOT NULL REFERENCES agents(id),
    
    -- Training Details
    training_module VARCHAR(100) NOT NULL,
    training_type VARCHAR(50) NOT NULL,
    training_provider VARCHAR(200),
    
    -- Progress and Completion
    status VARCHAR(20) DEFAULT 'not_started',
    progress_percentage INTEGER DEFAULT 0,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    
    -- Assessment and Certification
    assessment_score DECIMAL(5,2),
    passing_score DECIMAL(5,2) DEFAULT 70.00,
    certification_number VARCHAR(100),
    certification_expiry DATE,
    
    -- Training Materials
    training_materials JSONB,
    completion_certificate_path VARCHAR(500),
    
    -- Audit Fields
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_agent_training_agent (agent_id),
    INDEX idx_agent_training_status (status)
);

-- =====================================================
-- PERFORMANCE AND ANALYTICS TABLES
-- =====================================================

-- Agent Performance Metrics Table
CREATE TABLE agent_performance (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id VARCHAR(50) NOT NULL REFERENCES agents(id),
    
    -- Performance Period
    period_type VARCHAR(20) NOT NULL, -- 'daily', 'weekly', 'monthly', 'quarterly'
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    
    -- Transaction Metrics
    transaction_count INTEGER DEFAULT 0,
    transaction_volume DECIMAL(15,2) DEFAULT 0.00,
    avg_transaction_amount DECIMAL(15,2) DEFAULT 0.00,
    
    -- Commission Metrics
    gross_commission DECIMAL(15,2) DEFAULT 0.00,
    net_commission DECIMAL(15,2) DEFAULT 0.00,
    commission_rate_avg DECIMAL(5,4) DEFAULT 0.0000,
    
    -- Customer Metrics
    new_customers_acquired INTEGER DEFAULT 0,
    active_customers INTEGER DEFAULT 0,
    customer_retention_rate DECIMAL(5,2) DEFAULT 0.00,
    
    -- Quality Metrics
    success_rate DECIMAL(5,2) DEFAULT 0.00,
    error_rate DECIMAL(5,2) DEFAULT 0.00,
    dispute_count INTEGER DEFAULT 0,
    complaint_count INTEGER DEFAULT 0,
    
    -- Hierarchy Performance (for super agents)
    sub_agents_count INTEGER DEFAULT 0,
    sub_agents_performance JSONB,
    hierarchy_commission DECIMAL(15,2) DEFAULT 0.00,
    
    -- Rankings and Scores
    performance_score DECIMAL(5,2) DEFAULT 0.00,
    territory_rank INTEGER,
    tier_rank INTEGER,
    overall_rank INTEGER,
    
    -- Audit Fields
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(agent_id, period_type, period_start, period_end),
    INDEX idx_agent_performance_period (period_type, period_start, period_end),
    INDEX idx_agent_performance_score (performance_score DESC)
);

-- =====================================================
-- AUDIT AND LOGGING TABLES
-- =====================================================

-- Agent Activity Log Table
CREATE TABLE agent_activity_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id VARCHAR(50) NOT NULL REFERENCES agents(id),
    
    -- Activity Details
    activity_type VARCHAR(50) NOT NULL,
    activity_description TEXT NOT NULL,
    activity_data JSONB,
    
    -- Context Information
    ip_address INET,
    user_agent TEXT,
    session_id VARCHAR(100),
    device_info JSONB,
    location_data JSONB,
    
    -- Result and Status
    result VARCHAR(20) DEFAULT 'success',
    error_message TEXT,
    
    -- Audit Fields
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_agent_activity_log_agent_time (agent_id, timestamp),
    INDEX idx_agent_activity_log_type (activity_type),
    INDEX idx_agent_activity_log_result (result)
);

-- System Configuration Table
CREATE TABLE agent_system_config (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    config_key VARCHAR(100) UNIQUE NOT NULL,
    config_value JSONB NOT NULL,
    config_description TEXT,
    
    -- Configuration Metadata
    is_active BOOLEAN DEFAULT TRUE,
    requires_restart BOOLEAN DEFAULT FALSE,
    
    -- Audit Fields
    created_by VARCHAR(50),
    updated_by VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- INDEXES FOR PERFORMANCE
-- =====================================================

-- Agent-related indexes
CREATE INDEX idx_agents_tier ON agents(tier);
CREATE INDEX idx_agents_status ON agents(status);
CREATE INDEX idx_agents_parent ON agents(parent_agent_id);
CREATE INDEX idx_agents_territory ON agents(territory_id);
CREATE INDEX idx_agents_hierarchy_level ON agents(hierarchy_level);
CREATE INDEX idx_agents_created_at ON agents(created_at);

-- Territory indexes
CREATE INDEX idx_agent_territories_parent ON agent_territories(parent_territory_id);
CREATE INDEX idx_agent_territories_level ON agent_territories(territory_level);
CREATE INDEX idx_agent_territories_active ON agent_territories(is_active);

-- Hierarchy indexes
CREATE INDEX idx_agent_hierarchy_agent ON agent_hierarchy(agent_id);
CREATE INDEX idx_agent_hierarchy_ancestor ON agent_hierarchy(ancestor_id);
CREATE INDEX idx_agent_hierarchy_depth ON agent_hierarchy(depth);

-- Commission rules indexes
CREATE INDEX idx_commission_rules_tier ON commission_rules(agent_tier);
CREATE INDEX idx_commission_rules_active ON commission_rules(is_active);
CREATE INDEX idx_commission_rules_effective ON commission_rules(effective_from, effective_until);
CREATE INDEX idx_commission_rules_priority ON commission_rules(priority);

-- =====================================================
-- FUNCTIONS AND TRIGGERS
-- =====================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers for updated_at
CREATE TRIGGER update_agents_updated_at BEFORE UPDATE ON agents FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_agent_territories_updated_at BEFORE UPDATE ON agent_territories FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_agent_hierarchy_updated_at BEFORE UPDATE ON agent_hierarchy FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_commission_rules_updated_at BEFORE UPDATE ON commission_rules FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_commission_calculations_updated_at BEFORE UPDATE ON commission_calculations FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_commission_payouts_updated_at BEFORE UPDATE ON commission_payouts FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_agent_onboarding_updated_at BEFORE UPDATE ON agent_onboarding FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function to maintain agent hierarchy
CREATE OR REPLACE FUNCTION maintain_agent_hierarchy()
RETURNS TRIGGER AS $$
BEGIN
    -- Delete existing hierarchy for this agent
    DELETE FROM agent_hierarchy WHERE agent_id = NEW.id;
    
    -- Insert self-reference
    INSERT INTO agent_hierarchy (agent_id, ancestor_id, depth, path)
    VALUES (NEW.id, NEW.id, 0, NEW.id);
    
    -- Insert hierarchy chain if parent exists
    IF NEW.parent_agent_id IS NOT NULL THEN
        INSERT INTO agent_hierarchy (agent_id, ancestor_id, depth, path)
        SELECT NEW.id, ancestor_id, depth + 1, path || '/' || NEW.id
        FROM agent_hierarchy
        WHERE agent_id = NEW.parent_agent_id;
        
        -- Update hierarchy level
        UPDATE agents 
        SET hierarchy_level = (
            SELECT MAX(depth) + 1 
            FROM agent_hierarchy 
            WHERE agent_id = NEW.id
        )
        WHERE id = NEW.id;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for agent hierarchy maintenance
CREATE TRIGGER maintain_agent_hierarchy_trigger 
    AFTER INSERT OR UPDATE OF parent_agent_id ON agents 
    FOR EACH ROW EXECUTE FUNCTION maintain_agent_hierarchy();

-- Function to update territory agent count
CREATE OR REPLACE FUNCTION update_territory_agent_count()
RETURNS TRIGGER AS $$
BEGIN
    -- Update old territory count
    IF OLD.territory_id IS NOT NULL THEN
        UPDATE agent_territories 
        SET current_agent_count = current_agent_count - 1
        WHERE id = OLD.territory_id;
    END IF;
    
    -- Update new territory count
    IF NEW.territory_id IS NOT NULL THEN
        UPDATE agent_territories 
        SET current_agent_count = current_agent_count + 1
        WHERE id = NEW.territory_id;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for territory agent count
CREATE TRIGGER update_territory_agent_count_trigger 
    AFTER UPDATE OF territory_id ON agents 
    FOR EACH ROW EXECUTE FUNCTION update_territory_agent_count();

-- =====================================================
-- INITIAL DATA SETUP
-- =====================================================

-- Insert default territories
INSERT INTO agent_territories (id, name, code, country, territory_level) VALUES
    (uuid_generate_v4(), 'Nigeria', 'NG', 'Nigeria', 1),
    (uuid_generate_v4(), 'Lagos State', 'NG-LA', 'Nigeria', 2),
    (uuid_generate_v4(), 'Abuja FCT', 'NG-FC', 'Nigeria', 2),
    (uuid_generate_v4(), 'Kano State', 'NG-KN', 'Nigeria', 2)
ON CONFLICT (code) DO NOTHING;

-- Insert default commission rules
INSERT INTO commission_rules (
    rule_name, description, agent_tier, transaction_type, 
    commission_type, commission_value, percentage_rate, 
    hierarchy_commission_enabled, hierarchy_commission_rate
) VALUES
    ('Super Agent - Deposits', 'Commission for super agent deposits', 'super_agent', 'deposit', 'percentage', 0.0050, 0.0050, TRUE, 0.0010),
    ('Super Agent - Withdrawals', 'Commission for super agent withdrawals', 'super_agent', 'withdrawal', 'percentage', 0.0030, 0.0030, TRUE, 0.0005),
    ('Senior Agent - Deposits', 'Commission for senior agent deposits', 'senior_agent', 'deposit', 'percentage', 0.0040, 0.0040, TRUE, 0.0008),
    ('Agent - Deposits', 'Commission for regular agent deposits', 'agent', 'deposit', 'percentage', 0.0030, 0.0030, FALSE, 0.0000),
    ('Sub Agent - Deposits', 'Commission for sub agent deposits', 'sub_agent', 'deposit', 'percentage', 0.0020, 0.0020, FALSE, 0.0000)
ON CONFLICT DO NOTHING;

-- Insert system configuration
INSERT INTO agent_system_config (config_key, config_value, config_description) VALUES
    ('max_hierarchy_levels', '5', 'Maximum allowed hierarchy levels'),
    ('commission_calculation_frequency', '"real_time"', 'How often to calculate commissions'),
    ('payout_schedule', '"monthly"', 'Default payout schedule'),
    ('min_payout_amount', '1000.00', 'Minimum amount for payout processing'),
    ('auto_approve_payouts', 'false', 'Whether to automatically approve payouts')
ON CONFLICT (config_key) DO NOTHING;

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO banking_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO banking_user;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO banking_user;

-- Create views for common queries
CREATE OR REPLACE VIEW agent_hierarchy_view AS
SELECT 
    a.id,
    a.first_name || ' ' || a.last_name AS full_name,
    a.tier,
    a.status,
    a.hierarchy_level,
    p.first_name || ' ' || p.last_name AS parent_name,
    t.name AS territory_name,
    COUNT(sub.id) AS sub_agents_count
FROM agents a
LEFT JOIN agents p ON a.parent_agent_id = p.id
LEFT JOIN agent_territories t ON a.territory_id = t.id
LEFT JOIN agents sub ON sub.parent_agent_id = a.id
GROUP BY a.id, a.first_name, a.last_name, a.tier, a.status, a.hierarchy_level, p.first_name, p.last_name, t.name;

CREATE OR REPLACE VIEW commission_summary_view AS
SELECT 
    a.id AS agent_id,
    a.first_name || ' ' || a.last_name AS agent_name,
    a.tier,
    COUNT(cc.id) AS total_transactions,
    SUM(cc.commission_amount) AS total_commission,
    AVG(cc.commission_amount) AS avg_commission,
    SUM(cc.parent_commission_amount) AS hierarchy_commission
FROM agents a
LEFT JOIN commission_calculations cc ON a.id = cc.agent_id
WHERE cc.created_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY a.id, a.first_name, a.last_name, a.tier;

-- Create materialized view for performance metrics
CREATE MATERIALIZED VIEW agent_performance_summary AS
SELECT 
    a.id AS agent_id,
    a.first_name || ' ' || a.last_name AS agent_name,
    a.tier,
    a.status,
    t.name AS territory_name,
    COUNT(cc.id) AS monthly_transactions,
    SUM(cc.transaction_amount) AS monthly_volume,
    SUM(cc.commission_amount) AS monthly_commission,
    AVG(cc.commission_rate) AS avg_commission_rate,
    RANK() OVER (PARTITION BY a.tier ORDER BY SUM(cc.commission_amount) DESC) AS tier_rank
FROM agents a
LEFT JOIN agent_territories t ON a.territory_id = t.id
LEFT JOIN commission_calculations cc ON a.id = cc.agent_id 
    AND cc.transaction_date >= DATE_TRUNC('month', CURRENT_DATE)
GROUP BY a.id, a.first_name, a.last_name, a.tier, a.status, t.name;

-- Create index on materialized view
CREATE INDEX idx_agent_performance_summary_tier ON agent_performance_summary(tier);
CREATE INDEX idx_agent_performance_summary_rank ON agent_performance_summary(tier_rank);

-- Refresh materialized view (should be done periodically)
REFRESH MATERIALIZED VIEW agent_performance_summary;

COMMENT ON DATABASE remittance IS 'Remittance Platform - Complete Agent Management and Commission System Database';
