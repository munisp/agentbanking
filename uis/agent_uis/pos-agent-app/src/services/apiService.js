/**
 * Central API client for the 54agent mobile agent dashboard.
 * All requests route through APISIX.
 *
 * Core Banking Services (https://54agent.upi.dev):
 *   /auth/*              → auth-service
 *   /user/*              → user-service
 *   /dispute/*           → dispute-service
 *   /tenant-management/* → tenant-management
 *   /admin/*             → admin-service
 *   /orchestrator/*      → orchestrator
 *   /account/*           → account-service
 *   /ledger/*            → ledger-service
 *   /payment-processing/* → payment-processing
 *   /loan/*              → loan-service
 *
 * Agency Banking Services (https://54agent.upi.dev):
 *   /agent/*             → agent-service
 *   /inventory/*         → inventory-service
 *   /network-operations/* → network-operations
 *   /pos-terminals/*     → pos-terminal-management
 *   /pos-hardware/*      → pos-hardware-management
 *   /pos-integration/*   → pos-integration
 *   /pos-management/*    → pos-management
 *   /messaging/*         → messaging-service
 *   /translation/*       → realtime-translation
 *   /store-map/*         → store-map-service
 *   /commission/*        → commission-settlement
 *   /mdm/*               → mdm-service
 *
 * Loyalty Service (https://54agent.upi.dev):
 *   /loyalty/*           → loyalty-service
 */

import * as SecureStore from "expo-secure-store";

const CORE_BANKING_BASE = "https://54agent.upi.dev";
const AGENT_BANKING_BASE = "https://54agent.upi.dev";
const REMITTANCE_BANKING_BASE = "https://54remit.upi.dev";
const DEFAULT_TENANT_ID = "bpmgd";

/**
 * Map service prefixes to their API gateway
 */
const SERVICE_BASE_URLS = {
  // Core Banking Services
  "/dispute": AGENT_BANKING_BASE,
  "/user": AGENT_BANKING_BASE,
  "/auth": AGENT_BANKING_BASE,
  "/account": AGENT_BANKING_BASE,
  "/ledger": AGENT_BANKING_BASE,
  "/payment-processing": AGENT_BANKING_BASE,
  "/loan": AGENT_BANKING_BASE,
  "/loyalty": AGENT_BANKING_BASE,
  "/tenant-management": AGENT_BANKING_BASE,
  "/admin": AGENT_BANKING_BASE,
  "/orchestrator": AGENT_BANKING_BASE,
  "/document": AGENT_BANKING_BASE,

  // Agency Banking Services (default)
  "/agent": AGENT_BANKING_BASE,
  "/inventory": AGENT_BANKING_BASE,
  "/network-operations": AGENT_BANKING_BASE,
  "/pos-terminals": AGENT_BANKING_BASE,
  "/pos-hardware": AGENT_BANKING_BASE,
  "/pos-integration": AGENT_BANKING_BASE,
  "/pos-management": AGENT_BANKING_BASE,
  "/messaging": AGENT_BANKING_BASE,
  "/translation": AGENT_BANKING_BASE,
  "/store-map": AGENT_BANKING_BASE,
  "/commission": AGENT_BANKING_BASE,
  "/mdm": AGENT_BANKING_BASE,
  "/card": AGENT_BANKING_BASE,
};

/**
 * Get the correct base URL for a given path
 */
function getBaseUrl(path) {
  for (const [prefix, baseUrl] of Object.entries(SERVICE_BASE_URLS)) {
    if (path.startsWith(prefix)) {
      return baseUrl;
    }
  }
  return AGENT_BANKING_BASE;
}

// -------------------------------------------------------------------
// Header helpers
// -------------------------------------------------------------------

/**
 * Extract tenant headers from SecureStore tenant config
 */
async function getTenantHeadersFromConfig() {
  const configStr = await SecureStore.getItemAsync("tenant_config");
  if (!configStr) {
    console.warn("No tenant config found in SecureStore");
    return {
      "x-tenant-id": DEFAULT_TENANT_ID,
      "x-tenant-name": DEFAULT_TENANT_ID,
      "x-ledger-id": "1",
      "x-mint-id": "1",
      "x-mint-account-id": "MINT_ACCOUNT",
      "x-keycloak-realm": "master",
      "x-keycloak-pub-key": "",
    };
  }

  try {
    const tenant = JSON.parse(configStr);
    const headers = {};

    // x-tenant-id
    if (tenant.tenant_id) {
      headers["x-tenant-id"] = tenant.tenant_id;
    } else {
      headers["x-tenant-id"] = DEFAULT_TENANT_ID;
    }

    // Extract from feature_flags.auth.config
    const featureFlags = Array.isArray(tenant.feature_flags)
      ? tenant.feature_flags
      : [];
    const authFeature = featureFlags.find((flag) => flag.name === "auth");

    if (authFeature?.config) {
      if (authFeature.config.realm) {
        headers["x-keycloak-realm"] = String(authFeature.config.realm);
      }
      if (authFeature.config.public_rsa_key) {
        headers["x-keycloak-pub-key"] = String(
          authFeature.config.public_rsa_key,
        );
      }
    }

    return headers;
  } catch (error) {
    const errorMsg =
      error?.message || String(error) || "Error parsing tenant config";
    console.error("Error parsing tenant config:", errorMsg);
    return {
      "x-tenant-id": DEFAULT_TENANT_ID,
      "x-tenant-name": DEFAULT_TENANT_ID,
      "x-ledger-id": "1",
      "x-mint-id": "1",
      "x-mint-account-id": "MINT_ACCOUNT",
      "x-keycloak-realm": "master",
      "x-keycloak-pub-key": "",
    };
  }
}

export async function tenantHeaders() {
  return {
    "Content-Type": "application/json",
    ...(await getTenantHeadersFromConfig()),
  };
}

export async function getTenantId() {
  try {
    const configStr = await SecureStore.getItemAsync("tenant_config");
    if (!configStr) {
      return DEFAULT_TENANT_ID;
    }
    const tenant = JSON.parse(configStr);
    return tenant.tenant_id || DEFAULT_TENANT_ID;
  } catch (error) {
    const errorMsg =
      error?.message || String(error) || "Error getting tenant ID";
    console.error("Error getting tenant ID:", errorMsg);
    return DEFAULT_TENANT_ID;
  }
}

export async function authHeaders() {
  const token = await SecureStore.getItemAsync("authToken");
  const tenantHdrs = await getTenantHeadersFromConfig();

  // Add keycloak-id if not in tenant headers
  if (!tenantHdrs["x-keycloak-id"]) {
    const keycloakId = await SecureStore.getItemAsync("keycloakId");
    if (keycloakId) {
      tenantHdrs["x-keycloak-id"] = keycloakId;
    }
  }

  // Add ledger-id if not in tenant headers
  if (!tenantHdrs["x-ledger-id"]) {
    const ledgerId = (await SecureStore.getItemAsync("ledgerId")) || "1";
    if (ledgerId) {
      tenantHdrs["x-ledger-id"] = ledgerId;
    }
  }

  if (!tenantHdrs["x-tenant-name"]) {
    tenantHdrs["x-tenant-name"] =
      tenantHdrs["x-tenant-id"] || DEFAULT_TENANT_ID;
  }

  if (!tenantHdrs["x-mint-id"]) {
    tenantHdrs["x-mint-id"] = "1";
  }

  if (!tenantHdrs["x-mint-account-id"]) {
    tenantHdrs["x-mint-account-id"] = "MINT_ACCOUNT";
  }

  if (!tenantHdrs["x-keycloak-realm"]) {
    tenantHdrs["x-keycloak-realm"] = "master";
  }

  if (!tenantHdrs["x-keycloak-pub-key"]) {
    tenantHdrs["x-keycloak-pub-key"] = "";
  }

  const tenantConfig = await SecureStore.getItemAsync("tenant_config");
  if (tenantConfig) {
    const tenant = JSON.parse(tenantConfig);
    const featureFlags = Array.isArray(tenant.feature_flags)
      ? tenant.feature_flags
      : [];
    const accountsFeature = featureFlags.find(
      (flag) => flag.name === "accounts" && flag.config && flag.config.account,
    );
    if (accountsFeature?.config?.account?.id) {
      tenantHdrs["x-mint-account-id"] = String(
        accountsFeature.config.account.id,
      );
    }
  }

  return {
    "Content-Type": "application/json",
    ...tenantHdrs,
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

// -------------------------------------------------------------------
// Generic request wrapper
// -------------------------------------------------------------------

async function request(path, options = {}) {
  const baseUrl = getBaseUrl(path);
  const url = `${baseUrl}${path}`;

  // Ensure headers are included
  const headers = options.headers || {};
  const config = {
    ...options,
    headers,
  };

  try {
    console.log(`Requesting: ${url}`);
    const res = await fetch(url, config);

    // Handle empty responses (e.g. 204 No Content)
    if (res.status === 204) return null;

    const json = await res.json().catch(() => null);

    if (!res.ok) {
      const message =
        json?.detail ?? json?.message ?? `${res.status} ${res.statusText}`;
      throw new Error(message);
    }

    return json;
  } catch (error) {
    // If it's already an Error with a message, rethrow it
    if (error.message && !error.message.includes("JSON Parse error")) {
      console.error(`Request failed for ${url}:`, error.message);
      throw error;
    }
    // Handle network errors
    const errorMsg = error?.toString() || "Unknown error";
    console.error(`Network request failed for ${url}:`, errorMsg);
    throw new Error(`Network request failed: ${errorMsg}`);
  }
}

// -------------------------------------------------------------------
// Auth API
// -------------------------------------------------------------------

export const authApi = {
  /** Health check */
  health: () => fetch(`${CORE_BANKING_BASE}/auth/health`).then((r) => r.json()),

  /** Login — returns access_token, refresh_token, user info */
  login: async (email, password, userType = null) => {
    const headers = await getTenantHeadersFromConfig();

    const requiredHeaders = ["x-keycloak-realm", "x-keycloak-pub-key"];
    const missingHeaders = requiredHeaders.filter((h) => !headers[h]);

    if (missingHeaders.length > 0) {
      throw new Error(
        "Tenant configuration not loaded. Please refresh the app.",
      );
    }

    return request("/auth/auth/login", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...headers,
      },
      body: JSON.stringify({ email, password, type: userType }),
    });
  },

  /** Refresh access token */
  refresh: async (refreshToken) =>
    request("/auth/token/refresh", {
      method: "POST",
      headers: await tenantHeaders(),
      body: JSON.stringify({ refresh_token: refreshToken }),
    }),

  /** Logout / revoke token */
  logout: async (refreshToken) =>
    request("/auth/auth/logout", {
      method: "POST",
      headers: await authHeaders(),
      body: JSON.stringify({ refresh_token: refreshToken }),
    }),

  /** Setup / change password */
  setupPassword: async (keycloakId, password, confirmPassword) =>
    request("/auth/auth/setup-password", {
      method: "POST",
      headers: await tenantHeaders(),
      body: JSON.stringify({
        keycloak_id: keycloakId,
        password,
        confirm_password: confirmPassword,
      }),
    }),

  /** Verify OTP */
  verifyOtp: async (keycloakId, otpCode) =>
    request("/auth/auth/verify-otp", {
      method: "POST",
      headers: await tenantHeaders(),
      body: JSON.stringify({ keycloak_id: keycloakId, otp_code: otpCode }),
    }),
};

// -------------------------------------------------------------------
// Agent API
// -------------------------------------------------------------------

export const agentApi = {
  /** Health check */
  health: () =>
    fetch(`${AGENT_BANKING_BASE}/agent/health`).then((r) => r.json()),

  /** Get the current agent's profile */
  getProfile: async (keycloakId) =>
    request(`/agent/agent/${keycloakId}`, {
      headers: await authHeaders(),
    }),

  /** Update agent profile */
  updateProfile: async (keycloakId, data) =>
    request(`/agent/agent/${keycloakId}`, {
      method: "PATCH",
      headers: await authHeaders(),
      body: JSON.stringify(data),
    }),

  /** Get all agents for the tenant */
  getTenantAgents: async () =>
    request("/agent/agent/tenant", {
      headers: await authHeaders(),
    }),

  /** Get only the agents invited by the current user */
  getInvitedAgents: async () =>
    request("/agent/agent/invited", {
      headers: await authHeaders(),
    }),

  /** Get agent by keycloak_id */
  getAgentByKeycloakId: async (keycloakId) =>
    request(`/agent/agent/${keycloakId}`, {
      headers: await authHeaders(),
    }),

  /** Alias for getAgentByKeycloakId */
  getAgent: async (keycloakId) =>
    request(`/agent/agent/${keycloakId}`, {
      headers: await authHeaders(),
    }),

  /** Get sub-agents (agents invited by this agent) */
  getSubAgents: async (agentId) =>
    request(`/agent/agent/${agentId}/sub-agents`, {
      headers: await authHeaders(),
    }),

  /** Get businesses for the current agent */
  getAgentBusinesses: async (keycloakId) =>
    request(`/agent/agent/businesses/agent/${keycloakId}`, {
      headers: await authHeaders(),
    }),
};

// -------------------------------------------------------------------
// User API
// -------------------------------------------------------------------

export const userApi = {
  /** Get current user profile */
  getProfile: async (keycloakId) =>
    request(`/user/user/${keycloakId}`, {
      headers: await authHeaders(),
    }),

  /** Get user by keycloak_id (query parameter) */
  getUserByKeycloakId: async (keycloakId) =>
    request(`/user/user?keycloak_id=${keycloakId}`, {
      headers: await authHeaders(),
    }),
};

// -------------------------------------------------------------------
// Tenant Management API
// -------------------------------------------------------------------

export const tenantApi = {
  /** Get tenant configuration by tenant_id */
  getTenant: async (tenantId) =>
    request(`/tenant-management/tenant/${tenantId}`, {
      headers: await tenantHeaders(),
    }),
};

// -------------------------------------------------------------------
// Dispute API (Core Banking Service)
// -------------------------------------------------------------------

export const disputeApi = {
  /** Get all disputes for current user */
  getDisputes: async () =>
    request("/dispute/api/v1/disputes", {
      headers: await authHeaders(),
    }),

  /** Get all disputes for tenant (admin only) */
  getTenantDisputes: async () =>
    request("/dispute/api/v1/disputes/tenant", {
      headers: await authHeaders(),
    }),

  /** Get a specific dispute */
  getDispute: async (disputeId) =>
    request(`/dispute/api/v1/disputes/${disputeId}`, {
      headers: await authHeaders(),
    }),

  /** Create a new dispute */
  createDispute: async (data) =>
    request("/dispute/api/v1/disputes", {
      method: "POST",
      headers: await authHeaders(),
      body: JSON.stringify(data),
    }),

  /** Resolve a dispute (admin only) */
  resolveDispute: async (disputeId, resolution) =>
    request(`/dispute/api/v1/administration/disputes/${disputeId}/resolve`, {
      method: "PUT",
      headers: await authHeaders(),
      body: JSON.stringify({ resolution }),
    }),

  /** Get messages for a dispute */
  getMessages: async (disputeId) =>
    request(`/dispute/api/v1/disputes/${disputeId}/messages`, {
      headers: await authHeaders(),
    }),

  /** Add a message to a dispute */
  addMessage: async (disputeId, data) =>
    request(`/dispute/api/v1/disputes/${disputeId}/messages`, {
      method: "POST",
      headers: await authHeaders(),
      body: JSON.stringify(data),
    }),
};

// -------------------------------------------------------------------
// Network Operations API
// -------------------------------------------------------------------

export const networkOperationsApi = {
  /**
   * Get channel success rate predictions
   * @param {object} filters - Optional { type, channel, medium }
   * @returns {Promise<{predictions: Array}>}
   */
  getPredictions: async (filters = {}) => {
    const params = new URLSearchParams();
    if (filters.type) params.append("type", filters.type);
    if (filters.channel) params.append("channel", filters.channel);
    if (filters.medium) params.append("medium", filters.medium);
    const queryString = params.toString();
    return request(
      `/network-operations/api/v1/predictions${queryString ? `?${queryString}` : ""}`,
      {
        headers: await authHeaders(),
      },
    );
  },

  /**
   * Register a transaction attempt (for tracking success rates)
   * @param {object} data - { type, channel, medium, status, amount, provider }
   */
  registerTransaction: async (data) =>
    request("/network-operations/api/v1/transactions", {
      method: "POST",
      headers: await authHeaders(),
      body: JSON.stringify(data),
    }),

  // -------------------------------------------------------------------
  // DEPRECATED: The following methods are no longer supported
  // Transaction history has been moved to a separate service
  // -------------------------------------------------------------------

  /** @deprecated Use transaction history service instead */
  listTransactions: async (agentId, filters = {}, page = 1, limit = 20) => {
    console.warn(
      "networkOperationsApi.listTransactions is deprecated - use transaction history service",
    );
    return { transactions: [], data: [], total: 0, total_pages: 0 };
  },

  /** @deprecated Use transaction history service instead */
  getTransaction: async (id) => {
    console.warn(
      "networkOperationsApi.getTransaction is deprecated - use transaction history service",
    );
    return null;
  },

  /** @deprecated Cash position tracking moved to float management service */
  getAgentCashPosition: async (agentId) => {
    console.warn(
      "networkOperationsApi.getAgentCashPosition is deprecated - use float management service",
    );
    return null;
  },

  /** @deprecated Use appropriate transaction service instead */
  createCashIn: async (data) => {
    console.warn(
      "networkOperationsApi.createCashIn is deprecated - use transaction service",
    );
    throw new Error("Method no longer supported");
  },

  /** @deprecated Use appropriate transaction service instead */
  createCashOut: async (data) => {
    console.warn(
      "networkOperationsApi.createCashOut is deprecated - use transaction service",
    );
    throw new Error("Method no longer supported");
  },

  /** @deprecated Use appropriate transaction service instead */
  updateTransactionStatus: async (transactionId, status) => {
    console.warn(
      "networkOperationsApi.updateTransactionStatus is deprecated - use transaction service",
    );
    throw new Error("Method no longer supported");
  },

  /** Get billers/organizations for a given category */
  getBillers: async (category) => {
    const path = category
      ? `/network-operations/billers/${category}`
      : "/network-operations/billers";
    return request(path, {
      headers: await authHeaders(),
    });
  },

  /** Create a bill payment or donation transaction */
  createTransaction: async (data) =>
    request("/network-operations/transactions", {
      method: "POST",
      headers: await authHeaders(),
      body: JSON.stringify(data),
    }),
};

// -------------------------------------------------------------------
// Account API (Core Banking Service)
// -------------------------------------------------------------------

export const accountApi = {
  /** Set up PIN for an account */
  setupPin: async (accountNumber, pin) => {
    return request(`/account/account/setup-pin`, {
      method: "POST",
      headers: await authHeaders(),
      body: JSON.stringify({ account_number: accountNumber, pin }),
    });
  },

  /** Get accounts by keycloak_id */
  getAccounts: async (keycloakId) =>
    request(`/account/account/keycloak/${keycloakId}`, {
      headers: await authHeaders(),
    }),

  /** Get account by keycloak_id */
  getAccountByKeycloakId: async (keycloakId) =>
    request(`/account/account/keycloak/${keycloakId}`, {
      headers: await authHeaders(),
    }),

  /** Get account details by account number (legacy ledger endpoint) */
  getAccountByNumber: async (accountNumber) =>
    request(`/ledger/txn/account-number/${accountNumber}`, {
      headers: await authHeaders(),
    }),

  /** Get account details by account number (from account service) */
  getAccountByAccountNumber: async (accountNumber) =>
    request(`/account/account/account-number/${accountNumber}`, {
      headers: await authHeaders(),
    }),

  /** Get account balance */
  getAccountBalance: async (accountNumber) =>
    request(`/account/account/${accountNumber}/balance`, {
      headers: await authHeaders(),
    }),

  /** Get all accounts (for chart of accounts view) */
  getAllAccounts: async () =>
    request(`/account/account/all`, {
      headers: await authHeaders(),
    }),

  /** Get bank directory */
  getBanks: async () =>
    request(`/account/bank`, {
      headers: await authHeaders(),
    }),

  /** Create a new account (e.g. for a business/store) */
  createAccount: async (data) =>
    request(`/account/account`, {
      method: "POST",
      headers: await authHeaders(),
      body: JSON.stringify(data),
    }),

  /** Create a cash in (deposit) transaction */
  createCashIn: async (data) => {
    const options = {
      method: "POST",
      headers: await authHeaders(),
      body: JSON.stringify(data),
    };

    try {
      return await request(`/agent/transactions/cash-in`, options);
    } catch (error) {
      const message = String(error?.message || "").toLowerCase();
      if (!(message.includes("not found") || message.includes("404"))) {
        throw error;
      }
      return request(`/agent/agent/transactions/cash-in`, options);
    }
  },

  /** Create a cash out (withdrawal) transaction */
  createCashOut: async (data) => {
    const options = {
      method: "POST",
      headers: await authHeaders(),
      body: JSON.stringify(data),
    };

    try {
      return await request(`/agent/transactions/cash-out`, options);
    } catch (error) {
      const message = String(error?.message || "").toLowerCase();
      if (!(message.includes("not found") || message.includes("404"))) {
        throw error;
      }
      return request(`/agent/agent/transactions/cash-out`, options);
    }
  },

  /** Get cash book transactions */
  getCashBook: async (agentId, transactionType = null, limit = 100) => {
    const params = new URLSearchParams();
    if (agentId) params.append("agent_id", agentId);
    if (transactionType) params.append("transaction_type", transactionType);
    params.append("limit", limit);
    const query = params.toString() ? `?${params.toString()}` : "";
    const options = {
      headers: await authHeaders(),
    };

    try {
      return await request(`/agent/transactions/cash-book${query}`, options);
    } catch (error) {
      const message = String(error?.message || "").toLowerCase();
      if (!(message.includes("not found") || message.includes("404"))) {
        throw error;
      }
      return request(`/agent/agent/transactions/cash-book${query}`, options);
    }
  },
};

// -------------------------------------------------------------------
// Ledger API
// -------------------------------------------------------------------

export const ledgerApi = {
  /** Get transactions for an account number */
  getTransactionsByAccountNumber: async (accountNumber, limit = 50, page = 1) =>
    request(
      `/ledger/txn/account-number/${accountNumber}?limit=${limit}&page=${page}`,
      {
        headers: await authHeaders(),
      },
    ),

  /** Get a specific transaction */
  getTransaction: async (transactionId) =>
    request(`/ledger/txn/${transactionId}`, {
      headers: await authHeaders(),
    }),
};

// -------------------------------------------------------------------
// Card API
// -------------------------------------------------------------------

export const cardApi = {
  lookupCardByNumber: async (cardNumber) =>
    request(
      `/card/api/v1/cards/lookup?card_number=${encodeURIComponent(cardNumber)}`,
      {
        headers: await authHeaders(),
      },
    ),
};

// -------------------------------------------------------------------
// Inventory API
// -------------------------------------------------------------------

export const inventoryApi = {
  // ─── Store Management ─────────────────────────────────────────────

  /** Create a new store (agent only) */
  createStore: async (data) =>
    request("/inventory/stores", {
      method: "POST",
      headers: await authHeaders(),
      body: JSON.stringify(data),
    }),

  /** Get all stores owned by the agent */
  getStores: async (ownerKeycloakId = null) => {
    const params = ownerKeycloakId
      ? `?owner_keycloak_id=${ownerKeycloakId}`
      : "";
    return request(`/inventory/stores${params}`, {
      headers: await authHeaders(),
    });
  },

  /** Get a single store by ID */
  getStore: async (storeId) =>
    request(`/inventory/stores/${storeId}`, {
      headers: await authHeaders(),
    }),

  /** Update a store */
  updateStore: async (storeId, data) =>
    request(`/inventory/stores/${storeId}`, {
      method: "PUT",
      headers: await authHeaders(),
      body: JSON.stringify(data),
    }),

  /** Delete a store */
  deleteStore: async (storeId) =>
    request(`/inventory/stores/${storeId}`, {
      method: "DELETE",
      headers: await authHeaders(),
    }),

  // ─── Inventory Management ─────────────────────────────────────────

  /** Get all inventory items for a store */
  getInventoryItems: async (storeId, filters = {}) => {
    const params = new URLSearchParams();
    if (filters.search) params.append("search", filters.search);
    if (filters.category && filters.category !== "all")
      params.append("category", filters.category);
    if (filters.status && filters.status !== "all")
      params.append("status", filters.status);
    const query = params.toString() ? `?${params.toString()}` : "";
    return request(`/inventory/stores/${storeId}/items${query}`, {
      headers: await authHeaders(),
    });
  },

  /** Get a specific inventory item */
  getInventoryItem: async (itemId) =>
    request(`/inventory/inventory/items/${itemId}`, {
      headers: await authHeaders(),
    }),

  /** Create a new inventory item */
  createInventoryItem: async (storeId, data) =>
    request(`/inventory/stores/${storeId}/items`, {
      method: "POST",
      headers: await authHeaders(),
      body: JSON.stringify(data),
    }),

  /** Update an inventory item */
  updateInventoryItem: async (itemId, data) =>
    request(`/inventory/inventory/items/${itemId}`, {
      method: "PUT",
      headers: await authHeaders(),
      body: JSON.stringify(data),
    }),

  /** Delete an inventory item */
  deleteInventoryItem: async (itemId) =>
    request(`/inventory/inventory/items/${itemId}`, {
      method: "DELETE",
      headers: await authHeaders(),
    }),

  /** Get stock alerts */
  getStockAlerts: async () =>
    request("/inventory/inventory/alerts", {
      headers: await authHeaders(),
    }),

  /** Create a sale */
  createSale: async (data) =>
    request("/inventory/inventory/sales", {
      method: "POST",
      headers: await authHeaders(),
      body: JSON.stringify(data),
    }),

  /** Get sales history */
  getSalesHistory: async (limit = 50) => {
    const query = limit ? `?limit=${limit}` : "";
    return request(`/inventory/inventory/sales${query}`, {
      headers: await authHeaders(),
    });
  },

  /** Get inventory metrics */
  getInventoryMetrics: async () =>
    request("/inventory/inventory/metrics", {
      headers: await authHeaders(),
    }),

  // ─── Image Management ─────────────────────────────────────────────

  /** Upload image for an item */
  uploadItemImage: async (itemId, file) => {
    const formData = new FormData();
    formData.append("file", file);
    const token = await SecureStore.getItemAsync("authToken");
    const tenantHeaders = await getTenantHeadersFromConfig();
    return request(`/inventory/inventory/items/${itemId}/images`, {
      method: "POST",
      headers: {
        ...tenantHeaders,
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: formData,
    });
  },

  /** Add image URL for an item */
  addItemImageUrl: async (itemId, url) =>
    request(`/inventory/inventory/items/${itemId}/images/url`, {
      method: "POST",
      headers: await authHeaders(),
      body: JSON.stringify({ url }),
    }),

  /** Get images for an item */
  getItemImages: async (itemId) =>
    request(`/inventory/inventory/items/${itemId}/images`, {
      headers: await authHeaders(),
    }),

  /** Delete an item image */
  deleteItemImage: async (itemId, imageId) =>
    request(`/inventory/inventory/items/${itemId}/images/${imageId}`, {
      method: "DELETE",
      headers: await authHeaders(),
    }),
};

// -------------------------------------------------------------------
// Document API
// -------------------------------------------------------------------

export const documentApi = {
  /**
   * Upload a file to the document service.
   * Returns { url, id, filename, content_type }
   */
  uploadFile: async (file, documentType = "product_image") => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("document_type", documentType);
    const token = await SecureStore.getItemAsync("authToken");
    const tenantHeaders = await getTenantHeadersFromConfig();

    console.log("Upload config:", {
      url: "/document/upload",
      baseUrl: getBaseUrl("/document/upload"),
      fileName: file.name,
      fileType: file.type,
      hasToken: !!token,
      tenantHeaders,
    });

    // Do NOT set Content-Type — the system will handle multipart/form-data boundary
    return request("/document/upload", {
      method: "POST",
      headers: {
        ...tenantHeaders,
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: formData,
    });
  },
};

// -------------------------------------------------------------------
// POS Terminal Management API
// -------------------------------------------------------------------

export const posTerminalApi = {
  /** Get all terminals */
  getTerminals: async (params = {}) => {
    const query = new URLSearchParams();
    Object.entries(params).forEach(
      ([k, v]) => v != null && query.append(k, String(v)),
    );
    const qs = query.toString() ? `?${query.toString()}` : "";
    return request(`/pos-terminals/terminals${qs}`, {
      headers: await authHeaders(),
    });
  },

  /** Get a specific terminal by ID */
  getTerminal: async (id) =>
    request(`/pos-terminals/terminals/${id}`, {
      headers: await authHeaders(),
    }),

  /** Create a new terminal */
  createTerminal: async (data) =>
    request("/pos-terminals/terminals", {
      method: "POST",
      headers: await authHeaders(),
      body: JSON.stringify(data),
    }),

  /** Update a terminal */
  updateTerminal: async (id, data) =>
    request(`/pos-terminals/terminals/${id}`, {
      method: "PUT",
      headers: await authHeaders(),
      body: JSON.stringify(data),
    }),

  /** Delete a terminal */
  deleteTerminal: async (id) =>
    request(`/pos-terminals/terminals/${id}`, {
      method: "DELETE",
      headers: await authHeaders(),
    }),

  /** Get terminals filtered by status */
  getTerminalsByStatus: async (status) =>
    request(`/pos-terminals/terminals/status/${status}`, {
      headers: await authHeaders(),
    }),

  /** Search terminals */
  searchTerminals: async (q) =>
    request(`/pos-terminals/terminals/search?q=${encodeURIComponent(q)}`, {
      headers: await authHeaders(),
    }),

  /** Get service records for a terminal */
  getServiceRecords: async (id) =>
    request(`/pos-terminals/terminals/${id}/servicerecords`, {
      headers: await authHeaders(),
    }),

  /** Create a service record */
  createServiceRecord: async (id, data) =>
    request(`/pos-terminals/terminals/${id}/servicerecords`, {
      method: "POST",
      headers: await authHeaders(),
      body: JSON.stringify(data),
    }),
};

// -------------------------------------------------------------------
// POS Management API
// -------------------------------------------------------------------

export const posManagementApi = {
  /** Get all devices */
  getDevices: async (params = {}) => {
    const query = new URLSearchParams();
    Object.entries(params).forEach(
      ([k, v]) => v != null && query.append(k, String(v)),
    );
    const qs = query.toString() ? `?${query.toString()}` : "";
    return request(`/pos-management/api/v1/devices${qs}`, {
      headers: await authHeaders(),
    });
  },

  /** Get a specific device */
  getDevice: async (id) =>
    request(`/pos-management/api/v1/devices/${id}`, {
      headers: await authHeaders(),
    }),
};

// -------------------------------------------------------------------
// MDM Device API (POS terminal / device-side)
// -------------------------------------------------------------------

export const mdmDeviceApi = {
  /**
   * Send terminal heartbeat
   * PUT /api/v1/mdm/heartbeat/:terminal_id
   */
  sendHeartbeat: async (terminalId, payload) =>
    request(`/mdm/api/v1/mdm/heartbeat/${terminalId}`, {
      method: "PUT",
      headers: await authHeaders(),
      body: JSON.stringify(payload),
    }),

  /**
   * Fetch pending commands for terminal
   * GET /api/v1/mdm/commands/:terminal_id/pending
   */
  getPendingCommands: async (terminalId) =>
    request(`/mdm/api/v1/mdm/commands/${terminalId}/pending`, {
      headers: await authHeaders(),
    }),

  /**
   * Update command execution status
   * PUT /api/v1/mdm/commands/:command_id/status
   */
  updateCommandStatus: async (commandId, payload) =>
    request(`/mdm/api/v1/mdm/commands/${commandId}/status`, {
      method: "PUT",
      headers: await authHeaders(),
      body: JSON.stringify(payload),
    }),

  /**
   * Complete provisioning
   * PUT /api/v1/mdm/provision/:terminal_id/complete
   */
  completeProvisioning: async (terminalId, payload) =>
    request(`/mdm/api/v1/mdm/provision/${terminalId}/complete`, {
      method: "PUT",
      headers: await authHeaders(),
      body: JSON.stringify(payload),
    }),

  /**
   * Send tamper alert
   * POST /api/v1/mdm/tamper/:terminal_id/alert
   */
  sendTamperAlert: async (terminalId, payload) =>
    request(`/mdm/api/v1/mdm/tamper/${terminalId}/alert`, {
      method: "POST",
      headers: await authHeaders(),
      body: JSON.stringify(payload),
    }),

  /**
   * Get latest APK for a given model
   * GET /api/v1/mdm/apk/latest/:model_id
   */
  getLatestApkByModel: async (modelId) =>
    request(`/mdm/api/v1/mdm/apk/latest/${modelId}`, {
      headers: await authHeaders(),
    }),

  /** Update device status */
  updateDeviceStatus: async (id, status) =>
    request(`/pos-management/api/v1/devices/${id}/status`, {
      method: "PUT",
      headers: await authHeaders(),
      body: JSON.stringify({ status }),
    }),

  /** Get transactions for a device */
  getDeviceTransactions: async (id, params = {}) => {
    const query = new URLSearchParams(params);
    const qs = query.toString() ? `?${query.toString()}` : "";
    return request(`/pos-management/api/v1/devices/${id}/transactions${qs}`, {
      headers: await authHeaders(),
    });
  },

  /** Get device analytics */
  getDeviceAnalytics: async () =>
    request("/pos-management/api/v1/analytics/devices", {
      headers: await authHeaders(),
    }),

  /**
   * Look up a device by serial number (self-identification at startup)
   * GET /mdm/api/v1/mdm/devices/by-serial/:serial_number
   */
  getDeviceBySerial: async (serialNumber) =>
    request(`/mdm/api/v1/mdm/devices/by-serial/${encodeURIComponent(serialNumber)}`, {
      headers: await authHeaders(),
    }),
};

// -------------------------------------------------------------------
// POS Request API (Agent ordering workflow)
// -------------------------------------------------------------------

export const posRequestApi = {
  /** Create a new POS request */
  createRequest: async (data) =>
    request("/agent/agent/pos-requests", {
      method: "POST",
      headers: await authHeaders(),
      body: JSON.stringify(data),
    }),

  /** Get all my POS requests */
  getMyRequests: async (status = null) => {
    const params = status ? `?status=${status}` : "";
    return request(`/agent/agent/pos-requests/my-requests${params}`, {
      headers: await authHeaders(),
    });
  },

  /** Get a specific POS request */
  getRequest: async (requestId) =>
    request(`/agent/pos-requests/${requestId}`, {
      headers: await authHeaders(),
    }),

  /** Update a pending POS request */
  updateRequest: async (requestId, data) =>
    request(`/agent/agent/pos-requests/${requestId}`, {
      method: "PATCH",
      headers: await authHeaders(),
      body: JSON.stringify(data),
    }),

  /** Cancel a pending POS request */
  cancelRequest: async (requestId) =>
    request(`/agent/agent/pos-requests/${requestId}`, {
      method: "DELETE",
      headers: await authHeaders(),
    }),
};

// -------------------------------------------------------------------
// Business API
// -------------------------------------------------------------------

export const businessApi = {
  /** Get all businesses for the agent */
  getAgentBusinesses: async (agentId) =>
    request(`/agent/agent/businesses/agent/${agentId}`, {
      headers: await authHeaders(),
    }),

  /** Get a specific business by ID */
  getBusiness: async (id) =>
    request(`/agent/agent/businesses/${id}`, {
      headers: await authHeaders(),
    }),

  /** Create/register a new business */
  createBusiness: async (data) =>
    request("/agent/agent/businesses/create", {
      method: "POST",
      headers: await authHeaders(),
      body: JSON.stringify(data),
    }),

  /** Update an existing business */
  updateBusiness: async (businessId, data) =>
    request(`/agent/agent/businesses/${businessId}`, {
      method: "PATCH",
      headers: await authHeaders(),
      body: JSON.stringify(data),
    }),

  /** Unlink/delete a business */
  unlinkBusiness: async (businessId) =>
    request(`/agent/agent/businesses/unlink/${businessId}`, {
      method: "DELETE",
      headers: await authHeaders(),
    }),

  /** Link store to business */
  linkStoreToBusiness: async (storeId, businessId) =>
    request(`/inventory/stores/${storeId}/link-business`, {
      method: "PUT",
      headers: await authHeaders(),
      body: JSON.stringify({ business_id: businessId }),
    }),

  /** Link POS terminal to business */
  linkPOSTerminalToBusiness: async (terminalId, businessId) =>
    request(`/pos-terminals/terminals/${terminalId}/link-business`, {
      method: "PUT",
      headers: await authHeaders(),
      body: JSON.stringify({ business_id: businessId }),
    }),

  /** Get stores for a business */
  getBusinessStores: async (businessId) =>
    request(`/inventory/stores/business/${businessId}`, {
      headers: await authHeaders(),
    }),

  /** Get POS terminals for a business */
  getBusinessPOSTerminals: async (businessId) =>
    request(`/pos-terminals/terminals/business/${businessId}`, {
      headers: await authHeaders(),
    }),
};

// -------------------------------------------------------------------
// Commission API
// -------------------------------------------------------------------

export const commissionApi = {
  /** Get agent's commission wallet balance */
  getBalance: async (agentId) =>
    request(`/commission/api/v1/agents/${agentId}/balance`, {
      headers: await authHeaders(),
    }),

  /** List commissions for an agent */
  listCommissions: async (agentId, params = {}) => {
    const qp = new URLSearchParams({
      agent_id: agentId,
      page: params.page ?? 1,
      limit: params.limit ?? 50,
      ...(params.status && { status: params.status }),
      ...(params.start_date && { start_date: params.start_date }),
      ...(params.end_date && { end_date: params.end_date }),
    }).toString();
    return request(`/commission/api/v1/commissions?${qp}`, {
      headers: await authHeaders(),
    });
  },

  /** List settlement history */
  listSettlements: async (agentId, params = {}) => {
    const qp = new URLSearchParams({
      agent_id: agentId,
      page: params.page ?? 1,
      limit: params.limit ?? 20,
      ...(params.status && { status: params.status }),
    }).toString();
    return request(`/commission/api/v1/settlements?${qp}`, {
      headers: await authHeaders(),
    });
  },

  /** Request a commission withdrawal.
   *  Pass auto_process: true to have the service immediately pay out funds.
   */
  requestSettlement: async (data) =>
    request("/commission/api/v1/settlements", {
      method: "POST",
      headers: await authHeaders(),
      body: JSON.stringify(data),
    }),

  /** Get platform-wide settlement policy (withdrawal allowed, min amount, etc.) */
  getPolicy: async () =>
    request("/commission/api/v1/policy", {
      headers: await authHeaders(),
    }),

  /** Trigger EOD settlement batch for all agents (admin use) */
  runEod: async () =>
    request("/commission/api/v1/eod/run", {
      method: "POST",
      headers: await authHeaders(),
    }),
};

// -------------------------------------------------------------------
// Messaging API
// -------------------------------------------------------------------

export const messagingApi = {
  /** Get all conversations for the current agent */
  getConversations: async (storeEntityId = null) => {
    const tenantId = await getTenantId();
    const keycloakId =
      storeEntityId || (await SecureStore.getItemAsync("keycloakId"));

    if (!keycloakId) {
      throw new Error("Not authenticated");
    }

    return request(
      `/messaging/conversations?tenant_id=${tenantId}&keycloak_id=${keycloakId}&user_type=agent`,
      {
        headers: await authHeaders(),
      },
    );
  },

  /** Get messages for a conversation */
  getMessages: async (conversationId, options = {}) => {
    const tenantId = await getTenantId();

    // Handle both object and direct parameters
    const limit = typeof options === "object" ? options.limit || 50 : options;
    const offset = typeof options === "object" ? options.offset || 0 : 0;
    const page = typeof options === "object" ? options.page : undefined;

    return request(
      `/messaging/conversations/${conversationId}/messages?tenant_id=${tenantId}&limit=${limit}&offset=${offset}`,
      {
        headers: await authHeaders(),
      },
    );
  },

  /** Send a message */
  sendMessage: async (messageData) => {
    const tenantId = await getTenantId();
    const keycloakId = await SecureStore.getItemAsync("keycloakId");
    const displayName =
      (await SecureStore.getItemAsync("displayName")) || "Agent";

    if (!keycloakId) {
      throw new Error("Not authenticated");
    }

    const queryParams = new URLSearchParams({
      tenant_id: tenantId,
      sender_keycloak_id: keycloakId,
      sender_name: displayName,
      sender_type: "agent",
    });

    return request(`/messaging/messages?${queryParams}`, {
      method: "POST",
      headers: await authHeaders(),
      body: JSON.stringify(messageData),
    });
  },
};

// -------------------------------------------------------------------
// Loan API
// -------------------------------------------------------------------

export const loanApi = {
  /** Get all loan applications for an agent */
  getLoanApplications: async (keycloakId) =>
    request(`/loan/api/v1/loans/applications?keycloak_id=${keycloakId}`, {
      headers: await authHeaders(),
    }),

  /** Get a specific loan application */
  getLoanApplication: async (applicationId) =>
    request(`/loan/api/v1/loans/applications/${applicationId}`, {
      headers: await authHeaders(),
    }),

  /** Create a new loan application */
  createLoanApplication: async (data) =>
    request("/loan/api/v1/loans/applications", {
      method: "POST",
      headers: await authHeaders(),
      body: JSON.stringify(data),
    }),

  /** Get all active loans for an agent */
  getActiveLoans: async (keycloakId) =>
    request(`/loan/api/v1/loans?keycloak_id=${keycloakId}&status=active`, {
      headers: await authHeaders(),
    }),

  /** Make a loan payment */
  makeLoanPayment: async (loanId, data) =>
    request(`/loan/api/v1/loans/${loanId}/payments`, {
      method: "POST",
      headers: await authHeaders(),
      body: JSON.stringify(data),
    }),
};

export const qrApi = {
  /** Generate QR code for payment */
  generateQRCode: async (recipient, amount, currency = "NGN", note = "") => {
    const headers = await authHeaders();

    // Get mint account id from tenant config if available
    try {
      const tenantConfig = await SecureStore.getItemAsync("tenant_config");
      if (tenantConfig) {
        const tenant = JSON.parse(tenantConfig);
        const featureFlags = Array.isArray(tenant.feature_flags)
          ? tenant.feature_flags
          : [];
        const accountsFeature = featureFlags.find(
          (flag) =>
            flag.name === "accounts" && flag.config && flag.config.account,
        );
        if (accountsFeature?.config?.account?.id) {
          headers["x-mint-account-id"] = String(
            accountsFeature.config.account.id,
          );
        }
      }
    } catch (err) {
      console.warn("Could not parse tenant config for mint account id", err);
    }

    return request("/payment-processing/qr/generate", {
      method: "POST",
      headers,
      body: JSON.stringify({
        recipient: String(recipient),
        amount: String(amount),
        currency,
        note,
      }),
    });
  },
};

export const storeMapApi = {
  /** Register or update a store location on the map */
  registerStore: async (data) =>
    request("/store-map/stores", {
      method: "POST",
      headers: await authHeaders(),
      body: JSON.stringify(data),
    }),

  /** Get a specific store by entity ID */
  getStore: async (entityId) =>
    request(`/store-map/stores/${entityId}`, {
      headers: await authHeaders(),
    }),

  /** Find nearby stores within a given radius */
  findNearbyStores: async (latitude, longitude, radiusKm = 5) =>
    request("/store-map/stores/nearby", {
      method: "POST",
      headers: await authHeaders(),
      body: JSON.stringify({
        latitude,
        longitude,
        radius_km: radiusKm,
      }),
    }),

  /** Get all stores (for map display) */
  getAllStores: async () =>
    request("/store-map/stores", {
      headers: await authHeaders(),
    }),

  /** Search stores by name or location */
  searchStores: async (query) =>
    request(`/store-map/stores/search?q=${encodeURIComponent(query)}`, {
      headers: await authHeaders(),
    }),
};

// -------------------------------------------------------------------
// Order Management API (Store Orders/Sales)
// -------------------------------------------------------------------

export const orderApi = {
  /** Create a new order/sale transaction */
  createOrder: async (data) =>
    request("/inventory/orders", {
      method: "POST",
      headers: await authHeaders(),
      body: JSON.stringify(data),
    }),

  /** Get all orders for a store */
  getStoreOrders: async (storeId, filters = {}) => {
    const params = new URLSearchParams();
    if (filters.status) params.append("status", filters.status);
    if (filters.start_date) params.append("start_date", filters.start_date);
    if (filters.end_date) params.append("end_date", filters.end_date);
    if (filters.payment_method)
      params.append("payment_method", filters.payment_method);
    const query = params.toString() ? `?${params.toString()}` : "";
    return request(`/inventory/stores/${storeId}/orders${query}`, {
      headers: await authHeaders(),
    });
  },

  /** Get a specific order by ID */
  getOrder: async (orderId) =>
    request(`/inventory/orders/${orderId}`, {
      headers: await authHeaders(),
    }),

  /** Get orders for an agent (across all stores) */
  getAgentOrders: async (keycloakId, filters = {}) => {
    const params = new URLSearchParams();
    params.append("agent_keycloak_id", keycloakId);
    if (filters.status) params.append("status", filters.status);
    if (filters.start_date) params.append("start_date", filters.start_date);
    if (filters.end_date) params.append("end_date", filters.end_date);
    const query = params.toString() ? `?${params.toString()}` : "";
    return request(`/inventory/orders${query}`, {
      headers: await authHeaders(),
    });
  },

  /** Update order status */
  updateOrderStatus: async (orderId, status) =>
    request(`/inventory/orders/${orderId}/status`, {
      method: "PUT",
      headers: await authHeaders(),
      body: JSON.stringify({ status }),
    }),

  /** Get order statistics for a store */
  getStoreOrderStats: async (storeId, startDate = null, endDate = null) => {
    const params = new URLSearchParams();
    if (startDate) params.append("start_date", startDate);
    if (endDate) params.append("end_date", endDate);
    const query = params.toString() ? `?${params.toString()}` : "";
    return request(`/inventory/stores/${storeId}/orders/stats${query}`, {
      headers: await authHeaders(),
    });
  },
};

// -------------------------------------------------------------------
// Loyalty API (Agent-side)
// -------------------------------------------------------------------

export const loyaltyApi = {
  createAccount: async (userId) =>
    request("/loyalty/loyalty/accounts", {
      method: "POST",
      headers: await authHeaders(),
      body: JSON.stringify({ user_id: userId }),
    }),

  getAccount: async (userId) =>
    request(`/loyalty/loyalty/accounts/${userId}`, {
      headers: await authHeaders(),
    }),

  earnPoints: async (userId, data) =>
    request(`/loyalty/loyalty/accounts/${userId}/earn`, {
      method: "POST",
      headers: await authHeaders(),
      body: JSON.stringify(data),
    }),

  spendPoints: async (userId, data) =>
    request(`/loyalty/loyalty/accounts/${userId}/spend`, {
      method: "POST",
      headers: await authHeaders(),
      body: JSON.stringify(data),
    }),

  getActivities: async (userId, params = {}) => {
    const query = new URLSearchParams();
    if (params.skip !== undefined) query.append("skip", String(params.skip));
    if (params.limit !== undefined) query.append("limit", String(params.limit));
    if (params.activity_type)
      query.append("activity_type", params.activity_type);
    const queryString = query.toString() ? `?${query.toString()}` : "";
    return request(
      `/loyalty/loyalty/accounts/${userId}/activities${queryString}`,
      {
        headers: await authHeaders(),
      },
    );
  },
};

// -------------------------------------------------------------------
// Remittance API
// -------------------------------------------------------------------

export const remittanceApi = {
  initiateTransfer: async (payload) => {
    const headers = await authHeaders();
    const tenantName =
      headers["x-tenant-name"] || headers["x-tenant-id"] || DEFAULT_TENANT_ID;

    const response = await fetch(
      `${CORE_BANKING_BASE}/payment-hub/api/v1/transfers/initiate`,
      {
        method: "POST",
        headers: {
          ...headers,
          "x-switch-name": "mojaloop",
          "x-ams-name": "core_banking",
          "x-tenant-name": tenantName,
        },
        body: JSON.stringify({
          ...payload,
          destination: payload?.destination || tenantName,
        }),
      },
    );

    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data?.message || data?.detail || "Failed to initiate remittance");
    }
    return data;
  },

  verifyTransaction: async (payload) => {
    const response = await fetch(
      `${REMITTANCE_BANKING_BASE}/remittance/api/v1/transactions/verify`,
      {
        method: "POST",
        headers: await authHeaders(),
        body: JSON.stringify(payload),
      },
    );

    const data = await response.json().catch(() => ({}));
    if (!response.ok || !data?.success) {
      throw new Error(data?.message || "Verification failed");
    }
    return data;
  },

  markTransactionDisbursed: async (transactionId, payload) => {
    const response = await fetch(
      `${REMITTANCE_BANKING_BASE}/remittance/api/v1/transactions/${transactionId}/disburse`,
      {
        method: "POST",
        headers: await authHeaders(),
        body: JSON.stringify(payload),
      },
    );

    const data = await response.json().catch(() => ({}));
    if (!response.ok || !data?.success) {
      throw new Error(data?.message || "Failed to mark as disbursed");
    }
    return data;
  },
};

// -------------------------------------------------------------------
// SIM Orchestrator API (local daemon on the POS terminal — port 9200)
// Calls go directly to localhost, NOT through the APISIX gateway.
// -------------------------------------------------------------------

const ORCHESTRATOR_BASE_URL = "http://localhost:9200";

async function orchestratorFetch(path, options = {}) {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), 2000);
  try {
    const response = await fetch(`${ORCHESTRATOR_BASE_URL}${path}`, {
      ...options,
      signal: controller.signal,
    });
    return response.ok ? response.json() : null;
  } catch {
    return null;
  } finally {
    clearTimeout(id);
  }
}

// -------------------------------------------------------------------
// Reversal API
// -------------------------------------------------------------------

export const reversalApi = {
  /** Look up a transaction by reference (falls back to ledger) */
  lookupTransaction: async (reference) =>
    request(`/ledger/txn/reference/${encodeURIComponent(reference)}`, {
      headers: await authHeaders(),
    }),

  /** Initiate a transaction reversal */
  initiateReversal: async (data) =>
    request("/payment-processing/reversals", {
      method: "POST",
      headers: await authHeaders(),
      body: JSON.stringify(data),
    }),

  /** Get reversal status */
  getReversalStatus: async (reversalId) =>
    request(`/payment-processing/reversals/${reversalId}`, {
      headers: await authHeaders(),
    }),
};

// -------------------------------------------------------------------
// Settlement API
// -------------------------------------------------------------------

export const settlementApi = {
  /** Get outstanding settlement items for the agent */
  getOutstanding: async (agentId) =>
    request(`/commission/api/v1/settlements/outstanding?agent_id=${agentId}`, {
      headers: await authHeaders(),
    }),

  /** Submit an EOD report */
  submitEODReport: async (data) =>
    request("/agent/agent/eod-reports", {
      method: "POST",
      headers: await authHeaders(),
      body: JSON.stringify(data),
    }),

  /** Export settlement report for a date */
  exportReport: async (date) =>
    request(`/commission/api/v1/settlements/export?date=${date}`, {
      headers: await authHeaders(),
    }),
};

// -------------------------------------------------------------------
// SIM Orchestrator API (local daemon on the POS terminal — port 9200)
// Calls go directly to localhost, NOT through the APISIX gateway.
// -------------------------------------------------------------------

export const simOrchestratorApi = {
  /**
   * Returns current SIM status: active slot, signal readings, last failover.
   * Returns null when the daemon is unreachable (dev mode / emulator).
   */
  getStatus: () => orchestratorFetch("/sim/status"),

  /**
   * Legacy health check (uptime monitoring).
   */
  getHealth: () => orchestratorFetch("/health"),
};
