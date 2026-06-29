import api from "./api";

export interface TemporalGrant {
  id: string;
  tenant_id: string;
  subject_id: string;
  subject_type: string;
  permission: string;
  resource_type: string;
  resource_id: string;
  granted_by: string;
  granted_at: string;
  expires_at: string;
  reason: string;
  status: string;
  usage_count: number;
  max_usage?: number;
  conditions?: AccessConditions;
  revoked_at?: string;
  revoked_by?: string;
}

export interface AccessConditions {
  ip_whitelist?: string[];
  device_ids?: string[];
  require_mfa: boolean;
  require_liveness: boolean;
  time_windows?: TimeWindow[];
  location_restrictions?: LocationRestriction[];
  max_usage_count?: number;
}

export interface TimeWindow {
  start_time: string;
  end_time: string;
  days: string[];
  timezone: string;
}

export interface LocationRestriction {
  type: "country" | "region" | "city";
  value: string;
}

export interface CreateGrantRequest {
  tenant_id: string;
  subject_id: string;
  subject_type: string;
  permission: string;
  resource_type: string;
  resource_id: string;
  duration: string;
  reason: string;
  max_usage?: number;
  conditions?: AccessConditions;
}

export interface UpdateGrantRequest {
  reason?: string;
  max_usage?: number;
  conditions?: AccessConditions;
}

export interface PolicyRule {
  type: string;
  operator: string;
  value: any;
  action: string;
  metadata?: Record<string, any>;
}

export interface AccessPolicy {
  id: string;
  tenant_id: string;
  name: string;
  description: string;
  resource_type: string;
  permission: string;
  priority: number;
  enabled: boolean;
  created_at: string;
  updated_at: string;
  created_by: string;
  rules: PolicyRule[];
  metadata?: Record<string, any>;
}

export interface CreatePolicyRequest {
  tenant_id: string;
  name: string;
  description: string;
  resource_type: string;
  permission: string;
  priority: number;
  enabled: boolean;
  rules: PolicyRule[];
}

export interface UpdatePolicyRequest {
  name?: string;
  description?: string;
  resource_type?: string;
  permission?: string;
  priority?: number;
  enabled?: boolean;
  rules?: PolicyRule[];
}

export interface Delegation {
  id: string;
  tenant_id: string;
  delegator_id: string;
  delegate_id: string;
  permission: string;
  resource_type: string;
  resource_id: string;
  created_at: string;
  expires_at?: string;
  revoked: boolean;
  revoked_at?: string;
}

export interface CreateDelegationRequest {
  tenant_id: string;
  delegator_id: string;
  delegate_id: string;
  permission: string;
  resource_type: string;
  resource_id: string;
  expires_at?: string;
}

export interface UserSearchResult {
  id: string;
  email: string;
  keycloak_id: string;
  tenant_id: string;
  user_role: string;
  created_at: string;
}

export interface CheckAccessRequest {
  tenant_id: string;
  subject_id: string;
  permission: string;
  resource_type: string;
  resource_id: string;
  context?: Record<string, any>;
}

export interface CheckAccessResponse {
  allowed: boolean;
  reason: string;
  grant_id?: string;
  expires_at?: string;
  conditions_met?: boolean;
  requires_mfa?: any;
  requires_approval?:any;
  mfa_verified?:any;
}

class TemporalAccessService {
  private baseURL = "/temporal-access";

  // Grants Management
  async listGrants(tenantId: string): Promise<TemporalGrant[]> {
    const response = await api.get(
      `${this.baseURL}/api/v1/grants?tenant_id=${tenantId}`,
    );
    return response.data.grants || [];
  }

  async getGrant(grantId: string, tenantId: string): Promise<TemporalGrant> {
    const response = await api.get(
      `${this.baseURL}/api/v1/grants/${grantId}?tenant_id=${tenantId}`,
    );
    return response.data;
  }

  async createGrant(data: CreateGrantRequest): Promise<TemporalGrant> {
    const response = await api.post(`${this.baseURL}/api/v1/grants`, data);
    return response.data;
  }

  async revokeGrant(grantId: string, tenantId: string): Promise<void> {
    await api.delete(
      `${this.baseURL}/api/v1/grants/${grantId}?tenant_id=${tenantId}`,
    );
  }

  async extendGrant(
    grantId: string,
    tenantId: string,
    duration: string,
  ): Promise<TemporalGrant> {
    const response = await api.post(
      `${this.baseURL}/api/v1/grants/${grantId}/extend?tenant_id=${tenantId}`,
      { duration },
    );
    return response.data;
  }

  async updateGrant(
    grantId: string,
    tenantId: string,
    data: UpdateGrantRequest,
  ): Promise<TemporalGrant> {
    const response = await api.put(
      `${this.baseURL}/api/v1/grants/${grantId}?tenant_id=${tenantId}`,
      data,
    );
    return response.data;
  }

  // Access Policies
  async listPolicies(tenantId: string): Promise<AccessPolicy[]> {
    const response = await api.get(
      `${this.baseURL}/api/v1/policies?tenant_id=${tenantId}`,
    );
    return response.data.policies || [];
  }

  async createPolicy(data: CreatePolicyRequest): Promise<AccessPolicy> {
    const response = await api.post(`${this.baseURL}/api/v1/policies`, data);
    return response.data;
  }

  async updatePolicy(
    policyId: string,
    data: UpdatePolicyRequest,
  ): Promise<AccessPolicy> {
    const response = await api.put(
      `${this.baseURL}/api/v1/policies/${policyId}`,
      data,
    );
    return response.data;
  }

  async deletePolicy(policyId: string): Promise<void> {
    await api.delete(`${this.baseURL}/api/v1/policies/${policyId}`);
  }

  // Permission Check
  async checkAccess(data: CheckAccessRequest): Promise<CheckAccessResponse> {
    const response = await api.post(`${this.baseURL}/api/v1/authorize`, data);
    return response.data;
  }

  async listUserGrants(tenantId: string): Promise<TemporalGrant[]> {
    const response = await api.get(
      `${this.baseURL}/api/v1/users/me/grants?tenant_id=${tenantId}`,
    );
    const d = response.data;
    if (Array.isArray(d)) return d;
    if (Array.isArray(d?.grants)) return d.grants;
    if (Array.isArray(d?.data)) return d.data;
    return [];
  }

  // Delegations
  async listDelegations(
    tenantId: string,
    delegateId?: string,
  ): Promise<Delegation[]> {
    const keycloakId = localStorage.getItem("keycloak_id") || "";
    const finalDelegateId = delegateId || keycloakId;
    const response = await api.get(
      `${this.baseURL}/api/v1/delegations?tenant_id=${tenantId}&delegate_id=${finalDelegateId}`,
    );
    const d = response.data;
    if (Array.isArray(d)) return d;
    if (Array.isArray(d?.delegations)) return d.delegations;
    if (Array.isArray(d?.data)) return d.data;
    return [];
  }

  async createDelegation(data: CreateDelegationRequest): Promise<Delegation> {
    const response = await api.post(`${this.baseURL}/api/v1/delegations`, data);
    return response.data;
  }

  async revokeDelegation(delegationId: string): Promise<void> {
    await api.delete(`${this.baseURL}/api/v1/delegations/${delegationId}`);
  }

  // User Search (using existing auth/user service)
  async searchUsers(
    query: string,
    tenantId: string,
  ): Promise<UserSearchResult[]> {
    const searchTerm = query.trim().toLowerCase();
    console.log(tenantId)

    let users: UserSearchResult[] = [];
    let admins: UserSearchResult[] = [];

    // Fetch tenant users from user service
    try {
      const userResponse = await api.get(`/user/user/tenant`);
      const userData = userResponse.data;

      const rawUsers = Array.isArray(userData)
        ? userData
        : Array.isArray(userData?.users)
          ? userData.users
          : Array.isArray(userData?.data)
            ? userData.data
            : [];

      users = rawUsers
        .filter((u: any) => !!u?.email && !!u?.keycloak_id)
        .map((u: any) => ({
          id: u.id || u.keycloak_id || u.uin || u.email,
          email: u.email,
          keycloak_id: u.keycloak_id,
          tenant_id: u.tenant_id,
          user_role: u.user_role || "user",
          created_at: u.created_at || "",
        }));
    } catch (error) {
      // If user fetch fails, fall back to empty list
      users = [];
    }

    // Fetch admins from admin service
    try {
      const adminResponse = await api.get(`/admin/admin`);
      const adminData = adminResponse.data;

      const rawAdmins = Array.isArray(adminData)
        ? adminData
        : Array.isArray(adminData?.admins)
          ? adminData.admins
          : Array.isArray(adminData?.data)
            ? adminData.data
            : [];

      admins = rawAdmins
        .filter((a: any) => !!a?.email && !!a?.keycloak_id)
        .map((a: any) => ({
          id: String(a.id ?? a.keycloak_id ?? a.email),
          email: a.email,
          keycloak_id: a.keycloak_id,
          tenant_id: a.tenant_id,
          user_role: "admin",
          created_at: (a.created_at || a.createdAt || "") as string,
        }));
    } catch (error) {
      // If admin fetch fails, fall back to empty list
      admins = [];
    }

    const all = [...users, ...admins];

    if (!searchTerm) {
      return all;
    }

    return all.filter((item) => {
      const email = item.email?.toLowerCase() || "";
      const id = (item.id || "").toString().toLowerCase();
      const keycloakId = item.keycloak_id?.toLowerCase() || "";

      return (
        email.includes(searchTerm) ||
        id.includes(searchTerm) ||
        keycloakId.includes(searchTerm)
      );
    });
  }
}

export const temporalAccessService = new TemporalAccessService();
