import axios, { type AxiosInstance } from "axios";
import { DEVELOPER_PLATFORM_URL } from "../const";
import type * as Types from "../types/developerPlatform";

/**
 * Developer Platform API Client
 * Uses a separate base URL from the main application API
 */
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
    const response = await this.api.get("/api/v1/admin/developers", { params });
    return response.data;
  }

  async getDeveloperDetails(
    developerId: string,
  ): Promise<Types.DeveloperDetails> {
    const response = await this.api.get(
      `/api/v1/admin/developers/${developerId}`,
    );
    return response.data;
  }

  async suspendDeveloper(
    developerId: string,
    data: Types.SuspendDeveloperRequest,
  ): Promise<Types.ApiResponse> {
    const response = await this.api.post(
      `/api/v1/admin/developers/${developerId}/suspend`,
      data,
    );
    return response.data;
  }

  async reactivateDeveloper(
    developerId: string,
    data: Types.ReactivateDeveloperRequest,
  ): Promise<Types.ApiResponse> {
    const response = await this.api.post(
      `/api/v1/admin/developers/${developerId}/reactivate`,
      data,
    );
    return response.data;
  }

  async updateDeveloperTier(
    developerId: string,
    data: Types.UpdateDeveloperTierRequest,
  ): Promise<Types.ApiResponse> {
    const response = await this.api.put(
      `/api/v1/admin/developers/${developerId}/tier`,
      data,
    );
    return response.data;
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
    const response = await this.api.get("/api/v1/admin/organizations", {
      params,
    });
    return response.data;
  }

  async getOrganizationFullDetails(
    orgId: string,
  ): Promise<Types.OrganizationFullDetails> {
    const response = await this.api.get(
      `/api/v1/admin/organizations/${orgId}/full`,
    );
    return response.data;
  }

  async updateOrganizationStatus(
    orgId: string,
    data: Types.UpdateOrgStatusRequest,
  ): Promise<Types.ApiResponse> {
    const response = await this.api.put(
      `/api/v1/admin/organizations/${orgId}/status`,
      data,
    );
    return response.data;
  }

  // ============================================
  // KYB Verification
  // ============================================

  async listPendingKYB(): Promise<Types.PendingKYBResponse> {
    const response = await this.api.get("/api/v1/admin/kyb/pending");
    return response.data;
  }

  async reviewKYBApplication(orgId: string): Promise<Types.KYBReviewDetails> {
    const response = await this.api.get(`/api/v1/admin/kyb/${orgId}/review`);
    return response.data;
  }

  async approveKYB(
    orgId: string,
    data: Types.ApproveKYBRequest,
  ): Promise<Types.ApiResponse> {
    const response = await this.api.post(
      `/api/v1/admin/kyb/${orgId}/approve`,
      data,
    );
    return response.data;
  }

  async rejectKYB(
    orgId: string,
    data: Types.RejectKYBRequest,
  ): Promise<Types.ApiResponse> {
    const response = await this.api.post(
      `/api/v1/admin/kyb/${orgId}/reject`,
      data,
    );
    return response.data;
  }

  async requestAdditionalDocuments(
    orgId: string,
    data: Types.RequestDocumentsRequest,
  ): Promise<Types.ApiResponse> {
    const response = await this.api.post(
      `/api/v1/admin/kyb/${orgId}/request-documents`,
      data,
    );
    return response.data;
  }

  // ============================================
  // App Review & Approval
  // ============================================

  async listAppsPendingReview(): Promise<Types.PendingReviewResponse> {
    // Return mock data instead of making an API call
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve({
          apps: [
            {
              app_id: "data-brick-1",
              name: "Data Brick",
              developer_id: "dev-1",
              developer_name: "Jane Doe",
              organization_name: "Acme Corp",
              category: "Finance",
              version: "1.0.0",
              submitted_at: new Date().toISOString(),
              days_in_review: 2,
              priority: "normal",
              review_status: {
                security_scan: "pending",
                compliance_check: "pending",
                functionality_test: "pending",
                documentation_review: "pending",
              },
            },
          ],
          total: 1,
          average_review_time_days: 2,
        });
      }, 300);
    });
  }

  async getAppReviewDetails(appId: string): Promise<Types.AppReviewDetails> {
    const response = await this.api.get(`/api/v1/admin/apps/${appId}/review`);
    return response.data;
  }

  async approveApp(
    appId: string,
    data: Types.ApproveAppRequest,
  ): Promise<Types.ApiResponse> {
    const response = await this.api.post(
      `/api/v1/admin/apps/${appId}/approve`,
      data,
    );
    return response.data;
  }

  async rejectApp(
    appId: string,
    data: Types.RejectAppRequest,
  ): Promise<Types.ApiResponse> {
    const response = await this.api.post(
      `/api/v1/admin/apps/${appId}/reject`,
      data,
    );
    return response.data;
  }

  async requestAppChanges(
    appId: string,
    data: Types.RequestAppChangesRequest,
  ): Promise<Types.ApiResponse> {
    const response = await this.api.post(
      `/api/v1/admin/apps/${appId}/request-changes`,
      data,
    );
    return response.data;
  }

  async featureApp(
    appId: string,
    data: Types.FeatureAppRequest,
  ): Promise<Types.ApiResponse> {
    const response = await this.api.post(
      `/api/v1/admin/apps/${appId}/feature`,
      data,
    );
    return response.data;
  }

  async unpublishApp(
    appId: string,
    data: Types.UnpublishAppRequest,
  ): Promise<Types.ApiResponse> {
    const response = await this.api.post(
      `/api/v1/admin/apps/${appId}/unpublish`,
      data,
    );
    return response.data;
  }

  // ============================================
  // Security Vetting
  // ============================================

  async listSecurityScans(params?: {
    status?: Types.ScanStatus;
    severity?: Types.Severity;
    app_id?: string;
  }): Promise<Types.SecurityScansResponse> {
    const response = await this.api.get("/api/v1/admin/security/scans", {
      params,
    });
    return response.data;
  }

  async getScanDetails(scanId: string): Promise<Types.ScanDetails> {
    const response = await this.api.get(
      `/api/v1/admin/security/scans/${scanId}`,
    );
    return response.data;
  }

  async initiateScan(
    data: Types.InitiateScanRequest,
  ): Promise<Types.ApiResponse> {
    const response = await this.api.post("/api/v1/admin/security/scans", data);
    return response.data;
  }

  async updateVulnerability(
    vulnId: string,
    data: Types.UpdateVulnerabilityRequest,
  ): Promise<Types.ApiResponse> {
    const response = await this.api.put(
      `/api/v1/admin/security/vulnerabilities/${vulnId}`,
      data,
    );
    return response.data;
  }

  // ============================================
  // Marketplace Management
  // ============================================

  async getMarketplaceStats(): Promise<Types.MarketplaceStats> {
    const response = await this.api.get("/api/v1/admin/marketplace/stats");
    return response.data;
  }

  async updateAppCategories(
    data: Types.UpdateCategoriesRequest,
  ): Promise<Types.ApiResponse> {
    const response = await this.api.put(
      "/api/v1/admin/marketplace/categories",
      data,
    );
    return response.data;
  }

  async manageFeaturedApps(
    data: Types.ManageFeaturedAppsRequest,
  ): Promise<Types.ApiResponse> {
    const response = await this.api.post(
      "/api/v1/admin/marketplace/featured",
      data,
    );
    return response.data;
  }

  async getFlaggedReviews(): Promise<Types.FlaggedReviewsResponse> {
    const response = await this.api.get(
      "/api/v1/admin/marketplace/reviews/flagged",
    );
    return response.data;
  }

  async removeReview(
    reviewId: string,
    data: Types.RemoveReviewRequest,
  ): Promise<Types.ApiResponse> {
    const response = await this.api.delete(
      `/api/v1/admin/marketplace/reviews/${reviewId}`,
      { data },
    );
    return response.data;
  }

  // ============================================
  // Fee Configuration
  // ============================================

  async getActiveFeeConfig(): Promise<Types.FeeConfiguration> {
    const response = await this.api.get("/api/v1/admin/fees/configs/active");
    return response.data;
  }

  async createFeeConfig(
    data: Types.CreateFeeConfigRequest,
  ): Promise<Types.ApiResponse> {
    const response = await this.api.post("/api/v1/admin/fees/configs", data);
    return response.data;
  }

  async activateFeeConfig(
    configId: string,
    data: Types.ActivateFeeConfigRequest,
  ): Promise<Types.ApiResponse> {
    const response = await this.api.post(
      `/api/v1/admin/fees/configs/${configId}/activate`,
      data,
    );
    return response.data;
  }

  async assignCustomFee(
    data: Types.AssignCustomFeeRequest,
  ): Promise<Types.ApiResponse> {
    const response = await this.api.post(
      "/api/v1/admin/fees/assignments",
      data,
    );
    return response.data;
  }

  async getRevenueReport(params?: {
    period?: string;
    breakdown?: "app" | "developer" | "category";
  }): Promise<Types.RevenueReport> {
    const response = await this.api.get("/api/v1/admin/fees/reports/revenue", {
      params,
    });
    return response.data;
  }

  // ============================================
  // Platform Analytics
  // ============================================

  async getPlatformOverview(params?: {
    period?: "today" | "week" | "month" | "year";
    compare_to?: "previous_period";
  }): Promise<Types.PlatformOverview> {
    const response = await this.api.get("/api/v1/admin/analytics/overview", {
      params,
    });
    return response.data;
  }

  async getAPIUsageAnalytics(): Promise<Types.APIUsageAnalytics> {
    const response = await this.api.get("/api/v1/admin/analytics/api-usage");
    return response.data;
  }

  async getDeveloperGrowthMetrics(): Promise<Types.DeveloperGrowthMetrics> {
    const response = await this.api.get(
      "/api/v1/admin/analytics/developer-growth",
    );
    return response.data;
  }

  // ============================================
  // Tenant App Management
  // ============================================

  async listTenantInstallations(params?: {
    app_id?: string;
    tenant_id?: string;
    status?: "active" | "inactive" | "suspended";
  }): Promise<Types.TenantInstallationsResponse> {
    const response = await this.api.get("/api/v1/admin/tenants/installations", {
      params,
    });
    return response.data;
  }

  async suspendTenantInstallation(
    installationId: string,
    data: Types.SuspendInstallationRequest,
  ): Promise<Types.ApiResponse> {
    const response = await this.api.post(
      `/api/v1/admin/tenants/installations/${installationId}/suspend`,
      data,
    );
    return response.data;
  }

  async getInstallationDetails(
    installationId: string,
  ): Promise<Types.InstallationDetails> {
    const response = await this.api.get(
      `/api/v1/admin/tenants/installations/${installationId}`,
    );
    return response.data;
  }

  // ============================================
  // System Configuration
  // ============================================

  async updatePlatformSettings(
    data: Types.PlatformSettings,
  ): Promise<Types.ApiResponse> {
    const response = await this.api.put("/api/v1/admin/config/platform", data);
    return response.data;
  }

  async getSystemHealth(): Promise<Types.SystemHealth> {
    const response = await this.api.get("/api/v1/admin/system/health");
    return response.data;
  }

  async getAuditLogs(params?: {
    action?: string;
    admin_id?: string;
    start_date?: string;
    end_date?: string;
    page?: number;
    limit?: number;
  }): Promise<Types.AuditLogsResponse> {
    const response = await this.api.get("/api/v1/admin/audit/logs", { params });
    return response.data;
  }

  // ============================================
  // Emergency & Bulk Operations
  // ============================================

  async emergencySuspendApp(
    data: Types.EmergencySuspendAppRequest,
  ): Promise<Types.ApiResponse> {
    const response = await this.api.post(
      "/api/v1/admin/emergency/suspend-app",
      data,
    );
    return response.data;
  }

  async bulkSuspendDevelopers(
    data: Types.BulkSuspendDevelopersRequest,
  ): Promise<Types.ApiResponse> {
    const response = await this.api.post(
      "/api/v1/admin/bulk/suspend-developers",
      data,
    );
    return response.data;
  }
}

// Export singleton instance
export const developerPlatformService = new DeveloperPlatformService();
