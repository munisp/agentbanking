import api from "@/services/api";
import { useCallback, useEffect, useRef, useState } from "react";

// ─── localStorage helpers ────────────────────────────────────────────────────

function storageKey(userId: string, tenantId: string) {
  return `permify_cache:${userId}:${tenantId}`;
}

function resolveCurrentUserId(): string {
  const direct = localStorage.getItem("keycloak_id");
  if (direct) return direct;
  for (const key of ["admin_data", "auth_user"]) {
    try {
      const obj = JSON.parse(localStorage.getItem(key) || "{}");
      if (obj.keycloak_id) return obj.keycloak_id;
    } catch {}
  }
  return "";
}

function resolveTenantId(): string {
  if (import.meta.env.VITE_TENANT_ID) return import.meta.env.VITE_TENANT_ID as string;
  const direct = localStorage.getItem("tenant_id");
  if (direct) return direct;
  try {
    const raw = localStorage.getItem("tenant_config");
    if (raw) {
      const parsed = JSON.parse(raw);
      const config = parsed.tenant || parsed;
      if (config.tenant_id) return config.tenant_id;
    }
  } catch {}
  return "bpmgd";
}

function loadFromStorage(userId: string, tenantId: string): Map<string, boolean> {
  if (!userId || !tenantId) return new Map();
  try {
    const raw = localStorage.getItem(storageKey(userId, tenantId));
    return raw ? new Map(JSON.parse(raw) as [string, boolean][]) : new Map();
  } catch {
    return new Map();
  }
}

function persistToStorage(cache: Map<string, boolean>, userId: string, tenantId: string) {
  if (!userId || !tenantId) return;
  try {
    localStorage.setItem(storageKey(userId, tenantId), JSON.stringify([...cache]));
  } catch {}
}

// ─── All permissions to pre-load on mount ────────────────────────────────────

const ALL_PERMISSIONS = [
  { resourceType: "tenants", permission: "view_all_data" },
  { resourceType: "tenants", permission: "view_branch_data" },
  { resourceType: "tenants", permission: "manage_employees" },
  { resourceType: "tenants", permission: "manage_customers" },
  { resourceType: "tenants", permission: "suspend_or_reactivate_customers" },
  { resourceType: "tenants", permission: "verify_kyc" },
  { resourceType: "tenants", permission: "teller_actions" },
  { resourceType: "tenants", permission: "teller_management" },
  { resourceType: "tenants", permission: "vault_management" },
  { resourceType: "tenants", permission: "initiate_transactions" },
  { resourceType: "tenants", permission: "approve_or_reject" },
  { resourceType: "tenants", permission: "reverse_transactions" },
  { resourceType: "tenants", permission: "manage_transaction_limits" },
  { resourceType: "tenants", permission: "applications" },
  { resourceType: "tenants", permission: "approve_loans" },
  { resourceType: "tenants", permission: "manage_loan_limits" },
  { resourceType: "tenants", permission: "manage_esusu" },
  { resourceType: "tenants", permission: "islamic_banking" },
  { resourceType: "tenants", permission: "agric_banking" },
  { resourceType: "tenants", permission: "lpo_management" },
  { resourceType: "tenants", permission: "card_issuance" },
  { resourceType: "tenants", permission: "card_management" },
  { resourceType: "tenants", permission: "control_cards" },
  { resourceType: "tenants", permission: "dispute_management" },
  { resourceType: "tenants", permission: "view_audit_logs" },
  { resourceType: "tenants", permission: "export_audit_logs" },
  { resourceType: "tenants", permission: "flag_suspicious_activity" },
  { resourceType: "tenants", permission: "view_analytics" },
  { resourceType: "tenants", permission: "temporal_access_management" },
  { resourceType: "tenants", permission: "billing_management" },
  { resourceType: "tenants", permission: "coa_management" },
  { resourceType: "tenants", permission: "erp_management" },
  { resourceType: "tenants", permission: "communication_hub_management" },
  { resourceType: "tenants", permission: "emergency_override" },
  { resourceType: "platform", permission: "view_all_data" },
  { resourceType: "platform", permission: "manage_employees" },
  { resourceType: "platform", permission: "manage_tenants" },
  { resourceType: "platform", permission: "provide_support" },
  { resourceType: "platform", permission: "enable_features" },
  { resourceType: "platform", permission: "system_lockdown" },
];

// ─── Hook ────────────────────────────────────────────────────────────────────

/**
 * Permify permission hook for the 54link platform admin UI.
 *
 * Checks permissions against the v2.perm `platform` entity (and `tenants`
 * entity for tenant-scoped checks). Cache is pre-populated from localStorage
 * so hasPermission() is accurate on first render — no flash of hidden items.
 */
export function usePermissions() {
  const tenantId = resolveTenantId();
  const currentUserId = resolveCurrentUserId();

  const [permissionCache, setPermissionCache] = useState<Map<string, boolean>>(
    () => loadFromStorage(currentUserId, tenantId),
  );

  const cacheRef = useRef(permissionCache);
  useEffect(() => {
    cacheRef.current = permissionCache;
  }, [permissionCache]);

  const [loading, setLoading] = useState(false);
  const [initialLoading, setInitialLoading] = useState(() => {
    if (!currentUserId || !tenantId) return false;
    const cached = loadFromStorage(currentUserId, tenantId);
    return ALL_PERMISSIONS.some(
      ({ resourceType, permission }) =>
        !cached.has(`${resourceType}:${permission}:${tenantId}`),
    );
  });

  const writeEntry = useCallback(
    (key: string, value: boolean) => {
      setPermissionCache((prev) => {
        const next = new Map(prev).set(key, value);
        cacheRef.current = next;
        persistToStorage(next, currentUserId, tenantId);
        return next;
      });
    },
    [currentUserId, tenantId],
  );

  const checkPermission = useCallback(
    async (
      resourceType: string,
      permission: string,
      resourceId?: string,
    ): Promise<boolean> => {
      if (!currentUserId || !tenantId) return false;

      const key = `${resourceType}:${permission}:${resourceId || tenantId}`;

      if (cacheRef.current.has(key)) return cacheRef.current.get(key)!;

      setLoading(true);
      try {
        const response = await api.post(
          `/auth/permissions/check-permission`,
          null,
          {
            params: {
              permission,
              entity_type: resourceType,
              entity_id:  'bpmgd',
              user_id: currentUserId,
            },
          },
        );
        const hasAccess: boolean = response.data.has_permission || false;
        writeEntry(key, hasAccess);
        return hasAccess;
      } catch {
        return false;
      } finally {
        setLoading(false);
      }
    },
    [currentUserId, tenantId, writeEntry],
  );

  const hasPermission = useCallback(
    (resourceType: string, permission: string, resourceId?: string): boolean => {
      const key = `${resourceType}:${permission}:${resourceId || tenantId}`;
      return cacheRef.current.get(key) ?? false;
    },
    [tenantId],
  );

  const checkPermissions = useCallback(
    async (
      checks: Array<{ resourceType: string; permission: string; resourceId?: string }>,
    ): Promise<Map<string, boolean>> => {
      if (!currentUserId || !tenantId) return new Map();

      // Filter out already-cached checks
      const uncached = checks.filter(
        ({ resourceType, permission, resourceId }) =>
          !cacheRef.current.has(`${resourceType}:${permission}:${resourceId || tenantId}`),
      );

      if (uncached.length > 0) {
        setLoading(true);
        try {
          const response = await api.post(`/auth/permissions/check-permissions-batch`, {
            user_id: currentUserId,
            checks: uncached.map(({ resourceType, permission, resourceId }) => ({
              entity_type: resourceType,
              permission,
              entity_id: resourceId || 'bpmgd',
            })),
          });

          for (const item of response.data.results ?? []) {
            const key = `${item.entity_type}:${item.permission}:${item.entity_id}`;
            writeEntry(key, item.has_permission ?? false);
          }
        } catch {
          // fall back to false for uncached items; cached results still returned below
        } finally {
          setLoading(false);
        }
      }

      const results = new Map<string, boolean>();
      for (const { resourceType, permission, resourceId } of checks) {
        const key = `${resourceType}:${permission}:${resourceId || tenantId}`;
        results.set(`${resourceType}:${permission}`, cacheRef.current.get(key) ?? false);
      }
      return results;
    },
    [currentUserId, tenantId, writeEntry],
  );

  const clearCache = useCallback(() => {
    const empty = new Map<string, boolean>();
    cacheRef.current = empty;
    setPermissionCache(empty);
    try {
      localStorage.removeItem(storageKey(currentUserId, tenantId));
    } catch {}
  }, [currentUserId, tenantId]);

  // Pre-load all platform + tenant permissions on mount
  useEffect(() => {
    if (!currentUserId || !tenantId) return;

    const missing = ALL_PERMISSIONS.filter(
      ({ resourceType, permission }) =>
        !cacheRef.current.has(`${resourceType}:${permission}:${tenantId}`),
    );

    if (missing.length > 0) {
      setInitialLoading(true);
      checkPermissions(missing).finally(() => setInitialLoading(false));
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentUserId, tenantId]);

  return { checkPermission, hasPermission, checkPermissions, clearCache, loading, initialLoading, permissionCache };
}

// ─── Permission map ──────────────────────────────────────────────────────────

export const PERMISSION_MAP = {
  // ── tenants entity (mirrors tenant admin) ───────────────────────────────
  VIEW_ALL_DATA:             { resourceType: "tenants", permission: "view_all_data" },
  VIEW_BRANCH_DATA:          { resourceType: "tenants", permission: "view_branch_data" },
  MANAGE_EMPLOYEES:          { resourceType: "tenants", permission: "manage_employees" },
  MANAGE_CUSTOMERS:          { resourceType: "tenants", permission: "manage_customers" },
  SUSPEND_CUSTOMERS:         { resourceType: "tenants", permission: "suspend_or_reactivate_customers" },
  VERIFY_KYC:                { resourceType: "tenants", permission: "verify_kyc" },
  TELLER_ACTIONS:            { resourceType: "tenants", permission: "teller_actions" },
  TELLER_MANAGEMENT:         { resourceType: "tenants", permission: "teller_management" },
  VAULT_MANAGEMENT:          { resourceType: "tenants", permission: "vault_management" },
  INITIATE_TRANSACTIONS:     { resourceType: "tenants", permission: "initiate_transactions" },
  APPROVE_OR_REJECT:         { resourceType: "tenants", permission: "approve_or_reject" },
  REVERSE_TRANSACTIONS:      { resourceType: "tenants", permission: "reverse_transactions" },
  MANAGE_TRANSACTION_LIMITS: { resourceType: "tenants", permission: "manage_transaction_limits" },
  APPLICATIONS:              { resourceType: "tenants", permission: "applications" },
  APPROVE_LOANS:             { resourceType: "tenants", permission: "approve_loans" },
  MANAGE_LOAN_LIMITS:        { resourceType: "tenants", permission: "manage_loan_limits" },
  MANAGE_ESUSU:              { resourceType: "tenants", permission: "manage_esusu" },
  ISLAMIC_BANKING:           { resourceType: "tenants", permission: "islamic_banking" },
  AGRIC_BANKING:             { resourceType: "tenants", permission: "agric_banking" },
  LPO_MANAGEMENT:            { resourceType: "tenants", permission: "lpo_management" },
  CARD_ISSUANCE:             { resourceType: "tenants", permission: "card_issuance" },
  CARD_MANAGEMENT:           { resourceType: "tenants", permission: "card_management" },
  CONTROL_CARDS:             { resourceType: "tenants", permission: "control_cards" },
  DISPUTE_MANAGEMENT:        { resourceType: "tenants", permission: "dispute_management" },
  VIEW_AUDIT_LOGS:           { resourceType: "tenants", permission: "view_audit_logs" },
  EXPORT_AUDIT_LOGS:         { resourceType: "tenants", permission: "export_audit_logs" },
  FLAG_SUSPICIOUS:           { resourceType: "tenants", permission: "flag_suspicious_activity" },
  ANALYTICS:                 { resourceType: "tenants", permission: "view_analytics" },
  TEMPORAL_ACCESS:           { resourceType: "tenants", permission: "temporal_access_management" },
  BILLING:                   { resourceType: "tenants", permission: "billing_management" },
  CHART_OF_ACCOUNTS:         { resourceType: "tenants", permission: "coa_management" },
  ERP_INTEGRATION:           { resourceType: "tenants", permission: "erp_management" },
  DEVELOPER_PLATFORM:        { resourceType: "tenants", permission: "developer_platform" },
  COMMUNICATION_HUB:         { resourceType: "tenants", permission: "communication_hub_management" },
  EMERGENCY_OVERRIDE:        { resourceType: "tenants", permission: "emergency_override" },

  // ── platform entity ──────────────────────────────────────────────────────
  PLATFORM_VIEW_ALL:         { resourceType: "platform", permission: "view_all_data" },
  PLATFORM_MANAGE_EMPLOYEES: { resourceType: "platform", permission: "manage_employees" },
  PLATFORM_MANAGE_TENANTS:   { resourceType: "platform", permission: "manage_tenants" },
  PLATFORM_PROVIDE_SUPPORT:  { resourceType: "platform", permission: "provide_support" },
  PLATFORM_ENABLE_FEATURES:  { resourceType: "platform", permission: "enable_features" },
  PLATFORM_SYSTEM_LOCKDOWN:  { resourceType: "platform", permission: "system_lockdown" },

  // ── Meta ─────────────────────────────────────────────────────────────────
  DASHBOARD:      null,
  MY_PERMISSIONS: null,
} as const;
