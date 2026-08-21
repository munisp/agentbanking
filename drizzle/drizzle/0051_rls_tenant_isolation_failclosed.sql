-- ─────────────────────────────────────────────────────────────────────────────
-- Migration 0051: RLS tenant isolation — fail closed (FF-20)
--
-- Migration 0048 created "<table>_tenant_isolation" policies with a fail-open
-- escape hatch:
--
--     OR _54link_current_tenant_id() IS NULL
--
-- When the request context forgets to SET app.current_tenant_id (or the
-- function errors and returns NULL), that clause evaluates TRUE and the policy
-- exposes EVERY tenant's rows. This migration recreates the affected policies
-- WITHOUT the NULL escape: with no tenant context set, the strict predicate
-- "tenantId" = _54link_current_tenant_id() matches nothing, so queries fail
-- closed instead of leaking cross-tenant data. Rows whose "tenantId" IS NULL
-- (unowned/shared rows) remain visible exactly as before.
-- ─────────────────────────────────────────────────────────────────────────────

DO $$
DECLARE
  tbl TEXT;
  tenant_tables TEXT[] := ARRAY[
    'agents', 'transactions', 'fraud_alerts', 'customers',
    'float_top_up_requests', 'disputes', 'kyc_sessions',
    'commission_rules', 'commission_payouts', 'pos_terminals',
    'devices', 'merchants', 'referrals', 'agent_loans',
    'fee_rules', 'webhook_endpoints', 'api_keys',
    'ecommerce_products', 'ecommerce_orders', 'agent_stores'
  ];
BEGIN
  FOREACH tbl IN ARRAY tenant_tables LOOP
    IF EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_name = tbl AND column_name = 'tenantId'
    ) THEN
      EXECUTE format('ALTER TABLE "%s" ENABLE ROW LEVEL SECURITY;', tbl);
      EXECUTE format('ALTER TABLE "%s" FORCE ROW LEVEL SECURITY;', tbl);

      -- Drop the fail-open policy created by migration 0048
      EXECUTE format(
        'DROP POLICY IF EXISTS "%s_tenant_isolation" ON "%s";', tbl, tbl
      );

      -- Tenant isolation (strict): only see own rows, or rows with no tenant.
      -- No escape for a missing/NULL tenant context — fail closed.
      EXECUTE format(
        'CREATE POLICY "%s_tenant_isolation" ON "%s"
         USING (
           "tenantId" IS NULL
           OR "tenantId" = _54link_current_tenant_id()
         )
         WITH CHECK (
           "tenantId" IS NULL
           OR "tenantId" = _54link_current_tenant_id()
         );',
        tbl, tbl
      );
    END IF;
  END LOOP;
END;
$$;
--> statement-breakpoint
