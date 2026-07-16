import apiClient from "../api";
import { getTenantHeaders as extractTenantHeaders } from "./getTenantHeaders";

export interface TenantContact {
  id: string;
  name: string;
  email: string;
  phone: string;
}

export interface TenantBranding {
  id: string;
  logo_url: string;
  favicon_url: string;
  primary_color: string;
  secondary_color: string;
  domain: string;
}

export interface TenantBilling {
  id: number;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
  plan: string;
}

export interface FeatureFlagConfig {
  id: string;
  name: string;
  is_enabled: boolean;
  config: Record<string, unknown>;
}

export interface Tenant {
  id: number;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
  name: string;
  status: string;
  tenant_id: string;
  status_message: string | null;
  contact: TenantContact;
  branding: TenantBranding;
  billing: TenantBilling;
  feature_flags: FeatureFlagConfig[];
  admin_feature_flags?: FeatureFlagConfig[];
  super_admin_feature_flags?: FeatureFlagConfig[];
  super_tenant_feature_flags?: FeatureFlagConfig[];
  cac_certificate_url?: string;
  cbn_license_url?: string;
}

export interface GetTenantResponse {
  message: string;
  tenant: Tenant;
}

export interface TenantMetrics {
  total: string | number;
  standard: string | number;
  premium: string | number;
  enterprise: string | number;
}

export interface GetAllTenantsResponse {
  message: string;
  metrics: TenantMetrics;
  tenants: Tenant[];
}

// COMMENTED OUT: User roles removed - app is only for 54link
// export type UserRole = 'admin' | 'super_admin' | 'super_tenant';

// 54link default data - no tenant config needed
const LINK54_DEFAULT_DATA: Tenant = {
  id: 1,
  created_at: "2025-01-01T00:00:00.000Z",
  updated_at: "2025-01-01T00:00:00.000Z",
  deleted_at: null,
  name: "54Link",
  status: "active",
  tenant_id: "bpmgd",
  status_message: null,
  contact: {
    id: "54link-contact-id",
    name: "54Link Admin",
    email: "admin@54link.com",
    phone: "+2340000000000",
  },
  branding: {
    id: "54link-branding-id",
    logo_url: "",
    favicon_url: "",
    primary_color: "#22c55e", // Green for 54Link
    secondary_color: "#16a34a", // Darker green
    domain: "54link.com",
  },
  billing: {
    id: 1,
    created_at: "2025-01-01T00:00:00.000Z",
    updated_at: "2025-01-01T00:00:00.000Z",
    deleted_at: null,
    plan: "enterprise",
  },
  // 54link default feature flags - all enabled (must match backend FeatureFlag enum)
  feature_flags: [
    { id: "f1",  name: "auth",                  is_enabled: true, config: {} },
    { id: "f2",  name: "user_management",        is_enabled: true, config: {} },
    { id: "f3",  name: "accounts",               is_enabled: true, config: {} },
    { id: "f4",  name: "payments",               is_enabled: true, config: {} },
    { id: "f5",  name: "reporting",              is_enabled: true, config: {} },
    { id: "f6",  name: "audit",                  is_enabled: true, config: {} },
    { id: "f7",  name: "loans",                  is_enabled: true, config: {} },
    { id: "f8",  name: "savings",                is_enabled: true, config: {} },
    { id: "f9",  name: "lpo",                    is_enabled: true, config: {} },
    { id: "f10", name: "dispute",                is_enabled: true, config: {} },
    { id: "f11", name: "card_management",        is_enabled: true, config: {} },
    { id: "f12", name: "teller",                 is_enabled: true, config: {} },
    { id: "f13", name: "treasury",               is_enabled: true, config: {} },
    { id: "f14", name: "fx",                     is_enabled: true, config: {} },
    { id: "f15", name: "virtual_accounts",       is_enabled: true, config: {} },
    { id: "f16", name: "fraud_detection",        is_enabled: true, config: {} },
    { id: "f17", name: "risk_management",        is_enabled: true, config: {} },
    { id: "f18", name: "chart_of_accounts",      is_enabled: true, config: {} },
    { id: "f19", name: "reconciliation",         is_enabled: true, config: {} },
    { id: "f20", name: "relationship_manager",   is_enabled: true, config: {} },
    { id: "f21", name: "document_management",    is_enabled: true, config: {} },
    { id: "f22", name: "communication_hub",      is_enabled: true, config: {} },
    { id: "f23", name: "trade_finance",          is_enabled: true, config: {} },
    { id: "f24", name: "erp_integration",        is_enabled: true, config: {} },
    { id: "f25", name: "temporal_access",        is_enabled: true, config: {} },
    { id: "f26", name: "employee_management",    is_enabled: true, config: {} },
    { id: "f27", name: "merchant_management",    is_enabled: true, config: {} },
    { id: "f28", name: "developer_platform",     is_enabled: true, config: {} },
    { id: "f29", name: "salary_processing",      is_enabled: true, config: {} },
    { id: "f30", name: "maker_checker",          is_enabled: true, config: {} },
    { id: "f31", name: "cooperative_management", is_enabled: true, config: {} },
  ],
  // COMMENTED OUT: Role-based feature flags removed - app is only for 54link
  // admin_feature_flags: [...],
  // super_admin_feature_flags: [...],
  // super_tenant_feature_flags: [...]
};

// All individual features available on the platform.
// Used as the global catalog when the API is unavailable.
// Must stay in sync with the backend FeatureFlag enum in services/tenant-management/src/utils/enums.ts
export const GLOBAL_FEATURE_CATALOG: Array<{ name: string; label: string }> = [
  // Core
  { name: "auth", label: "Authentication" },
  { name: "user_management", label: "User Management" },
  { name: "accounts", label: "Accounts" },
  { name: "payments", label: "Payments" },
  { name: "reporting", label: "Reporting" },
  { name: "notifications", label: "Notifications" },
  { name: "kyc_kyb", label: "KYC / KYB" },
  { name: "compliance", label: "Compliance" },
  { name: "audit", label: "Audit" },
  // Banking Channels
  { name: "mobile_banking", label: "Mobile Banking" },
  { name: "ussd_banking", label: "USSD Banking" },
  { name: "whatsapp_banking", label: "WhatsApp Banking" },
  { name: "agent_banking", label: "Agent Banking" },
  { name: "chatbot", label: "Chatbot" },
  { name: "pos_terminal", label: "POS Terminal" },
  // Payments & Transfers
  { name: "bill_payments", label: "Bill Payments" },
  { name: "qr_payments", label: "QR Payments" },
  { name: "bulk_payments", label: "Bulk Payments" },
  { name: "standing_orders", label: "Standing Orders" },
  { name: "remittance", label: "Remittance" },
  { name: "atm_management", label: "ATM Management" },
  // Cards & Accounts
  { name: "teller", label: "Teller" },
  { name: "card_management", label: "Card Management" },
  { name: "virtual_accounts", label: "Virtual Accounts" },
  { name: "fx", label: "Foreign Exchange (FX)" },
  // Lending & Credit
  { name: "loans", label: "Loans" },
  { name: "education_loans", label: "Education Loans" },
  { name: "mortgage", label: "Mortgage" },
  { name: "lpo", label: "LPO (Local Purchase Order)" },
  { name: "bnpl", label: "Buy Now Pay Later" },
  // Savings & Investments
  { name: "savings", label: "Savings" },
  { name: "smart_savings", label: "Smart Savings" },
  { name: "esusu", label: "Esusu" },
  { name: "escrow", label: "Escrow" },
  { name: "investment", label: "Investment" },
  // Risk, Fraud & Compliance
  { name: "fraud_detection", label: "Fraud Detection" },
  { name: "risk_management", label: "Risk Management" },
  { name: "dispute", label: "Dispute Management" },
  { name: "aml_compliance", label: "AML Compliance" },
  { name: "sanctions_screening", label: "Sanctions Screening" },
  { name: "regulatory_reporting", label: "Regulatory Reporting" },
  // Insurance
  { name: "insurance", label: "Insurance" },
  { name: "etherisc", label: "Etherisc" },
  // Treasury & Finance
  { name: "treasury", label: "Treasury" },
  { name: "chart_of_accounts", label: "Chart of Accounts" },
  { name: "reconciliation", label: "Reconciliation" },
  { name: "finance", label: "Finance" },
  // Specialised Finance
  { name: "islamic_banking", label: "Islamic Banking" },
  { name: "agriculture_finance", label: "Agriculture Finance" },
  { name: "supply_chain_finance", label: "Supply Chain Finance" },
  { name: "trade_finance", label: "Trade Finance" },
  { name: "carbon_credits", label: "Carbon Credits" },
  { name: "cooperative_management", label: "Cooperative Management" },
  { name: "diaspora_banking", label: "Diaspora Banking" },
  { name: "microfinance", label: "Microfinance" },
  // Wealth & Capital Markets
  { name: "wealth_management", label: "Wealth Management" },
  { name: "pension", label: "Pension" },
  { name: "leasing", label: "Leasing" },
  { name: "securities_trading", label: "Securities Trading" },
  // Operations & Workflow
  { name: "employee_management", label: "Employee Management" },
  { name: "relationship_manager", label: "Relationship Manager" },
  { name: "document_management", label: "Document Management" },
  { name: "communication_hub", label: "Communication Hub" },
  { name: "merchant_management", label: "Merchant Management" },
  { name: "salary_processing", label: "Salary Processing" },
  { name: "maker_checker", label: "Maker-Checker" },
  { name: "product_factory", label: "Product Factory" },
  { name: "gamification", label: "Gamification" },
  // Platform & Integration
  { name: "open_banking", label: "Open Banking" },
  { name: "biometric_auth", label: "Biometric Auth" },
  { name: "developer_platform", label: "Developer Platform" },
  { name: "erp_integration", label: "ERP Integration" },
  { name: "temporal_access", label: "Temporal Access" },
];

class TenantService {
  // private readonly TENANT_CONFIG_KEY = 'tenant_config';
  private readonly TENANT_ID_KEY = "tenant_id";

  /**
   * Extract tenant_id from URL if present
   */
  private extractTenantIdFromUrl(): string | null {
    if (typeof window === "undefined") return null;

    const path = window.location.pathname;
    // Check for patterns like /tenant-management/tenant/{tenant_id} or /tenant/{tenant_id}
    const tenantMatch = path.match(/\/tenant[^/]*\/([^/]+)/);
    if (tenantMatch && tenantMatch[1]) {
      return tenantMatch[1];
    }

    return null;
  }

  /**
   * Get tenant_id from environment variable, localStorage, or URL
   * COMMENTED OUT: Not using API calls for now
   * Kept for when API calls are re-enabled
   */
  // eslint-disable-next-line @typescript-eslint/ban-ts-comment
  // @ts-ignore - Kept for future use when API calls are re-enabled
  private getTenantId(): string | null {
    // First check environment variable
    const envTenantId = import.meta.env.VITE_TENANT_ID || "bpmgd";
    if (envTenantId) {
      return envTenantId;
    }

    // Then check localStorage
    const storedTenantId = localStorage.getItem(this.TENANT_ID_KEY);
    if (storedTenantId) {
      return storedTenantId;
    }

    // Try to extract from URL
    const urlTenantId = this.extractTenantIdFromUrl();
    if (urlTenantId) {
      // Store it for future use
      this.setTenantId(urlTenantId);
      return urlTenantId;
    }

    // Default fallback (can be removed if tenant_id is always provided)
    return null;
  }

  /**
   * Set tenant_id in localStorage
   */
  setTenantId(tenantId: string): void {
    localStorage.setItem(this.TENANT_ID_KEY, tenantId);
  }

  /**
   * Change tenant ID and fetch new config
   * Useful for switching tenants dynamically
   */
  async changeTenant(tenantId: string): Promise<Tenant> {
    this.setTenantId(tenantId);
    // Clear old config to force fresh fetch
    // Removed call to non-existent removeTenantConfig
    // Fetch new tenant config
    return await this.getTenant(tenantId);
  }

  /**
   * Update tenant
   * @param tenantId - The tenant ID to update
   * @param data - The data to update
   * @returns Promise resolving to the updated tenant
   */
  async updateTenant(
    tenantId: string,
    data: Record<string, unknown>,
  ): Promise<Tenant> {
    try {
      const response = await apiClient.put<GetTenantResponse>(
        `/tenant-management/tenant/${tenantId}`,
        data,
      );

      // API returns { status: "success", tenant: {...} } or { message: "success", tenant: {...} }
      if (
        (response.data as any).status === "success" ||
        response.data.message === "success"
      ) {
        if (response.data.tenant) {
          if (import.meta.env.DEV) {
            console.log("Update tenant API response:", response.data);
          }
          return response.data.tenant;
        }
      }

      throw new Error("Invalid response format from tenant API");
    } catch (error: unknown) {
      const errorMessage =
        error instanceof Error ? error.message : "Unknown error";
      console.error("Error updating tenant:", errorMessage);
      throw this.handleError(error);
    }
  }

  async deleteTenant(tenantId: string): Promise<void> {
    try {
      const response = await apiClient.delete(`/tenant-management/tenant/${tenantId}`);

      if (response.data.message === "success") {
        if (import.meta.env.DEV) {
          console.log("Delete tenant API response:", response.data);
        }
        // Clear tenant config if the deleted tenant is the current one
        const currentTenantId = this.getTenantId();
        if (currentTenantId === tenantId) {
          // Removed call to non-existent removeTenantConfig
          localStorage.removeItem(this.TENANT_ID_KEY);
        }
        return;
      }

      throw new Error("Invalid response format from tenant API");
    } catch (error: unknown) {
      const errorMessage =
        error instanceof Error ? error.message : "Unknown error";
      console.error("Error deleting tenant:", errorMessage);
      throw this.handleError(error);
    }
  }

  /**
   * Get all tenants
   * @returns Promise resolving to an object with tenants array and metrics
   */
  async getAllTenants(): Promise<{
    tenants: Tenant[];
    metrics: TenantMetrics;
  }> {
    try {
      const response = await apiClient.get<GetAllTenantsResponse>(
        "/tenant-management/tenant/all",
      );

      if (response.data.message === "success") {
        if (import.meta.env.DEV) {
          console.log("Get all tenants API response:", response.data);
        }
        return {
          tenants: response.data.tenants || [],
          metrics: response.data.metrics || {
            total: 0,
            standard: 0,
            premium: 0,
            enterprise: 0,
          },
        };
      }

      throw new Error("Invalid response format from tenant API");
    } catch (error: unknown) {
      const errorMessage =
        error instanceof Error ? error.message : "Unknown error";
      console.error("Error fetching all tenants:", errorMessage);
      throw this.handleError(error);
    }
  }

  /**
   * Fetch all global features available on the platform.
   * Falls back to GLOBAL_FEATURE_CATALOG if the API is unavailable.
   */
  async getGlobalFeatures(): Promise<FeatureFlagConfig[]> {
    try {
      const response = await apiClient.get<{
        message: string;
        tenants: Array<{ name: string; is_enabled: boolean }>;
      }>("/tenant-management/tenant/features/global");
      if (
        response.data.message === "success" &&
        Array.isArray(response.data.tenants)
      ) {
        return response.data.tenants.map((f) => ({
          id: f.name,
          name: f.name,
          is_enabled: f.is_enabled,
          config: {},
        }));
      }
      throw new Error("Unexpected response shape");
    } catch {
      return GLOBAL_FEATURE_CATALOG.map((f) => ({
        id: f.name,
        name: f.name,
        is_enabled: false,
        config: {},
      }));
    }
  }

  /**
   * Get 54link default data - no tenant config needed
   * @param _tenantId - Not used, kept for compatibility
   */
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  async getTenant(_tenantId?: string): Promise<Tenant> {
    // Always return 54link default data - no storage needed
    if (import.meta.env.DEV) {
      console.log("Using 54link default data (no tenant config)");
    }

    return LINK54_DEFAULT_DATA;

    /* COMMENTED OUT API CALL - Using mock data for now
    const id = tenantId || this.getTenantId();
    
    if (!id) {
      throw new Error('Tenant ID is required. Please set VITE_TENANT_ID environment variable or call setTenantId() first.');
    }

    try {
      const response = await apiClient.get<GetTenantResponse>(
        `/tenant-management/tenant/${id}`
      );

      if (response.data.message === 'success' && response.data.tenant) {
        const tenant = response.data.tenant;
        
        // Debug logging
        if (import.meta.env.DEV) {
          console.log('Tenant API response:', response.data);
          console.log('Tenant object to store:', tenant);
          console.log('Feature flags in response:', tenant.feature_flags);
        }
        
        // Store tenant config in localStorage
        this.setTenantConfig(tenant);
        return tenant;
      }

      throw new Error('Invalid response format from tenant API');
    } catch (error: any) {
      throw this.handleError(error);
    }
    */
  }

  /**
   * Get tenant config - always returns 54link default data
   * No localStorage check - app is only for 54link
   */
  getTenantConfig(): Tenant | null {
    // Always return 54link default data - no tenant config needed
    return LINK54_DEFAULT_DATA;
  }

  /**
   * Set tenant config in localStorage
   * COMMENTED OUT: Not used - app always uses 54link default data
   */
  // setTenantConfig(tenant: Tenant): void {
  //   localStorage.setItem(this.TENANT_CONFIG_KEY, JSON.stringify(tenant));
  // }

  /**
   * Remove tenant config from localStorage
   * COMMENTED OUT: Not used - app always uses 54link default data
   */
  // removeTenantConfig(): void {
  //   localStorage.removeItem(this.TENANT_CONFIG_KEY);
  //   localStorage.removeItem(this.TENANT_ID_KEY);
  // }

  /**
   * Check if tenant config exists
   * Always returns true since we always have 54link default data
   */
  hasTenantConfig(): boolean {
    // Always return true - we always have 54link default data
    return true;
  }

  /**
   * Get required headers from tenant config
   * Returns an object with headers: x-tenant-id, x-ledger-id, x-mint-id, x-mint-account-id, x-staff-id
   */
  getTenantHeaders(): Record<string, string> {
    const tenant = this.getTenantConfig();
    return extractTenantHeaders(tenant);
  }

  /**
   * Get feature flags - always returns default feature flags (no role-based)
   * COMMENTED OUT: Role-based feature flags removed - app is only for 54link
   */
  getFeatureFlagsByRole(): FeatureFlagConfig[] {
    const tenant = this.getTenantConfig();
    if (!tenant) return [];
    // Always return default feature flags
    return tenant.feature_flags || [];
  }

  // COMMENTED OUT: User role methods removed - app is only for 54link
  // /**
  //  * Get current user role from localStorage
  //  */
  // getUserRole(): UserRole | null {
  //   const role = localStorage.getItem('user_role');
  //   if (role && ['admin', 'super_admin', 'super_tenant'].includes(role)) {
  //     return role as UserRole;
  //   }
  //   return null;
  // }

  /**
   * Handle API errors
   */
  private handleError(error: unknown): Error {
    if (error instanceof Error) {
      return error;
    }
    return new Error("An unexpected error occurred");
  }
}

// Export singleton instance
export const tenantService = new TenantService();
export default tenantService;
