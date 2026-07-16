import type {
  AxiosError,
  AxiosInstance,
  AxiosRequestConfig,
  InternalAxiosRequestConfig,
} from "axios";
import axios from "axios";
import { BACKEND_URL } from "../const";
import { tenantService } from "./tenant";
import { getTenantHeaders } from "./tenant/getTenantHeaders";

function getTenantHeadersFromStorage(): Record<string, string> {
  // First try to get from localStorage
  const tenantConfigStr = localStorage.getItem("tenant_config");
  if (tenantConfigStr) {
    try {
      const parsed = JSON.parse(tenantConfigStr);
      // Handle case where config might be nested under 'tenant' key
      const tenantConfig = parsed.tenant || parsed;
      if (import.meta.env.DEV) {
        console.log(
          "getTenantHeadersFromStorage: parsed config from localStorage",
          parsed,
        );
        console.log(
          "getTenantHeadersFromStorage: using tenant config",
          tenantConfig,
        );
      }
      const headers = getTenantHeaders(tenantConfig);
      // Only return if we have some headers, otherwise fall through to tenantService
      if (Object.keys(headers).length > 0) {
        return headers;
      }
    } catch (error) {
      console.error("Failed to parse tenant config from localStorage:", error);
    }
  }

  // Fallback to tenantService if localStorage doesn't have config or headers are empty
  try {
    const tenantConfig = tenantService.getTenantConfig();
    if (tenantConfig) {
      if (import.meta.env.DEV) {
        console.log(
          "getTenantHeadersFromStorage: using tenant config from tenantService",
          tenantConfig,
        );
      }
      return getTenantHeaders(tenantConfig);
    }
  } catch (error) {
    console.error("Failed to get tenant config from tenantService:", error);
  }

  if (import.meta.env.DEV) {
    console.warn(
      "getTenantHeadersFromStorage: no tenant config found in localStorage or tenantService",
    );
  }
  return {};
}

const initialTenantHeaders = getTenantHeadersFromStorage();

const apiClient: AxiosInstance = axios.create({
  baseURL: BACKEND_URL,
  timeout: 60000,
  headers: {
    "Content-Type": "application/json",
    ...initialTenantHeaders,
  },
});

Object.assign(apiClient.defaults.headers.common || {}, initialTenantHeaders);

apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem("auth_token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;

      // Try to extract x-keycloak-id from JWT token if not in tenant headers
      try {
        const parts = token.split(".");
        if (parts.length === 3) {
          const payload = JSON.parse(atob(parts[1]));
          // Check if x-keycloak-id is missing from tenant headers
          const tenantHeaders = getTenantHeadersFromStorage();
          if (!tenantHeaders["x-keycloak-id"]) {
            // Try to get from token payload (sub, id, keycloak_id, or user_id)
            const keycloakId =
              payload.sub ||
              payload.id ||
              payload.keycloak_id ||
              payload.user_id;
            if (keycloakId) {
              config.headers["x-keycloak-id"] = String(keycloakId);
              if (import.meta.env.DEV) {
                console.log(
                  "getTenantHeadersFromStorage: extracted x-keycloak-id from JWT token:",
                  keycloakId,
                );
              }
            }
          }
        }
      } catch (e) {
        // Ignore JWT parsing errors
        if (import.meta.env.DEV) {
          console.warn("Failed to parse JWT token for x-keycloak-id:", e);
        }
      }
    }

    // Skip tenant headers for tenant config fetch endpoint (to avoid circular dependency)
    const isTenantConfigEndpoint =
      config.url?.includes("/tenant-management/tenant/") && !token;

    if (!isTenantConfigEndpoint) {
      const tenantHeaders = getTenantHeadersFromStorage();

      // Always set headers, even if empty
      Object.assign(config.headers, tenantHeaders);
      Object.assign(apiClient.defaults.headers.common || {}, tenantHeaders);

      // If x-ledger-id is not in tenant config, fall back to localStorage / env — throw if missing
      if (!config.headers["x-ledger-id"]) {
        const ledgerId =
          localStorage.getItem("ledger_id") ||
          (import.meta.env.VITE_LEDGER_ID ? String(import.meta.env.VITE_LEDGER_ID) : null);
        if (!ledgerId) throw new Error("Missing x-ledger-id: user session is invalid");
        config.headers["x-ledger-id"] = ledgerId;
      }

      // If x-mint-account-id is not in tenant config, fall back to localStorage / env / ledger-id — throw if missing
      if (!config.headers["x-mint-account-id"]) {
        const mintId =
          localStorage.getItem("mint_id") ||
          (import.meta.env.VITE_MINT_ID ? String(import.meta.env.VITE_MINT_ID) : null) ||
          (config.headers["x-ledger-id"] as string | undefined) ||
          null;
        if (!mintId) throw new Error("Missing x-mint-account-id: user session is invalid");
        config.headers["x-mint-id"]         = mintId;
        config.headers["x-mint-account-id"] = mintId;
      }

      // Debug logging
      if (import.meta.env.DEV) {
        console.log("Request URL:", config.url);
        console.log("Tenant headers being added:", tenantHeaders);
        console.log("All request headers:", Object.keys(config.headers || {}));
      }
    } else if (import.meta.env.DEV) {
      console.log(
        "Skipping tenant headers for tenant config fetch:",
        config.url,
      );
    }

    return config;
  },
  (error: AxiosError) => {
    return Promise.reject(error);
  },
);

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => {
    return response;
  },
  (error: AxiosError) => {
    // Handle common errors
    if (error.response) {
      switch (error.response.status) {
        case 401:
          // Unauthorized - clear token and redirect to login
          localStorage.removeItem("auth_token");
          localStorage.removeItem("auth_user");
          localStorage.removeItem("54link-dev_auth");
          if (window.location.pathname !== "/login") {
            window.location.href = "/login";
          }
          break;
        case 403:
          console.error(
            "Forbidden: You do not have permission to access this resource",
          );
          break;
        case 404:
          console.error("Not Found: The requested resource does not exist");
          break;
        case 500:
          console.error("Server Error: Something went wrong on the server");
          break;
        default:
          console.error("API Error:", error.message);
      }
    } else if (error.request) {
      console.error("Network Error: No response received from server");
    } else {
      console.error("Error:", error.message);
    }
    return Promise.reject(error);
  },
);

export default apiClient;

// Helper function for API calls
export const apiRequest = async <T = unknown>(
  config: AxiosRequestConfig,
): Promise<T> => {
  const response = await apiClient.request<T>(config);
  return response.data;
};
