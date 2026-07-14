-- Create workflows table
CREATE TABLE IF NOT EXISTS workflows (
    id UUID PRIMARY KEY,
    workflow_id VARCHAR(255) UNIQUE NOT NULL,
    workflow_type VARCHAR(100) NOT NULL,
    status VARCHAR(50) NOT NULL,
    tenant_id VARCHAR(255),
    user_id VARCHAR(255),
    entity_id VARCHAR(255),
    input_data JSONB,
    output_data JSONB,
    context JSONB,
    current_step VARCHAR(255),
    total_steps INTEGER DEFAULT 0,
    completed_steps INTEGER DEFAULT 0,
    failed_steps INTEGER DEFAULT 0,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    failed_at TIMESTAMP,
    duration_seconds DOUBLE PRECISION DEFAULT 0,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX idx_workflows_workflow_id ON workflows(workflow_id);
CREATE INDEX idx_workflows_status ON workflows(status);
CREATE INDEX idx_workflows_workflow_type ON workflows(workflow_type);
CREATE INDEX idx_workflows_tenant_id ON workflows(tenant_id);
CREATE INDEX idx_workflows_user_id ON workflows(user_id);
CREATE INDEX idx_workflows_created_at ON workflows(created_at DESC);

-- Create workflow_steps table
CREATE TABLE IF NOT EXISTS workflow_steps (
    id UUID PRIMARY KEY,
    step_id VARCHAR(255) UNIQUE NOT NULL,
    workflow_id VARCHAR(255) NOT NULL REFERENCES workflows(workflow_id),
    step_name VARCHAR(255) NOT NULL,
    step_type VARCHAR(100) NOT NULL,
    step_order INTEGER NOT NULL,
    status VARCHAR(50) NOT NULL,
    service_url VARCHAR(500),
    endpoint VARCHAR(500),
    input_data JSONB,
    output_data JSONB,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    duration_seconds DOUBLE PRECISION DEFAULT 0,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for workflow_steps
CREATE INDEX idx_workflow_steps_workflow_id ON workflow_steps(workflow_id);
CREATE INDEX idx_workflow_steps_status ON workflow_steps(status);
CREATE INDEX idx_workflow_steps_step_order ON workflow_steps(workflow_id, step_order);

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers
CREATE TRIGGER update_workflows_updated_at BEFORE UPDATE ON workflows
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_workflow_steps_updated_at BEFORE UPDATE ON workflow_steps
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

