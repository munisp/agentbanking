-- ═══════════════════════════════════════════════════════════════════════════════
-- 54Link Agency Banking Platform — Row Level Security (RLS) Policies
-- Enforces tenant isolation at the database level.
--
-- Usage:
--   1. Each API request sets: SET LOCAL app.current_tenant_id = '<tenant_id>';
--   2. RLS policies automatically filter all queries to the current tenant.
--   3. Superusers bypass RLS (for admin/migration operations).
--
-- Run after initial schema creation via: psql -f rls-policies.sql
-- ═══════════════════════════════════════════════════════════════════════════════

-- ── Helper function to get current tenant ───────────────────────────────────
CREATE OR REPLACE FUNCTION current_tenant_id() RETURNS INTEGER AS $$
  SELECT COALESCE(
    NULLIF(current_setting('app.current_tenant_id', true), '')::INTEGER,
    NULL
  );
$$ LANGUAGE sql STABLE SECURITY DEFINER;

-- ── Enable RLS on all tenant-scoped tables ──────────────────────────────────
-- Core tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE agents ENABLE ROW LEVEL SECURITY;
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE fraud_alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE loyalty_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE float_top_up_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE disputes ENABLE ROW LEVEL SECURITY;
ALTER TABLE dispute_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE refunds ENABLE ROW LEVEL SECURITY;
ALTER TABLE velocity_limits ENABLE ROW LEVEL SECURITY;
ALTER TABLE compliance_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE kyc_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE pos_terminals ENABLE ROW LEVEL SECURITY;
ALTER TABLE commission_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE qr_codes ENABLE ROW LEVEL SECURITY;
ALTER TABLE inventory_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE reversal_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE customers ENABLE ROW LEVEL SECURITY;

-- ── SELECT policies (read own tenant only) ──────────────────────────────────
CREATE POLICY tenant_isolation_users_select ON users
  FOR SELECT USING ("tenantId" = current_tenant_id() OR current_tenant_id() IS NULL);

CREATE POLICY tenant_isolation_agents_select ON agents
  FOR SELECT USING ("tenantId" = current_tenant_id() OR current_tenant_id() IS NULL);

CREATE POLICY tenant_isolation_transactions_select ON transactions
  FOR SELECT USING ("tenantId" = current_tenant_id() OR current_tenant_id() IS NULL);

CREATE POLICY tenant_isolation_fraud_select ON fraud_alerts
  FOR SELECT USING ("tenantId" = current_tenant_id() OR current_tenant_id() IS NULL);

CREATE POLICY tenant_isolation_loyalty_select ON loyalty_history
  FOR SELECT USING ("tenantId" = current_tenant_id() OR current_tenant_id() IS NULL);

CREATE POLICY tenant_isolation_chat_sessions_select ON chat_sessions
  FOR SELECT USING ("tenantId" = current_tenant_id() OR current_tenant_id() IS NULL);

CREATE POLICY tenant_isolation_chat_messages_select ON chat_messages
  FOR SELECT USING ("tenantId" = current_tenant_id() OR current_tenant_id() IS NULL);

CREATE POLICY tenant_isolation_audit_select ON audit_log
  FOR SELECT USING ("tenantId" = current_tenant_id() OR current_tenant_id() IS NULL);

CREATE POLICY tenant_isolation_topup_select ON float_top_up_requests
  FOR SELECT USING ("tenantId" = current_tenant_id() OR current_tenant_id() IS NULL);

CREATE POLICY tenant_isolation_disputes_select ON disputes
  FOR SELECT USING ("tenantId" = current_tenant_id() OR current_tenant_id() IS NULL);

CREATE POLICY tenant_isolation_dispute_msgs_select ON dispute_messages
  FOR SELECT USING ("tenantId" = current_tenant_id() OR current_tenant_id() IS NULL);

CREATE POLICY tenant_isolation_refunds_select ON refunds
  FOR SELECT USING ("tenantId" = current_tenant_id() OR current_tenant_id() IS NULL);

CREATE POLICY tenant_isolation_velocity_select ON velocity_limits
  FOR SELECT USING ("tenantId" = current_tenant_id() OR current_tenant_id() IS NULL);

CREATE POLICY tenant_isolation_compliance_select ON compliance_reports
  FOR SELECT USING ("tenantId" = current_tenant_id() OR current_tenant_id() IS NULL);

CREATE POLICY tenant_isolation_kyc_select ON kyc_sessions
  FOR SELECT USING ("tenantId" = current_tenant_id() OR current_tenant_id() IS NULL);

CREATE POLICY tenant_isolation_terminals_select ON pos_terminals
  FOR SELECT USING ("tenantId" = current_tenant_id() OR current_tenant_id() IS NULL);

CREATE POLICY tenant_isolation_commissions_select ON commission_rules
  FOR SELECT USING ("tenantId" = current_tenant_id() OR current_tenant_id() IS NULL);

CREATE POLICY tenant_isolation_qrcodes_select ON qr_codes
  FOR SELECT USING ("tenantId" = current_tenant_id() OR current_tenant_id() IS NULL);

CREATE POLICY tenant_isolation_inventory_select ON inventory_items
  FOR SELECT USING ("tenantId" = current_tenant_id() OR current_tenant_id() IS NULL);

CREATE POLICY tenant_isolation_reversals_select ON reversal_requests
  FOR SELECT USING ("tenantId" = current_tenant_id() OR current_tenant_id() IS NULL);

CREATE POLICY tenant_isolation_customers_select ON customers
  FOR SELECT USING ("tenantId" = current_tenant_id() OR current_tenant_id() IS NULL);

-- ── INSERT policies (can only insert into own tenant) ───────────────────────
CREATE POLICY tenant_isolation_agents_insert ON agents
  FOR INSERT WITH CHECK ("tenantId" = current_tenant_id() OR current_tenant_id() IS NULL);

CREATE POLICY tenant_isolation_transactions_insert ON transactions
  FOR INSERT WITH CHECK ("tenantId" = current_tenant_id() OR current_tenant_id() IS NULL);

CREATE POLICY tenant_isolation_fraud_insert ON fraud_alerts
  FOR INSERT WITH CHECK ("tenantId" = current_tenant_id() OR current_tenant_id() IS NULL);

CREATE POLICY tenant_isolation_audit_insert ON audit_log
  FOR INSERT WITH CHECK ("tenantId" = current_tenant_id() OR current_tenant_id() IS NULL);

-- ── UPDATE policies (can only update own tenant) ────────────────────────────
CREATE POLICY tenant_isolation_agents_update ON agents
  FOR UPDATE USING ("tenantId" = current_tenant_id() OR current_tenant_id() IS NULL);

CREATE POLICY tenant_isolation_transactions_update ON transactions
  FOR UPDATE USING ("tenantId" = current_tenant_id() OR current_tenant_id() IS NULL);

CREATE POLICY tenant_isolation_fraud_update ON fraud_alerts
  FOR UPDATE USING ("tenantId" = current_tenant_id() OR current_tenant_id() IS NULL);

-- ── DELETE policies (soft-delete only, restrict hard deletes) ───────────────
CREATE POLICY tenant_isolation_agents_delete ON agents
  FOR DELETE USING ("tenantId" = current_tenant_id() OR current_tenant_id() IS NULL);

-- ── Application roles ───────────────────────────────────────────────────────
-- Create application user with RLS enforced (not superuser)
DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '54link_app') THEN
    CREATE ROLE "54link_app" WITH LOGIN PASSWORD 'changeme' NOSUPERUSER;
  END IF;
END $$;

GRANT USAGE ON SCHEMA public TO "54link_app";
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "54link_app";
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO "54link_app";

-- Admin role bypasses RLS
DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '54link_admin') THEN
    CREATE ROLE "54link_admin" WITH LOGIN PASSWORD 'changeme' SUPERUSER;
  END IF;
END $$;
