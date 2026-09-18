import axios, { type AxiosInstance } from "axios";
import { DEVELOPER_PLATFORM_URL } from "../const";
import type * as Types from "../types/developerPlatform";
/**
 * KNOWN GAP (contract repair, wave B5b): this client targets a "developer-platform"
 * backend service (/api/v1/admin/*) that is NOT implemented or registered in the
 * api-server at base commit 6d7bdd3a — every endpoint here would fail with 404 or
 * a network error. Until the backend service lands, every method degrades
 * gracefully: on request failure or 404 it resolves with a typed empty result
 * instead of throwing, so admin pages render empty states rather than crashing.
 * Public interfaces are unchanged. Remove the `safe` wrappers once the real
 * developer-platform service is deployed.
 */

/**
 * Developer Platform API Client
 * Uses a separate base URL from the main application API
 */

// ---------------------------------------------------------------------------
// Typed empty fallbacks returned when the developer-platform backend is absent.
// ---------------------------------------------------------------------------
const UNAVAILABLE_MSG =
  "developer platform service unavailable (known gap: backend not deployed)";

const EMPTY_API_RESPONSE: Types.ApiResponse = {
  message: UNAVAILABLE_MSG,
  success: false,
  unavailable: true,
};

const EMPTY_DEVELOPERS_LIST: Types.DevelopersListResponse = {
  developers: [],
  total: 0,
  page: 1,
  limit: 20,
};

const EMPTY_DEVELOPER_DETAILS: Types.DeveloperDetails = {
  id: "",
  email: "",
  name: "",
  organization_id: "",
  organization_name: "",
  role: "developer",
  status: "active" as Types.DeveloperStatus,
  kyb_status: "pending" as Types.KYBStatus,
  total_apps: 0,
  active_installations: 0,
  monthly_revenue: 0,
  created_at: "",
  last_login_at: "",
  apps: [],
  api_usage: { monthly_calls: 0, rate_limit: 0, current_tier: "free" },
  compliance: {
    kyb_verified: false,
    terms_accepted: false,
    privacy_policy_accepted: false,
    last_security_review: "",
  },
};

const EMPTY_ORGANIZATIONS_LIST: Types.OrganizationsListResponse = {
  organizations: [],
  total: 0,
  page: 1,
  limit: 20,
};

const EMPTY_ORGANIZATION_DETAILS: Types.OrganizationFullDetails = {
  id: "",
  name: "",
  legal_name: "",
  country: "",
  kyb_status: "pending" as Types.KYBStatus,
  tier_level: "free",
  total_developers: 0,
  total_apps: 0,
  monthly_revenue: 0,
  status: "active",
  created_at: "",
  registration_number: "",
  kyb_verified_at: "",
  kyb_documents: { cac_certificate: "", proof_of_address: "", director_id: "" },
  developers: [],
  apps: [],
  financial: {
    tier_level: "free",
    monthly_revenue: 0,
    platform_fees_ytd: 0,
    payout_account: "",
    next_payout_date: "",
  },
  compliance: {
    kyb_verified: false,
    security_reviews_passed: 0,
    last_security_scan: "",
    vulnerabilities_found: 0,
  },
};

const EMPTY_PENDING_KYB: Types.PendingKYBResponse = {
  applications: [],
  total: 0,
  average_review_time_days: 0,
};

const EMPTY_KYB_REVIEW: Types.KYBReviewDetails = {
  organization_id: "",
  organization_name: "",
  legal_name: "",
  registration_number: "",
  country: "",
  address: "",
  website: "",
  contact_email: "",
  contact_phone: "",
  submitted_at: "",
  documents: [],
  verification_checks: {
    registration_number_valid: null,
    address_verified: null,
    directors_checked: null,
    aml_screening: null,
  },
  risk_score: null,
};

const EMPTY_PENDING_REVIEW: Types.PendingReviewResponse = {
  apps: [],
  total: 0,
  average_review_time_days: 0,
};

const EMPTY_APP_REVIEW: Types.AppReviewDetails = {
  app_id: "",
  name: "",
  description: "",
  developer_id: "",
  organization_id: "",
  version: "",
  category: "",
  submitted_at: "",
  api_scopes: [],
  webhook_url: "",
  redirect_uris: [],
  screenshots: [],
  privacy_policy_url: "",
  terms_url: "",
  review_checklist: {
    security_scan: { status: "pending", findings: 0, severity: "none", completed_at: "" },
    compliance_check: {
      status: "pending",
      gdpr_compliant: false,
      ndpr_compliant: false,
      pci_dss_required: false,
      pci_dss_compliant: false,
    },
    functionality_test: { status: "pending", test_cases: 0, passed: 0, failed: 0 },
    documentation_review: { status: "pending", api_docs_quality: null, user_guide_present: false },
  },
  risk_assessment: {
    risk_level: "low",
    data_sensitivity: "low",
    requires_additional_review: false,
  },
};

const EMPTY_SECURITY_SCANS: Types.SecurityScansResponse = { scans: [], total: 0 };

const EMPTY_SCAN_DETAILS: Types.ScanDetails = {
  scan_id: "",
  app_id: "",
  scan_type: "",
  status: "pending",
  severity: "none",
  compliance_score: 0,
  vulnerabilities: [],
  recommendations: [],
  completed_at: "",
};

const EMPTY_MARKETPLACE_STATS: Types.MarketplaceStats = {
  total_apps: 0,
  published_apps: 0,
  pending_review: 0,
  featured_apps: 0,
  total_installations: 0,
  active_installations: 0,
  total_developers: 0,
  active_developers: 0,
  categories: [],
  top_apps: [],
  revenue: { monthly_gmv: 0, platform_fees: 0, growth_percentage: 0 },
};

const EMPTY_FLAGGED_REVIEWS: Types.FlaggedReviewsResponse = { reviews: [], total: 0 };

const EMPTY_FEE_CONFIG: Types.FeeConfiguration = {
  id: "",
  name: "",
  base_platform_fee: 0,
  tier_fees: {},
  transaction_fees: { enabled: false, fee_model: "flat", tiered_fees: [] },
  volume_discounts: [],
  effective_from: "",
  is_active: false,
};

const EMPTY_REVENUE_REPORT: Types.RevenueReport = {
  period: "",
  total_gmv: 0,
  total_platform_fees: 0,
  total_transaction_fees: 0,
  total_volume_discounts: 0,
  net_revenue: 0,
  breakdown_by_tier: [],
  top_revenue_apps: [],
};

const EMPTY_PLATFORM_OVERVIEW: Types.PlatformOverview = {
  period: "",
  date_range: { start: "", end: "" },
  metrics: {
    total_api_calls: 0,
    successful_calls: 0,
    failed_calls: 0,
    average_latency_ms: 0,
    uptime_percentage: 0,
    active_developers: 0,
    new_developers: 0,
    active_apps: 0,
    new_apps: 0,
    total_installations: 0,
    new_installations: 0,
    gmv: 0,
    platform_revenue: 0,
  },
  growth: { api_calls: 0, developers: 0, apps: 0, revenue: 0 },
  top_performers: {
    most_popular_apps: [],
    highest_revenue_apps: [],
    most_active_developers: [],
  },
};

const EMPTY_API_USAGE: Types.APIUsageAnalytics = {
  total_requests: 0,
  by_environment: { production: 0, sandbox: 0 },
  by_status_code: { "2xx": 0, "4xx": 0, "5xx": 0 },
  by_endpoint: [],
  peak_usage: { timestamp: "", requests_per_minute: 0 },
};

const EMPTY_DEVELOPER_GROWTH: Types.DeveloperGrowthMetrics = {
  timeline: [],
  retention: { "30_day": 0, "60_day": 0, "90_day": 0 },
  activation_funnel: {
    registered: 0,
    kyb_submitted: 0,
    kyb_verified: 0,
    app_submitted: 0,
    app_published: 0,
  },
};

const EMPTY_TENANT_INSTALLATIONS: Types.TenantInstallationsResponse = {
  installations: [],
  total: 0,
};

const EMPTY_INSTALLATION_DETAILS: Types.InstallationDetails = {
  installation_id: "",
  app_id: "",
  tenant_id: "",
  status: "inactive",
  configuration: { api_key: "", webhook_url: "" },
  permissions_granted: [],
  usage_stats: { api_calls_total: 0, api_calls_30d: 0, last_accessed: "" },
  installed_at: "",
};

const EMPTY_SYSTEM_HEALTH: Types.SystemHealth = {
  status: "unhealthy",
  services: {
    database: "unhealthy",
    redis: "unhealthy",
    apisix: "unhealthy",
    storage: "unhealthy",
  },
  metrics: {
    uptime_seconds: 0,
    cpu_usage_percent: 0,
    memory_usage_percent: 0,
    disk_usage_percent: 0,
  },
  last_deployment: "",
};

const EMPTY_AUDIT_LOGS: Types.AuditLogsResponse = { logs: [], total: 0, page: 1 };

class DeveloperPlatformService {
  private api: AxiosInstance;

  constructor() {
    this.api = axios.create({
      baseURL: DEVELOPER_PLATFORM_URL,
      headers: {
        "Content-Type": "application/json",
      },
    });

    // Add auth interceptor
    this.api.interceptors.request.use((config) => {
      const token = this.getAuthToken();
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }

      // Add admin role header if available
      const adminRole = this.getAdminRole();
      if (adminRole) {
        config.headers["X-Admin-Role"] = adminRole;
      }

      return config;
    });
  }


  /**
   * Execute a developer-platform call, returning `fallback` when the backend
   * service is missing/unreachable (network error, 404, 5xx) instead of throwing.
   */
  private async safe<T>(call: () => Promise<T>, fallback: T): Promise<T> {
    try {
      return await call();
    } catch (error) {
      const status = (error as { response?: { status?: number } })?.response
        ?.status;
      console.warn(
        `[developerPlatform] backend unavailable${status ? ` (HTTP ${status})` : ""}; returning empty result.`,
      );
      return fallback;
    }
  }

  private getAuthToken(): string | null {
    return localStorage.getItem("admin_token");
  }

  private getAdminRole(): string | null {
    return localStorage.getItem("admin_role");
  }

  // ============================================
  // Developer Management
  // ============================================

  async listDevelopers(params?: {
    status?: Types.DeveloperStatus;
    kyb_status?: Types.KYBStatus;
    page?: number;
    limit?: number;
    search?: string;
  }): Promise<Types.DevelopersListResponse> {
    return this.safe(async () => {
      const response = await this.api.get("/api/v1/admin/developers", { params });
      return response.data;
    }, EMPTY_DEVELOPERS_LIST);
  }

  async getDeveloperDetails(
    developerId: string,
  ): Promise<Types.DeveloperDetails> {
    return this.safe(async () => {
      const response = await this.api.get(
      `/api/v1/admin/developers/${developerId}`,
    );
      return response.data;
    }, EMPTY_DEVELOPER_DETAILS);
  }

  async suspendDeveloper(
    developerId: string,
    data: Types.SuspendDeveloperRequest,
  ): Promise<Types.ApiResponse> {
    return this.safe(async () => {
      const response = await this.api.post(
      `/api/v1/admin/developers/${developerId}/suspend`,
      data,
    );
      return response.data;
    }, EMPTY_API_RESPONSE);
  }

  async reactivateDeveloper(
    developerId: string,
    data: Types.ReactivateDeveloperRequest,
  ): Promise<Types.ApiResponse> {
    return this.safe(async () => {
      const response = await this.api.post(
      `/api/v1/admin/developers/${developerId}/reactivate`,
      data,
    );
      return response.data;
    }, EMPTY_API_RESPONSE);
  }

  async updateDeveloperTier(
    developerId: string,
    data: Types.UpdateDeveloperTierRequest,
  ): Promise<Types.ApiResponse> {
    return this.safe(async () => {
      const response = await this.api.put(
      `/api/v1/admin/developers/${developerId}/tier`,
      data,
    );
      return response.data;
    }, EMPTY_API_RESPONSE);
  }

  // ============================================
  // Organization Management
  // ============================================

  async listOrganizations(params?: {
    kyb_status?: Types.KYBStatus;
    tier_level?: Types.TierLevel;
    country?: string;
    status?: Types.OrgStatus;
    page?: number;
    limit?: number;
  }): Promise<Types.OrganizationsListResponse> {
    return this.safe(async () => {
      const response = await this.api.get("/api/v1/admin/organizations", {
      params,
    });
      return response.data;
    }, EMPTY_ORGANIZATIONS_LIST);
  }

  async getOrganizationFullDetails(
    orgId: string,
  ): Promise<Types.OrganizationFullDetails> {
    return this.safe(async () => {
      const response = await this.api.get(
      `/api/v1/admin/organizations/${orgId}/full`,
    );
      return response.data;
    }, EMPTY_ORGANIZATION_DETAILS);
  }

  async updateOrganizationStatus(
    orgId: string,
    data: Types.UpdateOrgStatusRequest,
  ): Promise<Types.ApiResponse> {
    return this.safe(async () => {
      const response = await this.api.put(
      `/api/v1/admin/organizations/${orgId}/status`,
      data,
    );
      return response.data;
    }, EMPTY_API_RESPONSE);
  }

  // ============================================
  // KYB Verification
  // ============================================

  async listPendingKYB(): Promise<Types.PendingKYBResponse> {
    return this.safe(async () => {
      const response = await this.api.get("/api/v1/admin/kyb/pending");
      return response.data;
    }, EMPTY_PENDING_KYB);
  }

  async reviewKYBApplication(orgId: string): Promise<Types.KYBReviewDetails> {
    return this.safe(async () => {
      const response = await this.api.get(`/api/v1/admin/kyb/${orgId}/review`);
      return response.data;
    }, EMPTY_KYB_REVIEW);
  }

  async approveKYB(
    orgId: string,
    data: Types.ApproveKYBRequest,
  ): Promise<Types.ApiResponse> {
    return this.safe(async () => {
      const response = await this.api.post(
      `/api/v1/admin/kyb/${orgId}/approve`,
      data,
    );
      return response.data;
    }, EMPTY_API_RESPONSE);
  }

  async rejectKYB(
    orgId: string,
    data: Types.RejectKYBRequest,
  ): Promise<Types.ApiResponse> {
    return this.safe(async () => {
      const response = await this.api.post(
      `/api/v1/admin/kyb/${orgId}/reject`,
      data,
    );
      return response.data;
    }, EMPTY_API_RESPONSE);
  }

  async requestAdditionalDocuments(
    orgId: string,
    data: Types.RequestDocumentsRequest,
  ): Promise<Types.ApiResponse> {
    return this.safe(async () => {
      const response = await this.api.post(
      `/api/v1/admin/kyb/${orgId}/request-documents`,
      data,
    );
      return response.data;
    }, EMPTY_API_RESPONSE);
  }

  // ============================================
  // App Review & Approval
  // ============================================

  async listAppsPendingReview(): Promise<Types.PendingReviewResponse> {
    return this.safe(async () => {
      const response = await this.api.get("/api/v1/admin/apps/pending-review");
      return response.data;
    }, EMPTY_PENDING_REVIEW);
  }

  async getAppReviewDetails(appId: string): Promise<Types.AppReviewDetails> {
    return this.safe(async () => {
      const response = await this.api.get(`/api/v1/admin/apps/${appId}/review`);
      return response.data;
    }, EMPTY_APP_REVIEW);
  }

  async approveApp(
    appId: string,
    data: Types.ApproveAppRequest,
  ): Promise<Types.ApiResponse> {
    return this.safe(async () => {
      const response = await this.api.post(
      `/api/v1/admin/apps/${appId}/approve`,
      data,
    );
      return response.data;
    }, EMPTY_API_RESPONSE);
  }

  async rejectApp(
    appId: string,
    data: Types.RejectAppRequest,
  ): Promise<Types.ApiResponse> {
    return this.safe(async () => {
      const response = await this.api.post(
      `/api/v1/admin/apps/${appId}/reject`,
      data,
    );
      return response.data;
    }, EMPTY_API_RESPONSE);
  }

  async requestAppChanges(
    appId: string,
    data: Types.RequestAppChangesRequest,
  ): Promise<Types.ApiResponse> {
    return this.safe(async () => {
      const response = await this.api.post(
      `/api/v1/admin/apps/${appId}/request-changes`,
      data,
    );
      return response.data;
    }, EMPTY_API_RESPONSE);
  }

  async featureApp(
    appId: string,
    data: Types.FeatureAppRequest,
  ): Promise<Types.ApiResponse> {
    return this.safe(async () => {
      const response = await this.api.post(
      `/api/v1/admin/apps/${appId}/feature`,
      data,
    );
      return response.data;
    }, EMPTY_API_RESPONSE);
  }

  async unpublishApp(
    appId: string,
    data: Types.UnpublishAppRequest,
  ): Promise<Types.ApiResponse> {
    return this.safe(async () => {
      const response = await this.api.post(
      `/api/v1/admin/apps/${appId}/unpublish`,
      data,
    );
      return response.data;
    }, EMPTY_API_RESPONSE);
  }

  // ============================================
  // Security Vetting
  // ============================================

  async listSecurityScans(params?: {
    status?: Types.ScanStatus;
    severity?: Types.Severity;
    app_id?: string;
  }): Promise<Types.SecurityScansResponse> {
    return this.safe(async () => {
      const response = await this.api.get("/api/v1/admin/security/scans", {
      params,
    });
      return response.data;
    }, EMPTY_SECURITY_SCANS);
  }

  async getScanDetails(scanId: string): Promise<Types.ScanDetails> {
    return this.safe(async () => {
      const response = await this.api.get(
      `/api/v1/admin/security/scans/${scanId}`,
    );
      return response.data;
    }, EMPTY_SCAN_DETAILS);
  }

  async initiateScan(
    data: Types.InitiateScanRequest,
  ): Promise<Types.ApiResponse> {
    return this.safe(async () => {
      const response = await this.api.post("/api/v1/admin/security/scans", data);
      return response.data;
    }, EMPTY_API_RESPONSE);
  }

  async updateVulnerability(
    vulnId: string,
    data: Types.UpdateVulnerabilityRequest,
  ): Promise<Types.ApiResponse> {
    return this.safe(async () => {
      const response = await this.api.put(
      `/api/v1/admin/security/vulnerabilities/${vulnId}`,
      data,
    );
      return response.data;
    }, EMPTY_API_RESPONSE);
  }

  // ============================================
  // Marketplace Management
  // ============================================

  async getMarketplaceStats(): Promise<Types.MarketplaceStats> {
    return this.safe(async () => {
      const response = await this.api.get("/api/v1/admin/marketplace/stats");
      return response.data;
    }, EMPTY_MARKETPLACE_STATS);
  }

  async updateAppCategories(
    data: Types.UpdateCategoriesRequest,
  ): Promise<Types.ApiResponse> {
    return this.safe(async () => {
      const response = await this.api.put(
      "/api/v1/admin/marketplace/categories",
      data,
    );
      return response.data;
    }, EMPTY_API_RESPONSE);
  }

  async manageFeaturedApps(
    data: Types.ManageFeaturedAppsRequest,
  ): Promise<Types.ApiResponse> {
    return this.safe(async () => {
      const response = await this.api.post(
      "/api/v1/admin/marketplace/featured",
      data,
    );
      return response.data;
    }, EMPTY_API_RESPONSE);
  }

  async getFlaggedReviews(): Promise<Types.FlaggedReviewsResponse> {
    return this.safe(async () => {
      const response = await this.api.get(
      "/api/v1/admin/marketplace/reviews/flagged",
    );
      return response.data;
    }, EMPTY_FLAGGED_REVIEWS);
  }

  async removeReview(
    reviewId: string,
    data: Types.RemoveReviewRequest,
  ): Promise<Types.ApiResponse> {
    return this.safe(async () => {
      const response = await this.api.delete(
      `/api/v1/admin/marketplace/reviews/${reviewId}`,
      { data },
    );
      return response.data;
    }, EMPTY_API_RESPONSE);
  }

  // ============================================
  // Fee Configuration
  // ============================================

  async getActiveFeeConfig(): Promise<Types.FeeConfiguration> {
    return this.safe(async () => {
      const response = await this.api.get("/api/v1/admin/fees/configs/active");
      return response.data;
    }, EMPTY_FEE_CONFIG);
  }

  async createFeeConfig(
    data: Types.CreateFeeConfigRequest,
  ): Promise<Types.ApiResponse> {
    return this.safe(async () => {
      const response = await this.api.post("/api/v1/admin/fees/configs", data);
      return response.data;
    }, EMPTY_API_RESPONSE);
  }

  async activateFeeConfig(
    configId: string,
    data: Types.ActivateFeeConfigRequest,
  ): Promise<Types.ApiResponse> {
    return this.safe(async () => {
      const response = await this.api.post(
      `/api/v1/admin/fees/configs/${configId}/activate`,
      data,
    );
      return response.data;
    }, EMPTY_API_RESPONSE);
  }

  async assignCustomFee(
    data: Types.AssignCustomFeeRequest,
  ): Promise<Types.ApiResponse> {
    return this.safe(async () => {
      const response = await this.api.post(
      "/api/v1/admin/fees/assignments",
      data,
    );
      return response.data;
    }, EMPTY_API_RESPONSE);
  }

  async getRevenueReport(params?: {
    period?: string;
    breakdown?: "app" | "developer" | "category";
  }): Promise<Types.RevenueReport> {
    return this.safe(async () => {
      const response = await this.api.get("/api/v1/admin/fees/reports/revenue", {
      params,
    });
      return response.data;
    }, EMPTY_REVENUE_REPORT);
  }

  // ============================================
  // Platform Analytics
  // ============================================

  async getPlatformOverview(params?: {
    period?: "today" | "week" | "month" | "year";
    compare_to?: "previous_period";
  }): Promise<Types.PlatformOverview> {
    return this.safe(async () => {
      const response = await this.api.get("/api/v1/admin/analytics/overview", {
      params,
    });
      return response.data;
    }, EMPTY_PLATFORM_OVERVIEW);
  }

  async getAPIUsageAnalytics(): Promise<Types.APIUsageAnalytics> {
    return this.safe(async () => {
      const response = await this.api.get("/api/v1/admin/analytics/api-usage");
      return response.data;
    }, EMPTY_API_USAGE);
  }

  async getDeveloperGrowthMetrics(): Promise<Types.DeveloperGrowthMetrics> {
    return this.safe(async () => {
      const response = await this.api.get(
      "/api/v1/admin/analytics/developer-growth",
    );
      return response.data;
    }, EMPTY_DEVELOPER_GROWTH);
  }

  // ============================================
  // Tenant App Management
  // ============================================

  async listTenantInstallations(params?: {
    app_id?: string;
    tenant_id?: string;
    status?: "active" | "inactive" | "suspended";
  }): Promise<Types.TenantInstallationsResponse> {
    return this.safe(async () => {
      const response = await this.api.get("/api/v1/admin/tenants/installations", {
      params,
    });
      return response.data;
    }, EMPTY_TENANT_INSTALLATIONS);
  }

  async suspendTenantInstallation(
    installationId: string,
    data: Types.SuspendInstallationRequest,
  ): Promise<Types.ApiResponse> {
    return this.safe(async () => {
      const response = await this.api.post(
      `/api/v1/admin/tenants/installations/${installationId}/suspend`,
      data,
    );
      return response.data;
    }, EMPTY_API_RESPONSE);
  }

  async getInstallationDetails(
    installationId: string,
  ): Promise<Types.InstallationDetails> {
    return this.safe(async () => {
      const response = await this.api.get(
      `/api/v1/admin/tenants/installations/${installationId}`,
    );
      return response.data;
    }, EMPTY_INSTALLATION_DETAILS);
  }

  // ============================================
  // System Configuration
  // ============================================

  async updatePlatformSettings(
    data: Types.PlatformSettings,
  ): Promise<Types.ApiResponse> {
    return this.safe(async () => {
      const response = await this.api.put("/api/v1/admin/config/platform", data);
      return response.data;
    }, EMPTY_API_RESPONSE);
  }

  async getSystemHealth(): Promise<Types.SystemHealth> {
    return this.safe(async () => {
      const response = await this.api.get("/api/v1/admin/system/health");
      return response.data;
    }, EMPTY_SYSTEM_HEALTH);
  }

  async getAuditLogs(params?: {
    action?: string;
    admin_id?: string;
    start_date?: string;
    end_date?: string;
    page?: number;
    limit?: number;
  }): Promise<Types.AuditLogsResponse> {
    return this.safe(async () => {
      const response = await this.api.get("/api/v1/admin/audit/logs", { params });
      return response.data;
    }, EMPTY_AUDIT_LOGS);
  }

  // ============================================
  // Emergency & Bulk Operations
  // ============================================

  async emergencySuspendApp(
    data: Types.EmergencySuspendAppRequest,
  ): Promise<Types.ApiResponse> {
    return this.safe(async () => {
      const response = await this.api.post(
      "/api/v1/admin/emergency/suspend-app",
      data,
    );
      return response.data;
    }, EMPTY_API_RESPONSE);
  }

  async bulkSuspendDevelopers(
    data: Types.BulkSuspendDevelopersRequest,
  ): Promise<Types.ApiResponse> {
    return this.safe(async () => {
      const response = await this.api.post(
      "/api/v1/admin/bulk/suspend-developers",
      data,
    );
      return response.data;
    }, EMPTY_API_RESPONSE);
  }
}

// Export singleton instance
export const developerPlatformService = new DeveloperPlatformService();
