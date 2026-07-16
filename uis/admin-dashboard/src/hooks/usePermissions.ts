import { useCallback, useEffect, useRef, useState } from "react";
import { getTenantHeaders, getTenantHeadersFromStorage } from "../services/tenant";

// ─── localStorage helpers ────────────────────────────────────────────────────

function storageKey(userId: string, tenantId: string) {
  return `permify_cache:${userId}:${tenantId}`;
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

const BASE_URL = import.meta.env.VITE_API_URL || "https://54agent.upi.dev";

// ─── Hook ────────────────────────────────────────────────────────────────────

/**
 * Permify permission hook for the agent banking admin dashboard.
 *
 * Checks permissions against the v2.perm `tenants` entity via the auth
 * service. Cache is pre-populated from localStorage on first render so
 * hasPermission() works synchronously without a loading flash.
 *
 * Admin roles (super_admin, operations_manager, etc.) are v2.perm tenant
 * roles — they are NOT agent roles (agent / super_agent / aggregator).
 */
export function usePermissions() {
  const tenantId = import.meta.env.VITE_TENANT_ID;
  const currentUserId = localStorage.getItem("keycloakId") || "";

  // Pre-populate from localStorage → no flash on first render
  const [permissionCache, setPermissionCache] = useState<Map<string, boolean>>(
    () => loadFromStorage(currentUserId, tenantId),
  );

  // Ref mirrors state so callbacks read the latest value without stale closures
  const cacheRef = useRef(permissionCache);
  useEffect(() => {
    cacheRef.current = permissionCache;
  }, [permissionCache]);

  const [loading, setLoading] = useState(false);
  const [initialLoading, setInitialLoading] = useState(
    () => loadFromStorage(currentUserId, tenantId).size === 0 && !!currentUserId && !!tenantId,
  );

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
        const token = localStorage.getItem("auth_token") || "";
        const params = new URLSearchParams({
          permission,
          entity_type: resourceType,
          entity_id: resourceId || tenantId,
          user_id: currentUserId,
        });
        // const headers = getTenantHeaders
         const tenantHeaders = getTenantHeadersFromStorage()
        const res = await fetch(
          `${BASE_URL}/auth/permissions/check-permission?${params}`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${token}`,
              ...tenantHeaders
            },
          },
        );
        if (!res.ok) return false;
        const data = await res.json();
        const hasAccess: boolean = data.has_permission || false;
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

  /**
   * Synchronous read from cache — accurate from first render when
   * localStorage was pre-populated on a previous login.
   */
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

      const uncached = checks.filter(
        ({ resourceType, permission, resourceId }) =>
          !cacheRef.current.has(`${resourceType}:${permission}:${resourceId || tenantId}`),
      );

      if (uncached.length > 0) {
        setLoading(true);
        try {
          const token = localStorage.getItem("auth_token") || "";
          const tenantHeaders = getTenantHeadersFromStorage();
          const res = await fetch(`${BASE_URL}/auth/permissions/check-permissions-batch`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${token}`,
              ...tenantHeaders,
            },
            body: JSON.stringify({
              user_id: currentUserId,
              checks: uncached.map(({ resourceType, permission, resourceId }) => ({
                entity_type: resourceType,
                permission,
                entity_id: resourceId || tenantId,
              })),
            }),
          });
          if (res.ok) {
            const data = await res.json();
            for (const item of data.results ?? []) {
              const key = `${item.entity_type}:${item.permission}:${item.entity_id}`;
              writeEntry(key, item.has_permission ?? false);
            }
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

  // Pre-load all tenant permissions on mount — skips ones already cached
  useEffect(() => {
    if (!currentUserId || !tenantId) return;

    const tenantPermissions = [
      "manage_customers",
      "manage_employees",
      "view_all_data",
      "view_analytics",
      "view_audit_logs",
      "initiate_transactions",
      "dispute_management",
      "applications",
      "billing_management",
      "coa_management",
      "erp_management",
      "flag_suspicious_activity",
      "communication_hub_management",
      "verify_kyc",
      "temporal_access_management",
    ].map((p) => ({ resourceType: "tenants", permission: p }));

    const missing = tenantPermissions.filter(
      ({ resourceType, permission }) =>
        !cacheRef.current.has(`${resourceType}:${permission}:${tenantId}`),
    );

    if (missing.length > 0) {
      setInitialLoading(true);
      checkPermissions(missing).finally(() => setInitialLoading(false));
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentUserId, tenantId]);

  return { checkPermission, hasPermission, checkPermissions, clearCache, loading, initialLoading };
}

// ─── Permission map ──────────────────────────────────────────────────────────

/**
 * Maps agent banking admin sidebar items to v2.perm `tenants` entity
 * permissions. null = visible to all authenticated admin users.
 *
 * NOTE: these are ADMIN permissions. Agent roles (agent/super_agent/aggregator)
 * are entirely separate and never used for admin sidebar visibility.
 */
export const PERMISSION_MAP = {
  // Visibility
  VIEW_ALL:            { resourceType: "tenants", permission: "view_all_data" },
  VIEW_ANALYTICS:      { resourceType: "tenants", permission: "view_analytics" },
  // People
  MANAGE_CUSTOMERS:    { resourceType: "tenants", permission: "manage_customers" },
  MANAGE_EMPLOYEES:    { resourceType: "tenants", permission: "manage_employees" },
  // Finance
  BILLING:             { resourceType: "tenants", permission: "billing_management" },
  CHART_OF_ACCOUNTS:   { resourceType: "tenants", permission: "coa_management" },
  APPLICATIONS:        { resourceType: "tenants", permission: "applications" },
  TRANSACTIONS:        { resourceType: "tenants", permission: "initiate_transactions" },
  // IT / Devices
  ERP:                 { resourceType: "tenants", permission: "erp_management" },
  // Compliance / Risk
  DISPUTES:            { resourceType: "tenants", permission: "dispute_management" },
  AUDIT_LOGS:          { resourceType: "tenants", permission: "view_audit_logs" },
  FLAG_SUSPICIOUS:     { resourceType: "tenants", permission: "flag_suspicious_activity" },
  VERIFY_KYC:          { resourceType: "tenants", permission: "verify_kyc" },
  // Communication
  COMMUNICATION:       { resourceType: "tenants", permission: "communication_hub_management" },
  // Meta
  DASHBOARD:           null,
  NOTIFICATIONS:       null,
} as const;
