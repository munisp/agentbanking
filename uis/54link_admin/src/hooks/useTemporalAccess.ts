import { temporalAccessService } from "@/services/temporalAccessService";
import { useEffect, useState } from "react";

interface UseTemporalAccessOptions {
  permission: string;
  resourceType: string;
  resourceId?: string;
  autoCheck?: boolean; // Automatically check on mount
  refetchInterval?: number; // Auto-refresh interval in ms
}

interface TemporalAccessResult {
  allowed: boolean;
  requiresMfa: boolean;
  requiresApproval: boolean;
  mfaVerified: boolean;
  reason?: string;
  loading: boolean;
  error: Error | null;
  check: () => Promise<void>;
}

/**
 * React hook for checking temporal access permissions
 *
 * @example
 * ```tsx
 * // Check if user can approve loans
 * const { allowed, requiresMfa, loading, check } = useTemporalAccess({
 *   permission: 'approve',
 *   resourceType: 'loan',
 *   resourceId: 'loan_123',
 *   autoCheck: true,
 * });
 *
 * if (loading) return <Spinner />;
 *
 * return (
 *   <Button disabled={!allowed} onClick={handleApprove}>
 *     {allowed ? 'Approve Loan' : 'No Permission'}
 *     {requiresMfa && ' (MFA Required)'}
 *   </Button>
 * );
 * ```
 */
export function useTemporalAccess({
  permission,
  resourceType,
  resourceId = "",
  autoCheck = false,
  refetchInterval,
}: UseTemporalAccessOptions): TemporalAccessResult {
  const [allowed, setAllowed] = useState(false);
  const [requiresMfa, setRequiresMfa] = useState(false);
  const [requiresApproval, setRequiresApproval] = useState(false);
  const [mfaVerified, setMfaVerified] = useState(false);
  const [reason, setReason] = useState<string | undefined>();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const tenantId =
    import.meta.env.VITE_TENANT_ID ||
    localStorage.getItem("tenant_id") ||
    "54link";
  const currentUserId = localStorage.getItem("keycloak_id") || "";

  const check = async () => {
    if (!currentUserId) {
      setError(new Error("User not authenticated"));
      setAllowed(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const result = await temporalAccessService.checkAccess({
        tenant_id: tenantId,
        subject_id: currentUserId,
        permission,
        resource_type: resourceType,
        resource_id: resourceId,
        context: {},
      });

      setAllowed(result.allowed);
      setRequiresMfa(result.requires_mfa || false);
      setRequiresApproval(result.requires_approval || false);
      setMfaVerified(result.mfa_verified || false);
      setReason(result.reason);
    } catch (err) {
      setError(err instanceof Error ? err : new Error("Unknown error"));
      setAllowed(false);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (autoCheck && currentUserId) {
      check();
    }
  }, [permission, resourceType, resourceId, currentUserId, autoCheck]);

  useEffect(() => {
    if (refetchInterval && refetchInterval > 0) {
      const interval = setInterval(() => {
        check();
      }, refetchInterval);
      return () => clearInterval(interval);
    }
  }, [refetchInterval, permission, resourceType, resourceId]);

  return {
    allowed,
    requiresMfa,
    requiresApproval,
    mfaVerified,
    reason,
    loading,
    error,
    check,
  };
}

/**
 * Hook to get all active grants for the current user
 *
 * @example
 * ```tsx
 * const { grants, loading, refresh } = useMyGrants();
 *
 * return (
 *   <div>
 *     <h2>Active Grants: {grants.filter(g => g.status === 'active').length}</h2>
 *     <Button onClick={refresh}>Refresh</Button>
 *   </div>
 * );
 * ```
 */
export function useMyGrants() {
  const [grants, setGrants] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const tenantId =
    import.meta.env.VITE_TENANT_ID ||
    localStorage.getItem("tenant_id") ||
    "54link";
  const currentUserId = localStorage.getItem("keycloak_id") || "";

  const refresh = async () => {
    if (!currentUserId) {
      setError(new Error("User not authenticated"));
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const data = await temporalAccessService.listUserGrants(tenantId);
      setGrants(data);
    } catch (err) {
      setError(err instanceof Error ? err : new Error("Unknown error"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (currentUserId) {
      refresh();
    }
  }, [currentUserId]);

  return { grants, loading, error, refresh };
}

/**
 * Hook to get all delegations to the current user
 *
 * @example
 * ```tsx
 * const { delegations, loading, refresh } = useMyDelegations();
 *
 * const activeDelegations = delegations.filter(d => !d.revoked);
 * ```
 */
export function useMyDelegations() {
  const [delegations, setDelegations] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const tenantId =
    import.meta.env.VITE_TENANT_ID ||
    localStorage.getItem("tenant_id") ||
    "54link";
  const currentUserId = localStorage.getItem("keycloak_id") || "";

  const refresh = async () => {
    if (!currentUserId) {
      setError(new Error("User not authenticated"));
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const data = await temporalAccessService.listDelegations(
        tenantId,
        currentUserId,
      );
      setDelegations(data);
    } catch (err) {
      setError(err instanceof Error ? err : new Error("Unknown error"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (currentUserId) {
      refresh();
    }
  }, [currentUserId]);

  return { delegations, loading, error, refresh };
}
