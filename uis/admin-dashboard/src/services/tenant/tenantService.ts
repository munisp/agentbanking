import axios from "axios";

const CORE_BANKING_BASE =
  import.meta.env.VITE_CORE_BANKING_URL || "https://54agent.upi.dev";

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
}

export interface GetTenantResponse {
  message: string;
  tenant: Tenant;
}

class TenantService {
  private readonly TENANT_CONFIG_KEY = "tenant_config";
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
   */
  private getTenantId(): string | null {
    // First check environment variable
    const envTenantId = import.meta.env.VITE_TENANT_ID;

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

    // Default fallback
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
    this.removeTenantConfig();
    // Fetch new tenant config
    return await this.getTenant(tenantId);
  }

  /**
   * Fetch tenant data from API
   * @param tenantId - Optional tenant ID
   */
  async getTenant(tenantId?: string): Promise<Tenant> {
    // Check for existing tenant config in localStorage first (cache)
    const existingConfig = this.getTenantConfig();
    if (existingConfig) {
      return existingConfig;
    }

    const id = tenantId || this.getTenantId();

    if (!id) {
      throw new Error(
        "Tenant ID is required. Please set VITE_TENANT_ID environment variable or call setTenantId() first.",
      );
    }

    try {
      const response = await axios.get<GetTenantResponse>(
        `${CORE_BANKING_BASE}/tenant-management/tenant/${id}`,
      );

      if (response.data.message === "success" && response.data.tenant) {
        const tenant = response.data.tenant;

        // Debug logging
        if (import.meta.env.DEV) {
          console.log("Tenant API response:", response.data);
          console.log("Tenant object to store:", tenant);
          console.log("Feature flags in response:", tenant.feature_flags);
        }

        // Store tenant config in localStorage
        this.setTenantConfig(tenant);
        return tenant;
      }

      throw new Error("Invalid response format from tenant API");
    } catch (error: any) {
      throw this.handleError(error);
    }
  }

  /**
   * Get tenant config from localStorage
   * Returns null if no config is stored
   */
  getTenantConfig(): Tenant | null {
    const configStr = localStorage.getItem(this.TENANT_CONFIG_KEY);
    if (!configStr) {
      return null;
    }

    try {
      return JSON.parse(configStr);
    } catch {
      return null;
    }
  }

  /**
   * Set tenant config in localStorage
   */
  setTenantConfig(tenant: Tenant): void {
    localStorage.setItem(this.TENANT_CONFIG_KEY, JSON.stringify(tenant));
  }

  /**
   * Remove tenant config from localStorage
   */
  removeTenantConfig(): void {
    localStorage.removeItem(this.TENANT_CONFIG_KEY);
  }

  /**
   * Clear all tenant-related data
   */
  clearTenantData(): void {
    localStorage.removeItem(this.TENANT_CONFIG_KEY);
    localStorage.removeItem(this.TENANT_ID_KEY);
  }

  /**
   * Handle API errors
   */
  private handleError(error: any): Error {
    if (error.response) {
      const message =
        error.response.data?.message ||
        error.response.statusText ||
        "Unknown error occurred";
      return new Error(`API Error: ${message}`);
    }
    if (error.request) {
      return new Error(
        "Network error: Unable to reach the server. Please check your connection.",
      );
    }
    return new Error(error.message || "An unexpected error occurred");
  }
}

// Export singleton instance
export const tenantService = new TenantService();
