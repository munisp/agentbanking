import {
    temporalAccessService,
    type TemporalGrant,
} from "@/services/temporalAccessService";
import { useEffect } from "react";

const STORAGE_KEY = "temporal_access_grants";

export function useTemporalAccessPolling(enabled: boolean) {
  useEffect(() => {
    if (!enabled) return;

    const tenantId =
      import.meta.env.VITE_TENANT_ID ||
      localStorage.getItem("tenant_id") ||
      "bpmgd";
    const keycloakId = localStorage.getItem("keycloak_id");

    if (!tenantId || !keycloakId) return;

    const fetchGrants = async () => {
      try {
        const grants = await temporalAccessService.listUserGrants(
          tenantId,
        );
        localStorage.setItem(STORAGE_KEY, JSON.stringify(grants));
      } catch (error) {
        console.error("Failed to refresh temporal access grants:", error);
      }
    };

    // Initial fetch
    fetchGrants();

    const interval = window.setInterval(fetchGrants, 60_000); // every 60s

    return () => {
      window.clearInterval(interval);
    };
  }, [enabled]);
}

export function getCachedTemporalGrants(): TemporalGrant[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    return JSON.parse(raw) as TemporalGrant[];
  } catch {
    return [];
  }
}

type HasTemporalPermissionOptions = {
  permission: string;
  resourceType?: string;
  resourceId?: string;
  grants?: TemporalGrant[];
};

// Helper to check if the current user has a specific temporal permission
// based on the cached grants in localStorage (or a provided grants array).
export function hasTemporalPermission(options: HasTemporalPermissionOptions) {
  const { permission, resourceType, resourceId, grants } = options;

  const allGrants = (grants ?? getCachedTemporalGrants()) || [];
  const now = Date.now();

  return allGrants.some((grant) => {
    if (!grant) return false;
    if (grant.status !== "active") return false;

    // Expiry guard in case cache lags behind backend
    if (grant.expires_at && new Date(grant.expires_at).getTime() <= now) {
      return false;
    }

    if (grant.permission !== permission) return false;

    if (resourceType && grant.resource_type !== resourceType) return false;

    if (resourceId) {
      // If a specific resource is requested, match either the same resource
      // or a grant that was issued for "all" resources (empty resource_id).
      if (grant.resource_id && grant.resource_id !== resourceId) {
        return false;
      }
    }

    return true;
  });
}
