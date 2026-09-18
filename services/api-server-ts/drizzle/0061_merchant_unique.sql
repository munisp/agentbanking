-- 0061_merchant_unique.sql
-- DB-level uniqueness for merchant registrations: prevent duplicate ACTIVE or
-- PENDING merchants per (tenant, business registration number) and per
-- (tenant, owner user). Partial unique indexes so historical closed/suspended
-- records do not conflict.

-- Duplicate active/pending merchant per tenant + business registration number
CREATE UNIQUE INDEX IF NOT EXISTS merchants_tenant_rc_active_uniq
    ON merchants ("tenantId", "rcNumber")
    WHERE status IN ('pending', 'active')
      AND "deletedAt" IS NULL
      AND "rcNumber" IS NOT NULL;

-- Duplicate active/pending merchant per tenant + owner user (keycloak sub)
CREATE UNIQUE INDEX IF NOT EXISTS merchants_tenant_owner_active_uniq
    ON merchants ("tenantId", "keycloakSub")
    WHERE status IN ('pending', 'active')
      AND "deletedAt" IS NULL
      AND "keycloakSub" IS NOT NULL;
