import { getTenantHeaders } from "./getTenantHeaders";

/**
 * Get tenant headers from localStorage
 * This helper reads the tenant config from localStorage and extracts headers
 */
export function getTenantHeadersFromStorage(): Record<string, string> {
  const tenantConfigStr = localStorage.getItem("tenant_config");
  if (!tenantConfigStr) {
    if (import.meta.env.DEV) {
      console.warn(
        "getTenantHeadersFromStorage: tenant_config not found in localStorage",
      );
    }
    return {};
  }
  try {
    const parsed = JSON.parse(tenantConfigStr);
    // Handle case where config might be nested under 'tenant' key
    const tenantConfig = parsed.tenant || parsed;
    if (import.meta.env.DEV) {
      console.log("getTenantHeadersFromStorage: parsed config", parsed);
      console.log(
        "getTenantHeadersFromStorage: using tenant config",
        tenantConfig,
      );
    }
    return getTenantHeaders(tenantConfig);
  } catch (error) {
    console.error("Failed to parse tenant config:", error);
    return {};
  }
}
