import { tenantApi } from "../utils/api";

const CORE_BANKING_BASE = "https://54agent.upi.dev";

class TenantService {
  TENANT_CONFIG_KEY = "tenant_config";
  TENANT_ID_KEY = "tenant_id";

  /**
   * Get tenant_id from environment variable or localStorage
   */
  getTenantId() {
    const envTenantId = import.meta.env.VITE_TENANT_ID;
    if (envTenantId) {
      return envTenantId;
    }

    const storedTenantId = localStorage.getItem(this.TENANT_ID_KEY);
    if (storedTenantId) {
      return storedTenantId;
    }

    return null;
  }

  /**
   * Set tenant_id in localStorage
   */
  setTenantId(tenantId) {
    localStorage.setItem(this.TENANT_ID_KEY, tenantId);
  }

  /**
   * Get Keycloak realm from tenant config feature flags
   */
  getKeycloakRealm() {
    const config = this.getTenantConfig();
    if (config?.feature_flags) {
      const authFeature = config.feature_flags.find((f) => f.name === "auth");
      if (authFeature?.config?.realm) {
        return authFeature.config.realm;
      }
    }
    return this.getTenantId() || "remittance";
  }

  /**
   * Get Keycloak public key from tenant config feature flags
   */
  getKeycloakPubKey() {
    const config = this.getTenantConfig();
    if (config?.feature_flags) {
      const authFeature = config.feature_flags.find((f) => f.name === "auth");
      if (authFeature?.config?.public_rsa_key) {
        return authFeature.config.public_rsa_key;
      }
    }
    return "default";
  }

  /**
   * Fetch tenant data from API
   */
  async getTenant(tenantId) {
    const id = tenantId || this.getTenantId();

    if (!id) {
      throw new Error(
        "Tenant ID is required. Please set VITE_TENANT_ID environment variable.",
      );
    }

    // Reuse cache only when it belongs to the same tenant.
    const existingConfig = this.getTenantConfig();
    if (existingConfig?.tenant_id === id) {
      return existingConfig;
    }

    try {
      // Use direct fetch to core banking to avoid circular dependency
      const response = await fetch(
        `${CORE_BANKING_BASE}/tenant-management/tenant/${id}`,
        {
          method: "GET",
          headers: {
            "Content-Type": "application/json",
            "x-tenant-id": id,
          },
        },
      );

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();

      if (data.message === "success" && data.tenant) {
        const tenant = data.tenant;

        // Store tenant config in localStorage
        this.setTenantConfig(tenant);

        return tenant;
      }

      throw new Error("Invalid response format from tenant API");
    } catch (error) {
      console.error("Failed to fetch tenant config:", error);
      // Return a basic config if API fails
      const defaultConfig = this.getDefaultConfig();
      this.setTenantConfig(defaultConfig);
      return defaultConfig;
    }
  }

  /**
   * Get tenant config from localStorage
   */
  getTenantConfig() {
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
  setTenantConfig(tenant) {
    localStorage.setItem(this.TENANT_CONFIG_KEY, JSON.stringify(tenant));
  }

  /**
   * Remove tenant config from localStorage
   */
  removeTenantConfig() {
    localStorage.removeItem(this.TENANT_CONFIG_KEY);
  }

  /**
   * Get default tenant configuration
   */
  getDefaultConfig() {
    const tenantId = this.getTenantId() || "momopsb";
    return {
      id: 0,
      name: "Area Konnect by Fidelity",
      tenant_id: tenantId,
      status: "active",
      branding: {
        logo_url: null,
        favicon_url: null,
        primary_color: "#002082",
        secondary_color: "#6CC049",
        domain: null,
      },
      feature_flags: [
        {
          name: "auth",
          is_enabled: true,
          config: {
            realm: tenantId,
            public_rsa_key: "default",
          },
        },
      ],
    };
  }

  /**
   * Initialize tenant configuration on app startup
   */
  async initialize() {
    const tenantId = this.getTenantId();
    if (tenantId) {
      try {
        await this.getTenant(tenantId);
      } catch (error) {
        console.error("Failed to initialize tenant:", error);
      }
    }
  }
}

export const tenantService = new TenantService();
