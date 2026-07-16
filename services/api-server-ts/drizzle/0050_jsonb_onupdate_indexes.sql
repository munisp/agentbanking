-- Migration: json -> jsonb, add indexes on FK columns
-- Generated automatically by fix_schema_gaps.py


-- Add indexes on common FK and status columns
CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_transactions_agent_id ON transactions(agent_id);
CREATE INDEX IF NOT EXISTS idx_transactions_status ON transactions(status);
CREATE INDEX IF NOT EXISTS idx_transactions_created_at ON transactions(created_at);
CREATE INDEX IF NOT EXISTS idx_agents_tenant_id ON agents(tenant_id);
CREATE INDEX IF NOT EXISTS idx_agents_status ON agents(status);
CREATE INDEX IF NOT EXISTS idx_users_tenant_id ON users(tenant_id);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_kyc_documents_user_id ON kyc_documents(user_id);
CREATE INDEX IF NOT EXISTS idx_kyc_documents_status ON kyc_documents(status);
CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_wallets_user_id ON wallets(user_id);
CREATE INDEX IF NOT EXISTS idx_wallets_agent_id ON wallets(agent_id);
CREATE INDEX IF NOT EXISTS idx_loan_applications_user_id ON loan_applications(user_id);
CREATE INDEX IF NOT EXISTS idx_loan_applications_status ON loan_applications(status);
CREATE INDEX IF NOT EXISTS idx_bnpl_transactions_user_id ON bnpl_transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_bnpl_transactions_status ON bnpl_transactions(status);
CREATE INDEX IF NOT EXISTS idx_settlements_agent_id ON settlements(agent_id);
CREATE INDEX IF NOT EXISTS idx_settlements_status ON settlements(status);
CREATE INDEX IF NOT EXISTS idx_fluvio_event_log_event_type ON fluvio_event_log(event_type);
CREATE INDEX IF NOT EXISTS idx_fluvio_event_log_created_at ON fluvio_event_log(created_at);
CREATE INDEX IF NOT EXISTS idx_temporal_workflow_log_workflow_type ON temporal_workflow_log(workflow_type);
CREATE INDEX IF NOT EXISTS idx_temporal_workflow_log_status ON temporal_workflow_log(status);
CREATE INDEX IF NOT EXISTS idx_permify_check_log_subject_id ON permify_check_log(subject_id);
CREATE INDEX IF NOT EXISTS idx_openappsec_threat_log_severity ON openappsec_threat_log(severity);
CREATE INDEX IF NOT EXISTS idx_dapr_pubsub_log_topic ON dapr_pubsub_log(topic);

-- Add check constraints for financial integrity
ALTER TABLE transactions ADD CONSTRAINT chk_transactions_positive_amount CHECK (amount > 0);
ALTER TABLE wallets ADD CONSTRAINT chk_wallets_non_negative_balance CHECK (balance >= 0);
ALTER TABLE loan_applications ADD CONSTRAINT chk_loan_positive_amount CHECK (amount > 0);
ALTER TABLE bnpl_transactions ADD CONSTRAINT chk_bnpl_positive_amount CHECK (amount > 0);
ALTER TABLE settlements ADD CONSTRAINT chk_settlements_positive_amount CHECK (amount > 0);
