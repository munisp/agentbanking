import * as SecureStore from "expo-secure-store";
import { tenantApi } from "./apiService";

const CORE_BANKING_BASE = "https://54agent.upi.dev";
const DEFAULT_TENANT_ID = "bpmgd";

class TenantService {
  TENANT_CONFIG_KEY = "tenant_config";
  TENANT_ID_KEY = "tenant_id";

  /**
   * Get tenant_id from SecureStore
   */
  async getTenantId() {
    const storedTenantId = await SecureStore.getItemAsync(this.TENANT_ID_KEY);
    if (storedTenantId) {
      return storedTenantId;
    }

    return DEFAULT_TENANT_ID;
  }

  /**
   * Set tenant_id in SecureStore
   */
  async setTenantId(tenantId) {
    await SecureStore.setItemAsync(this.TENANT_ID_KEY, tenantId);
  }

  /**
   * Get tenant config from SecureStore
   */
  async getTenantConfig() {
    try {
      const configStr = await SecureStore.getItemAsync(this.TENANT_CONFIG_KEY);
      if (configStr) {
        return JSON.parse(configStr);
      }
      return null;
    } catch (error) {
      console.error("Error getting tenant config:", error);
      return null;
    }
  }

  /**
   * Get Keycloak realm from tenant config feature flags
   */
  async getKeycloakRealm() {
    const config = await this.getTenantConfig();
    if (config?.feature_flags) {
      const authFeature = config.feature_flags.find((f) => f.name === "auth");
      if (authFeature?.config?.realm) {
        return authFeature.config.realm;
      }
    }
    return (await this.getTenantId()) || "remittance";
  }

  /**
   * Get Keycloak public key from tenant config feature flags
   */
  async getKeycloakPubKey() {
    const config = await this.getTenantConfig();
    if (config?.feature_flags) {
      const authFeature = config.feature_flags.find((f) => f.name === "auth");
      if (authFeature?.config?.public_rsa_key) {
        return authFeature.config.public_rsa_key;
      }
    }
    return "default";
  }

  /**
   * Fetch tenant data from API and cache it
   */
  async getTenant(tenantId) {
    // Check for existing tenant config in SecureStore first (cache)
    const existingConfig = await this.getTenantConfig();
    if (existingConfig) {
      return existingConfig;
    }

    const id = tenantId || (await this.getTenantId());

    if (!id) {
      throw new Error(
        "Tenant ID is required. Please set TENANT_ID in environment variables.",
      );
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

        // Cache tenant config in SecureStore
        await SecureStore.setItemAsync(
          this.TENANT_CONFIG_KEY,
          JSON.stringify(tenant),
        );

        // Also store tenant_id separately for quick access
        if (tenant.tenant_id) {
          await this.setTenantId(tenant.tenant_id);
        }

        console.log(
          "Tenant configuration loaded and cached:",
          tenant.tenant_id,
        );
        return tenant;
      }

      throw new Error("Invalid tenant response from API");
    } catch (error) {
      console.error("Error fetching tenant:", error);
      throw error;
    }
  }

  /**
   * Clear tenant config from SecureStore
   */
  async clearTenantConfig() {
    try {
      await SecureStore.deleteItemAsync(this.TENANT_CONFIG_KEY);
      await SecureStore.deleteItemAsync(this.TENANT_ID_KEY);
      console.log("Tenant configuration cleared");
    } catch (error) {
      console.error("Error clearing tenant config:", error);
    }
  }

  /**
   * Reload tenant config from API
   */
  async reloadTenantConfig(tenantId) {
    await this.clearTenantConfig();
    return this.getTenant(tenantId);
  }
}

export default new TenantService();
