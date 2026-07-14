/**
 * Central API client for the 54agent agent dashboard.
 * All requests route through APISIX.
 *
 * Core Banking Services (https://54agent.upi.dev):
 *   /auth/*              → auth-service
 *   /user/*              → user-service
 *   /dispute/*           → dispute-service
 *   /tenant-management/* → tenant-management
 *   /admin/*             → admin-service
 *   /orchestrator/*      → orchestrator
 *
 * Agency Banking Services (https://54agent.upi.dev):
 *   /agent/*             → agent-service
 *
 * Loyalty Service (https://54agent.upi.dev):
 *   /loyalty/*           → loyalty-service
 */

const CORE_BANKING_BASE = "https://54agent.upi.dev";
const AGENT_BANKING_BASE =
  import.meta.env.VITE_API_URL || "https://54agent.upi.dev";

const DEFAULT_TENANT_ID = import.meta.env.VITE_TENANT_ID || "54agent";

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

  // Core Banking – document storage (MinIO via document-service)
  "/document": AGENT_BANKING_BASE,
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
 * Extract tenant headers from localStorage tenant config
 * Similar to admin dashboard's getTenantHeaders
 */
function getTenantHeadersFromConfig() {
  const configStr = localStorage.getItem("tenant_config");
  if (!configStr) {
    console.warn("No tenant config found in localStorage");
    return { "x-tenant-id": DEFAULT_TENANT_ID };
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
    const accountFeature = featureFlags.find(
      (flag) => flag.name === "accounts",
    );

    if (accountFeature?.config) {
      headers["x-mint-account-id"] = String(accountFeature.config.account.id);
    }

    if (authFeature?.config) {
      // x-keycloak-realm from auth.config.realm
      if (authFeature.config.realm) {
        headers["x-keycloak-realm"] = String(authFeature.config.realm);
      } else {
        console.warn("No realm found in auth feature config");
      }

      // x-keycloak-pub-key from auth.config.public_rsa_key
      if (authFeature.config.public_rsa_key) {
        headers["x-keycloak-pub-key"] = String(
          authFeature.config.public_rsa_key,
        );
      } else {
        console.warn("No public_rsa_key found in auth feature config");
      }
    } else {
      console.warn("No auth feature flag found in tenant config");
    }

    console.log("Tenant headers extracted:", headers);
    return headers;
  } catch (error) {
    console.error("Error parsing tenant config:", error);
    return { "x-tenant-id": DEFAULT_TENANT_ID };
  }
}

export function tenantHeaders() {
  return {
    "Content-Type": "application/json",
    ...getTenantHeadersFromConfig(),
  };
}

/**
 * Get the current tenant ID from localStorage
 */
export function getTenantId() {
  try {
    const configStr = localStorage.getItem("tenant_config");
    if (!configStr) {
      return DEFAULT_TENANT_ID;
    }
    const tenant = JSON.parse(configStr);
    return tenant.tenant_id || DEFAULT_TENANT_ID;
  } catch (error) {
    console.error("Error getting tenant ID:", error);
    return DEFAULT_TENANT_ID;
  }
}

export function authHeaders() {
  const token = localStorage.getItem("agent_dashboard_token");
  const tenantHeaders = getTenantHeadersFromConfig();

  // Add keycloak-id if not in tenant headers
  if (!tenantHeaders["x-keycloak-id"]) {
    // Try dedicated key first, then fall back to stored user object
    let keycloakId = localStorage.getItem("keycloakId");
    if (!keycloakId) {
      try {
        const storedUser = JSON.parse(
          localStorage.getItem("agent_dashboard_user") ||
            localStorage.getItem("user") ||
            "null",
        );
        keycloakId = storedUser?.keycloakId ?? storedUser?.keycloak_id ?? null;
      } catch {
        /* ignore */
      }
    }
    if (!keycloakId && token && token !== "authenticated" && token !== "demo-token") {
      // Extract keycloak user ID from JWT sub claim as last resort
      try {
        const payload = JSON.parse(
          atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")),
        );
        if (payload.sub) {
          keycloakId = payload.sub;
          localStorage.setItem("keycloakId", payload.sub);
        }
      } catch {
        /* non-JWT token, skip */
      }
    }
    if (keycloakId) {
      tenantHeaders["x-keycloak-id"] = keycloakId;
    } else {
      console.warn(
        "⚠️ Missing x-keycloak-id header - user may not be properly authenticated",
      );
    }
  }

  // Add ledger-id if not in tenant headers
  if (!tenantHeaders["x-ledger-id"]) {
    const ledgerId = localStorage.getItem("ledgerId") || "1";
    if (ledgerId) {
      tenantHeaders["x-ledger-id"] = ledgerId;
    }
  }

  return {
    "Content-Type": "application/json",
    ...tenantHeaders,
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

// -------------------------------------------------------------------
// Generic request wrapper
// -------------------------------------------------------------------

async function request(path, options = {}) {
  const baseUrl = getBaseUrl(path);
  const res = await fetch(`${baseUrl}${path}`, options);

  // Handle empty responses (e.g. 204 No Content)
  if (res.status === 204) return null;

  const json = await res.json().catch(() => null);

  if (!res.ok) {
    const message =
      json?.detail?.message ??
      (typeof json?.detail === "string" ? json.detail : null) ??
      json?.message ??
      `${res.status} ${res.statusText}`;
    throw new Error(message);
  }

  return json;
}

// -------------------------------------------------------------------
// Auth API
// -------------------------------------------------------------------

export const authApi = {
  /** Health check */
  health: () => fetch(`${AGENT_BANKING_BASE}/auth/health`).then((r) => r.json()),

  /** Login — returns access_token, refresh_token, user info */
  login: (email, password, userType = null) => {
    // Get headers from tenant config
    const headers = getTenantHeadersFromConfig();

    // Validate required headers
    const requiredHeaders = ["x-keycloak-realm", "x-keycloak-pub-key"];
    const missingHeaders = requiredHeaders.filter((h) => !headers[h]);

    if (missingHeaders.length > 0) {
      console.error("Missing required headers for login:", missingHeaders);
      console.log("Current headers:", headers);
      console.log("Tenant config:", localStorage.getItem("tenant_config"));
      throw new Error(
        "Tenant configuration not loaded. Please refresh the page.",
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
  refresh: (refreshToken) =>
    request("/auth/token/refresh", {
      method: "POST",
      headers: tenantHeaders(),
      body: JSON.stringify({ refresh_token: refreshToken }),
    }),

  /** Logout / revoke token */
  logout: (refreshToken) =>
    request("/auth/auth/logout", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ refresh_token: refreshToken }),
    }),

  /** Setup / change password */
  setupPassword: (keycloakId, password, confirmPassword) =>
    request("/auth/auth/setup-password", {
      method: "POST",
      headers: tenantHeaders(),
      body: JSON.stringify({
        keycloak_id: keycloakId,
        password,
        confirm_password: confirmPassword,
      }),
    }),

  /** Verify OTP */
  verifyOtp: (keycloakId, otpCode) =>
    request("/auth/auth/verify-otp", {
      method: "POST",
      headers: tenantHeaders(),
      body: JSON.stringify({ keycloak_id: keycloakId, otp_code: otpCode }),
    }),
};

// -------------------------------------------------------------------
// Agent API
// -------------------------------------------------------------------

export const agentApi = {
  /** Health check */
  health: () => fetch(`${AGENT_BANKING_BASE}/agent/health`).then((r) => r.json()),

  /** Get the current agent's profile */
  getProfile: (keycloakId) =>
    request(`/agent/agent/${keycloakId}`, {
      headers: authHeaders(),
    }),

  /** Update agent profile */
  updateProfile: (keycloakId, data) =>
    request(`/agent/agent/${keycloakId}`, {
      method: "PATCH",
      headers: authHeaders(),
      body: JSON.stringify(data),
    }),

  /** Get all agents for the tenant */
  getTenantAgents: () =>
    request("/agent/agent/tenant", {
      headers: authHeaders(),
    }),

  /** Get only the agents invited by the current user */
  getInvitedAgents: () =>
    request("/agent/agent/invited", {
      headers: authHeaders(),
    }),

  /** Get agent by keycloak_id - expects { message, agent } response */
  getAgentByKeycloakId: (keycloakId) =>
    request(`/agent/agent/${keycloakId}`, {
      headers: authHeaders(),
    }),

  /** Get businesses for the current agent */
  getAgentBusinesses: (keycloakId) =>
    request(`/agent/agent/businesses/agent/${keycloakId}`, {
      headers: authHeaders(),
    }),
};

// -------------------------------------------------------------------
// User API
// -------------------------------------------------------------------

export const userApi = {
  /** Health check */
  health: () => fetch(`${AGENT_BANKING_BASE}/user/health`).then((r) => r.json()),

  /** Get current user profile */
  getProfile: (keycloakId) =>
    request(`/user/user/${keycloakId}`, {
      headers: authHeaders(),
    }),
};

// -------------------------------------------------------------------
// Tenant Management API
// -------------------------------------------------------------------

export const tenantApi = {
  /** Get tenant configuration by tenant_id */
  getTenant: (tenantId) =>
    request(`/tenant-management/tenant/${tenantId}`, {
      headers: tenantHeaders(),
    }),
};

// -------------------------------------------------------------------
// Orchestrator API (Temporal workflows — registration flows)
// -------------------------------------------------------------------

export const orchestratorApi = {
  /** Register a new agent via Temporal workflow */
  registerAgent: (data) =>
    request("/orchestrator/agent", {
      method: "POST",
      headers: tenantHeaders(),
      body: JSON.stringify(data),
    }),
};

// -------------------------------------------------------------------
// Dispute API (Core Banking Service)
// -------------------------------------------------------------------

export const disputeApi = {
  /** Get all disputes for current user */
  getDisputes: () =>
    request("/dispute/api/v1/disputes", {
      headers: authHeaders(),
    }),

  /** Get all disputes for tenant (admin only) */
  getTenantDisputes: () =>
    request("/dispute/api/v1/disputes/tenant", {
      headers: authHeaders(),
    }),

  /** Get a specific dispute */
  getDispute: (disputeId) =>
    request(`/dispute/api/v1/disputes/${disputeId}`, {
      headers: authHeaders(),
    }),

  /** Create a new dispute */
  createDispute: (data) =>
    request("/dispute/api/v1/disputes", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify(data),
    }),

  /** Resolve a dispute (admin only) */
  resolveDispute: (disputeId, resolution) =>
    request(`/dispute/api/v1/administration/disputes/${disputeId}/resolve`, {
      method: "PUT",
      headers: authHeaders(),
      body: JSON.stringify({ resolution }),
    }),
};

// -------------------------------------------------------------------
// Network Operations API
// -------------------------------------------------------------------

export const networkOperationsApi = {
  /**
   * Get channel success rate predictions
   * @param {object} filters - optional: { type, channel, medium }
   */
  getPredictions: (filters = {}) => {
    const params = new URLSearchParams();
    if (filters.type) params.append("type", filters.type);
    if (filters.channel) params.append("channel", filters.channel);
    if (filters.medium) params.append("medium", filters.medium);
    const queryString = params.toString();
    return request(
      `/network-operations/api/v1/predictions${queryString ? `?${queryString}` : ""}`,
      {
        headers: authHeaders(),
      },
    );
  },

  /**
   * Register a transaction (success or failure) to update predictions
   * @param {object} data - { type, channel, medium, status, amount?, agent_id? }
   */
  registerTransaction: (data) =>
    request("/network-operations/api/v1/transactions", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify(data),
    }),

  /**
   * List transactions for the agent.
   * @param {string} agentId - keycloak ID of the agent
   * @param {object} filters - optional: { status, type, from_date, to_date }
   * @param {number} page
   * @param {number} limit
   * @deprecated - Use getPredictions for new network operations service
   */
  listTransactions: (agentId, filters = {}, page = 1, limit = 20) => {
    const params = new URLSearchParams();
    params.append("page", String(page));
    params.append("limit", String(limit));
    if (agentId) params.append("agent_id", agentId);
    if (filters.status) params.append("status", filters.status);
    if (filters.type) params.append("type", filters.type);
    if (filters.from_date) params.append("from_date", filters.from_date);
    if (filters.to_date) params.append("to_date", filters.to_date);
    return request(`/network-operations/api/v1/transactions?${params}`, {
      headers: authHeaders(),
    });
  },

  /** Get a single transaction by ID - @deprecated */
  getTransaction: (id) =>
    request(`/network-operations/api/v1/transactions/${id}`, {
      headers: authHeaders(),
    }),

  /** Get agent cash position - @deprecated */
  getAgentCashPosition: (agentId) =>
    request(`/network-operations/api/v1/cash-positions/agents/${agentId}`, {
      headers: authHeaders(),
    }),

  /**
   * Create a Cash In transaction - @deprecated
   * @param {object} data - { agent_id, customer_account, amount, currency, reference, description }
   */
  createCashIn: (data) =>
    request("/network-operations/api/v1/transactions", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({
        ...data,
        transaction_type: "cash_in",
      }),
    }),

  /**
   * Create a Cash Out transaction - @deprecated
   * @param {object} data - { agent_id, customer_account, amount, currency, reference, description }
   */
  createCashOut: (data) =>
    request("/network-operations/api/v1/transactions", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({
        ...data,
        transaction_type: "cash_out",
      }),
    }),

  /**
   * Update transaction status (e.g., complete, cancel) - @deprecated
   * @param {string} transactionId
   * @param {string} status - pending|completed|failed|cancelled
   */
  updateTransactionStatus: (transactionId, status) =>
    request(`/network-operations/api/v1/transactions/${transactionId}/status`, {
      method: "PUT",
      headers: authHeaders(),
      body: JSON.stringify({ status }),
    }),
};

// Keep for backward compat – wraps networkOperationsApi
export const networkStatusApi = networkOperationsApi;

// -------------------------------------------------------------------
// Inventory API
// -------------------------------------------------------------------

export const inventoryApi = {
  // ─── Store Management ─────────────────────────────────────────────

  /** Create a new store (agent only) */
  createStore: (data) =>
    request("/inventory/stores", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify(data),
    }),

  /** Get all stores owned by the agent */
  getStores: (ownerKeycloakId = null) => {
    const params = ownerKeycloakId
      ? `?owner_keycloak_id=${ownerKeycloakId}`
      : "";
    return request(`/inventory/stores${params}`, {
      headers: authHeaders(),
    });
  },

  /** Get all stores (admin only - no filter) */
  getAllStores: () =>
    request("/inventory/stores", {
      headers: authHeaders(),
    }),

  /** Get a single store by ID */
  getStore: (storeId) =>
    request(`/inventory/stores/${storeId}`, {
      headers: authHeaders(),
    }),

  /** Update a store's name / description */
  updateStore: (storeId, data) =>
    request(`/inventory/stores/${storeId}`, {
      method: "PUT",
      headers: authHeaders(),
      body: JSON.stringify(data),
    }),

  /** Delete a store and all its inventory items */
  deleteStore: (storeId) =>
    request(`/inventory/stores/${storeId}`, {
      method: "DELETE",
      headers: authHeaders(),
    }),

  // ─── Inventory Management ─────────────────────────────────────────

  /** Get all inventory items for a store with optional filters */
  getInventoryItems: (storeId, filters = {}) => {
    const params = new URLSearchParams();
    if (filters.search) params.append("search", filters.search);
    if (filters.category && filters.category !== "all")
      params.append("category", filters.category);
    if (filters.status && filters.status !== "all")
      params.append("status", filters.status);
    const query = params.toString() ? `?${params.toString()}` : "";
    return request(`/inventory/stores/${storeId}/items${query}`, {
      headers: authHeaders(),
    });
  },

  /** Get a specific inventory item */
  getInventoryItem: (itemId) =>
    request(`/inventory/inventory/items/${itemId}`, {
      headers: authHeaders(),
    }),

  /** Create a new inventory item for a store */
  createInventoryItem: (storeId, data) =>
    request(`/inventory/stores/${storeId}/items`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify(data),
    }),

  /** Update an inventory item */
  updateInventoryItem: (itemId, data) =>
    request(`/inventory/inventory/items/${itemId}`, {
      method: "PUT",
      headers: authHeaders(),
      body: JSON.stringify(data),
    }),

  /** Delete an inventory item */
  deleteInventoryItem: (itemId) =>
    request(`/inventory/inventory/items/${itemId}`, {
      method: "DELETE",
      headers: authHeaders(),
    }),

  // ─── Image Management ─────────────────────────────────────────────

  /** Upload image for an item */
  uploadItemImage: (itemId, file) => {
    const formData = new FormData();
    formData.append("file", file);
    return request(`/inventory/inventory/items/${itemId}/images`, {
      method: "POST",
      headers: {
        ...getTenantHeadersFromConfig(),
        Authorization: `Bearer ${localStorage.getItem("agent_dashboard_token")}`,
      },
      body: formData,
    });
  },

  /** Add image URL for an item */
  addItemImageUrl: (itemId, url) =>
    request(`/inventory/inventory/items/${itemId}/images/url`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ url }),
    }),

  /** Get all images for an item */
  getItemImages: (itemId) =>
    request(`/inventory/inventory/items/${itemId}/images`, {
      headers: authHeaders(),
    }),

  /** Delete an image */
  deleteItemImage: (itemId, imageId) =>
    request(`/inventory/inventory/items/${itemId}/images/${imageId}`, {
      method: "DELETE",
      headers: authHeaders(),
    }),

  // ─── Sales & Metrics ─────────────────────────────────────────────

  /** Get stock alerts (low stock, critical, out of stock) */
  getStockAlerts: () =>
    request("/inventory/inventory/alerts", {
      headers: authHeaders(),
    }),

  /** Create a sale and update inventory */
  createSale: (data) =>
    request("/inventory/inventory/sales", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify(data),
    }),

  /** Get sales history */
  getSalesHistory: (limit = 50) => {
    const query = limit ? `?limit=${limit}` : "";
    return request(`/inventory/inventory/sales${query}`, {
      headers: authHeaders(),
    });
  },

  /** Get inventory metrics */
  getInventoryMetrics: () =>
    request("/inventory/inventory/metrics", {
      headers: authHeaders(),
    }),
};

// -------------------------------------------------------------------
// Document API (Core Banking document-service → MinIO)
// Upload a file, get back a permanent URL, then pass that URL wherever
// an image/document reference is needed.
// -------------------------------------------------------------------
export const documentApi = {
  /**
   * Upload a file to the document service.
   * Returns { url, id, filename, content_type }
   */
  uploadFile: (file, documentType = "product_image") => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("document_type", documentType);
    const token = localStorage.getItem("agent_dashboard_token");
    const tenantHdrs = getTenantHeadersFromConfig();
    // Do NOT set Content-Type — browser must set multipart/form-data boundary
    return request("/document/upload", {
      method: "POST",
      headers: {
        ...tenantHdrs,
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: formData,
    });
  },
};

// -------------------------------------------------------------------
// Account API (Core Banking Service)
// -------------------------------------------------------------------

export const accountApi = {
  /** Set up PIN for an account */
  setupPin: async (accountNumber, pin) => {
    return request(`/account/account/setup-pin`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ account_number: accountNumber, pin }),
    });
  },
  /** Get account by keycloak_id */
  getAccountByKeycloakId: (keycloakId) =>
    request(`/account/account/keycloak/${keycloakId}`, {
      headers: authHeaders(),
    }),

  /** Get account details by account number (using ledger endpoint) */
  getAccountByNumber: (accountNumber) =>
    request(`/ledger/txn/account-number/${accountNumber}`, {
      headers: authHeaders(),
    }),

  /** Get account balance */
  getAccountBalance: (accountNumber) =>
    request(`/account/account/${accountNumber}/balance`, {
      headers: authHeaders(),
    }),

  /** Get all accounts (for chart of accounts view) */
  getAllAccounts: () =>
    request(`/account/account/all`, {
      headers: authHeaders(),
    }),

  /** Create a new account (e.g. for a business/store) */
  createAccount: (data) =>
    request(`/account/account`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify(data),
    }),

  /** Create a cash in (deposit) transaction */
  createCashIn: (data) =>
    request(`/agent/transactions/cash-in`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify(data),
    }),

  /** Create a cash out (withdrawal) transaction */
  createCashOut: (data) =>
    request(`/agent/transactions/cash-out`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify(data),
    }),

  /** Get cash book transactions */
  getCashBook: (agentId, transactionType = null, limit = 100) => {
    const params = new URLSearchParams();
    if (agentId) params.append("agent_id", agentId);
    if (transactionType) params.append("transaction_type", transactionType);
    params.append("limit", limit);
    const query = params.toString() ? `?${params.toString()}` : "";
    return request(`/agent/transactions/cash-book${query}`, {
      headers: authHeaders(),
    });
  },
};

// -------------------------------------------------------------------
// POS Terminal Management API
// -------------------------------------------------------------------

export const posTerminalApi = {
  /** Get all terminals. Params can include: q (search), status, assigned_to */
  getTerminals: (params = {}) => {
    const query = new URLSearchParams();
    Object.entries(params).forEach(
      ([k, v]) => v != null && query.append(k, String(v)),
    );
    const qs = query.toString() ? `?${query.toString()}` : "";
    return request(`/pos-terminals/terminals${qs}`, { headers: authHeaders() });
  },

  /** Get a specific terminal by ID */
  getTerminal: (id) =>
    request(`/pos-terminals/terminals/${id}`, { headers: authHeaders() }),

  /** Create a new terminal */
  createTerminal: (data) =>
    request("/pos-terminals/terminals", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify(data),
    }),

  /** Update a terminal (PUT) */
  updateTerminal: (id, data) =>
    request(`/pos-terminals/terminals/${id}`, {
      method: "PUT",
      headers: authHeaders(),
      body: JSON.stringify(data),
    }),

  /** Delete a terminal */
  deleteTerminal: (id) =>
    request(`/pos-terminals/terminals/${id}`, {
      method: "DELETE",
      headers: authHeaders(),
    }),

  /** Get terminals filtered by status (Active, Inactive, Maintenance) */
  getTerminalsByStatus: (status) =>
    request(`/pos-terminals/terminals/status/${status}`, {
      headers: authHeaders(),
    }),

  /** Full-text search across location, model, serial_number, assigned_to */
  searchTerminals: (q) =>
    request(`/pos-terminals/terminals/search?q=${encodeURIComponent(q)}`, {
      headers: authHeaders(),
    }),

  /** Get service records for a terminal */
  getServiceRecords: (id) =>
    request(`/pos-terminals/terminals/${id}/servicerecords`, {
      headers: authHeaders(),
    }),

  /** Create a service record for a terminal */
  createServiceRecord: (id, data) =>
    request(`/pos-terminals/terminals/${id}/servicerecords`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify(data),
    }),

  /** Get terminal configuration */
  getConfiguration: (id) =>
    request(`/pos-terminals/terminals/${id}/configuration`, {
      headers: authHeaders(),
    }),

  /** Update terminal configuration */
  updateConfiguration: (id, config) =>
    request(`/pos-terminals/terminals/${id}/configuration`, {
      method: "PUT",
      headers: authHeaders(),
      body: JSON.stringify(config),
    }),
};

// -------------------------------------------------------------------
// POS Hardware Management API
// -------------------------------------------------------------------

export const posHardwareApi = {
  /** Get all hardware POS devices. Params: agent_id, status, device_type */
  getPOSDevices: (params = {}) => {
    const query = new URLSearchParams();
    Object.entries(params).forEach(
      ([k, v]) => v != null && query.append(k, String(v)),
    );
    const qs = query.toString() ? `?${query.toString()}` : "";
    return request(`/pos-hardware/api/v1/pos-devices${qs}`, {
      headers: authHeaders(),
    });
  },

  /** Get a specific hardware device */
  getPOSDevice: (deviceId) =>
    request(`/pos-hardware/api/v1/pos-devices/${deviceId}`, {
      headers: authHeaders(),
    }),

  /** Get device health report */
  getDeviceHealth: (deviceId) =>
    request(`/pos-hardware/api/v1/pos-devices/${deviceId}/health`, {
      headers: authHeaders(),
    }),

  /** Get all edge nodes */
  getEdgeNodes: () =>
    request("/pos-hardware/api/v1/edge-nodes", { headers: authHeaders() }),

  /** Get all IoT devices */
  getIoTDevices: () =>
    request("/pos-hardware/api/v1/iot-devices", { headers: authHeaders() }),
};

// -------------------------------------------------------------------
// POS Integration API
// -------------------------------------------------------------------

export const posIntegrationApi = {
  /** Get all POS transactions. Params: device_id, status, limit */
  getTransactions: (params = {}) => {
    const query = new URLSearchParams();
    Object.entries(params).forEach(
      ([k, v]) => v != null && query.append(k, String(v)),
    );
    const qs = query.toString() ? `?${query.toString()}` : "";
    return request(`/pos-integration/api/v1/transactions${qs}`, {
      headers: authHeaders(),
    });
  },

  /** Get a specific transaction by ID */
  getTransaction: (id) =>
    request(`/pos-integration/api/v1/transactions/${id}`, {
      headers: authHeaders(),
    }),

  /** Create a new transaction */
  createTransaction: (data) =>
    request("/pos-integration/api/v1/transactions", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify(data),
    }),

  /** Get registered integration-layer POS devices */
  getDevices: () =>
    request("/pos-integration/api/v1/devices", { headers: authHeaders() }),
};

// -------------------------------------------------------------------
// POS Management API (device lifecycle & analytics)
// -------------------------------------------------------------------

export const posManagementApi = {
  /** Get all devices. Params: agent_id, status */
  getDevices: (params = {}) => {
    const query = new URLSearchParams();
    Object.entries(params).forEach(
      ([k, v]) => v != null && query.append(k, String(v)),
    );
    const qs = query.toString() ? `?${query.toString()}` : "";
    return request(`/pos-management/api/v1/devices${qs}`, {
      headers: authHeaders(),
    });
  },

  /** Get a specific device */
  getDevice: (id) =>
    request(`/pos-management/api/v1/devices/${id}`, { headers: authHeaders() }),

  /** Update device status */
  updateDeviceStatus: (id, status) =>
    request(`/pos-management/api/v1/devices/${id}/status`, {
      method: "PUT",
      headers: authHeaders(),
      body: JSON.stringify({ status }),
    }),

  /** Get transactions for a device */
  getDeviceTransactions: (id, params = {}) => {
    const query = new URLSearchParams(params);
    const qs = query.toString() ? `?${query.toString()}` : "";
    return request(`/pos-management/api/v1/devices/${id}/transactions${qs}`, {
      headers: authHeaders(),
    });
  },

  /** Get device analytics across all devices */
  getDeviceAnalytics: () =>
    request("/pos-management/api/v1/analytics/devices", {
      headers: authHeaders(),
    }),

  /** Restart a device remotely */
  restartDevice: (id) =>
    request(`/pos-management/api/v1/devices/${id}/restart`, {
      method: "POST",
      headers: authHeaders(),
    }),

  /** Get device configuration */
  getConfiguration: (id) =>
    request(`/pos-management/api/v1/devices/${id}/configuration`, {
      headers: authHeaders(),
    }),

  /** Update device configuration */
  updateConfiguration: (id, config) =>
    request(`/pos-management/api/v1/devices/${id}/configuration`, {
      method: "PUT",
      headers: authHeaders(),
      body: JSON.stringify(config),
    }),
};

// -------------------------------------------------------------------
// POS Request API (Agent ordering workflow)
// -------------------------------------------------------------------

export const posRequestApi = {
  /**
   * Create a new POS request
   * @param {Object} data - Request data
   * @returns {Promise<Object>} Created POS request
   */
  createRequest: (data) =>
    request("/agent/agent/pos-requests", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify(data),
    }),

  /**
   * Get all my POS requests
   * @param {string} [status] - Optional status filter
   * @returns {Promise<Array>} List of POS requests
   */
  getMyRequests: (status = null) => {
    const params = status ? `?status=${status}` : "";
    return request(`/agent/agent/pos-requests/my-requests${params}`, {
      headers: authHeaders(),
    });
  },

  /**
   * Get a specific POS request
   * @param {string} requestId - Request ID
   * @returns {Promise<Object>} POS request details
   */
  getRequest: (requestId) =>
    request(`/agent/pos-requests/${requestId}`, {
      headers: authHeaders(),
    }),

  /**
   * Update a pending POS request
   * @param {string} requestId - Request ID
   * @param {Object} data - Update data
   * @returns {Promise<Object>} Updated request
   */
  updateRequest: (requestId, data) =>
    request(`/agent/agent/pos-requests/${requestId}`, {
      method: "PATCH",
      headers: authHeaders(),
      body: JSON.stringify(data),
    }),

  /**
   * Cancel a pending POS request
   * @param {string} requestId - Request ID
   * @returns {Promise<void>}
   */
  cancelRequest: (requestId) =>
    request(`/agent/agent/pos-requests/${requestId}`, {
      method: "DELETE",
      headers: authHeaders(),
    }),
};

// -------------------------------------------------------------------
// Business API (KYB verified businesses)
// -------------------------------------------------------------------

export const businessApi = {
  /** Get all businesses for the agent */
  getAgentBusinesses: (agentId) =>
    request(`/agent/agent/businesses/agent/${agentId}`, {
      headers: authHeaders(),
    }),

  /** Get all businesses (admin view) */
  getAllBusinesses: () =>
    request("/agent/agent/businesses", {
      headers: authHeaders(),
    }),

  /** Get a specific business by ID */
  getBusiness: (id) =>
    request(`/agent/agent/businesses/${id}`, {
      headers: authHeaders(),
    }),

  /** Create/register a new business for agent */
  createBusiness: (data) =>
    request("/agent/agent/businesses/create", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify(data),
    }),

  /** Update an existing business */
  updateBusiness: (businessId, data) =>
    request(`/agent/agent/businesses/${businessId}`, {
      method: "PATCH",
      headers: authHeaders(),
      body: JSON.stringify(data),
    }),

  /** Unlink/delete a business */
  unlinkBusiness: (businessId) =>
    request(`/agent/agent/businesses/unlink/${businessId}`, {
      method: "DELETE",
      headers: authHeaders(),
    }),

  /** Link a verified business to agent */
  linkBusinessToAgent: (businessId) =>
    request("/agent/agent/businesses/link-agent", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ business_id: businessId }),
    }),

  /** Link store to business */
  linkStoreToBusiness: (storeId, businessId) =>
    request(`/inventory/stores/${storeId}/link-business`, {
      method: "PUT",
      headers: authHeaders(),
      body: JSON.stringify({ business_id: businessId }),
    }),

  /** Link POS terminal to business */
  linkPOSTerminalToBusiness: (terminalId, businessId) =>
    request(`/pos-terminals/terminals/${terminalId}/link-business`, {
      method: "PUT",
      headers: authHeaders(),
      body: JSON.stringify({ business_id: businessId }),
    }),

  /** Get stores for a business */
  getBusinessStores: (businessId) =>
    request(`/inventory/stores/business/${businessId}`, {
      headers: authHeaders(),
    }),

  /** Get POS terminals for a business */
  getBusinessPOSTerminals: (businessId) =>
    request(`/pos-terminals/terminals/business/${businessId}`, {
      headers: authHeaders(),
    }),
};

// -------------------------------------------------------------------
// Messaging API
// -------------------------------------------------------------------
export const messagingApi = {
  /**
   * Get all conversations for the current agent.
   * Pass storeEntityId to load conversations that customers started with a
   * specific store (store entity_id is used as agent_keycloak_id by the customer portal).
   */
  getConversations: (storeEntityId = null) => {
    const tenantId = getTenantId();
    const keycloakId = storeEntityId || localStorage.getItem("keycloakId");

    if (!keycloakId) {
      return Promise.reject(new Error("Not authenticated"));
    }

    return request(
      `/messaging/conversations?tenant_id=${tenantId}&keycloak_id=${keycloakId}&user_type=agent`,
      {
        headers: authHeaders(),
      },
    );
  },

  /** Get messages for a conversation */
  getMessages: (conversationId, limit = 50, offset = 0) => {
    const tenantId = getTenantId();

    return request(
      `/messaging/conversations/${conversationId}/messages?tenant_id=${tenantId}&limit=${limit}&offset=${offset}`,
      {
        headers: authHeaders(),
      },
    );
  },

  /** Send a message */
  sendMessage: (messageData) => {
    const tenantId = getTenantId();
    const keycloakId = localStorage.getItem("keycloakId");
    const displayName = localStorage.getItem("displayName") || "Agent";

    if (!keycloakId) {
      return Promise.reject(new Error("Not authenticated"));
    }

    const queryParams = new URLSearchParams({
      tenant_id: tenantId,
      sender_keycloak_id: keycloakId,
      sender_name: displayName,
      sender_type: "agent",
    });

    return request(`/messaging/messages?${queryParams}`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify(messageData),
    });
  },

  /** Mark conversation as read. Pass storeEntityId when the conversation belongs to a store. */
  markAsRead: (conversationId, storeEntityId = null) => {
    const tenantId = getTenantId();
    const keycloakId = storeEntityId || localStorage.getItem("keycloakId");

    if (!keycloakId) {
      return Promise.reject(new Error("Not authenticated"));
    }

    const queryParams = new URLSearchParams({
      tenant_id: tenantId,
      keycloak_id: keycloakId,
      user_type: "agent",
    });

    return request(
      `/messaging/conversations/${conversationId}/mark-read?${queryParams}`,
      {
        method: "POST",
        headers: authHeaders(),
      },
    );
  },

  /** Connect to WebSocket for real-time messages */
  connectWebSocket: (onMessage) => {
    const keycloakId = localStorage.getItem("keycloakId");

    if (!keycloakId) {
      throw new Error("Not authenticated");
    }

    const wsUrl = AGENT_BANKING_BASE.replace("https://", "wss://").replace(
      "http://",
      "ws://",
    );
    const ws = new WebSocket(`${wsUrl}/messaging/ws/${keycloakId}`);

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (onMessage) {
        onMessage(data);
      }
    };

    ws.onerror = (error) => {
      console.error("WebSocket error:", error);
    };

    // Send heartbeat every 30 seconds
    const heartbeat = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send("ping");
      }
    }, 30000);

    ws.onclose = () => {
      clearInterval(heartbeat);
    };

    return ws;
  },

  /** Translate text via the realtime-translation service */
  translateText: (text, targetLanguage, sourceLanguage = null) => {
    return request("/translation/", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({
        text,
        target_language: targetLanguage,
        ...(sourceLanguage ? { source_language: sourceLanguage } : {}),
        apply_glossary: true,
      }),
    });
  },

  /** Get supported languages for translation */
  getSupportedLanguages: () => {
    return request("/messaging/supported-languages", {
      headers: authHeaders(),
    });
  },

  /** Update language preference for a conversation */
  updateLanguagePreference: (
    conversationId,
    language,
    autoTranslate = true,
  ) => {
    const tenantId = getTenantId();
    const keycloakId = localStorage.getItem("keycloakId");

    if (!keycloakId) {
      return Promise.reject(new Error("Not authenticated"));
    }

    const queryParams = new URLSearchParams({
      tenant_id: tenantId,
      keycloak_id: keycloakId,
      user_type: "agent",
    });

    return request(
      `/messaging/conversations/${conversationId}/language-preference?${queryParams}`,
      {
        method: "PUT",
        headers: authHeaders(),
        body: JSON.stringify({ language, auto_translate: autoTranslate }),
      },
    );
  },

  /** Get conversations for a specific business */
  getConversationsByBusiness: (businessId) => {
    const tenantId = getTenantId();
    const keycloakId = localStorage.getItem("keycloakId");

    if (!keycloakId) {
      return Promise.reject(new Error("Not authenticated"));
    }

    return request(
      `/messaging/conversations/by-business/${businessId}?tenant_id=${tenantId}&keycloak_id=${keycloakId}`,
      {
        headers: authHeaders(),
      },
    );
  },

  /** Get all businesses that have conversations with the agent */
  getBusinessesWithConversations: () => {
    const tenantId = getTenantId();
    const keycloakId = localStorage.getItem("keycloakId");

    if (!keycloakId) {
      return Promise.reject(new Error("Not authenticated"));
    }

    return request(
      `/messaging/businesses/with-conversations?tenant_id=${tenantId}&keycloak_id=${keycloakId}`,
      {
        headers: authHeaders(),
      },
    );
  },
};

// -------------------------------------------------------------------
// Store Map API (Store Map Service)
// -------------------------------------------------------------------

export const storeMapApi = {
  /** Register or update a store location on the map */
  registerStore: (data) =>
    request("/store-map/stores", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify(data),
    }),

  /** Get a specific store by entity ID */
  getStore: (entityId) =>
    request(`/store-map/stores/${entityId}`, {
      headers: authHeaders(),
    }),

  /** Find nearby stores within a given radius */
  findNearbyStores: (latitude, longitude, radiusKm = 5) =>
    request("/store-map/stores/nearby", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({
        latitude,
        longitude,
        radius_km: radiusKm,
      }),
    }),

  /** Get all stores (for map display) */
  getAllStores: () =>
    request("/store-map/stores", {
      headers: authHeaders(),
    }),

  /** Update store status */
  updateStoreStatus: (entityId, status) =>
    request(`/store-map/stores/${entityId}/status`, {
      method: "PATCH",
      headers: authHeaders(),
      body: JSON.stringify({ status }),
    }),

  /** Get stores by state */
  getStoresByState: (state) =>
    request(`/store-map/stores/state/${state}`, {
      headers: authHeaders(),
    }),
};

// -------------------------------------------------------------------
// Commission & Settlement API
// Routes to commission-settlement service via APISIX (/commission/* → /api/v1/*)
// -------------------------------------------------------------------

export const commissionApi = {
  /**
   * Get the agent's commission wallet balance.
   * @param {string} agentId  Internal UUID of the agent (from agent-service)
   */
  getBalance: (agentId) =>
    request(`/commission/api/v1/agents/${agentId}/balance`, {
      headers: authHeaders(),
    }),

  /**
   * List commissions for an agent with optional filters.
   * @param {string} agentId  Internal UUID
   * @param {object} params   { page, limit, status, start_date, end_date }
   */
  listCommissions: (agentId, params = {}) => {
    const qp = new URLSearchParams({
      agent_id: agentId,
      page: params.page ?? 1,
      limit: params.limit ?? 50,
      ...(params.status && { status: params.status }),
      ...(params.start_date && { start_date: params.start_date }),
      ...(params.end_date && { end_date: params.end_date }),
    }).toString();
    return request(`/commission/api/v1/commissions?${qp}`, {
      headers: authHeaders(),
    });
  },

  /**
   * List settlement (withdrawal) history for an agent.
   * @param {string} agentId  Internal UUID
   * @param {object} params   { page, limit, status }
   */
  listSettlements: (agentId, params = {}) => {
    const qp = new URLSearchParams({
      agent_id: agentId,
      page: params.page ?? 1,
      limit: params.limit ?? 20,
      ...(params.status && { status: params.status }),
    }).toString();
    return request(`/commission/api/v1/settlements?${qp}`, {
      headers: authHeaders(),
    });
  },

  /**
   * Request a commission withdrawal (creates a pending settlement).
   * @param {object} data { agent_id, payment_method, payment_details, start_date, end_date }
   */
  requestSettlement: (data) =>
    request("/commission/api/v1/settlements", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify(data),
    }),

  /**
   * Trigger processing of a pending settlement (admin / auto-process flow).
   * @param {string} settlementId  UUID of the settlement
   */
  processSettlement: (settlementId) =>
    request(`/commission/api/v1/settlements/${settlementId}/process`, {
      method: "POST",
      headers: authHeaders(),
    }),
};

// -------------------------------------------------------------------
// Order API (Agency Banking Service)
// Routes to inventory service for order management
// -------------------------------------------------------------------

export const orderApi = {
  /**
   * Create a new order (for store sales/transactions)
   * @param {object} data Order details including items, customer info, payment method
   */
  createOrder: (data) =>
    request("/inventory/inventory/orders", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify(data),
    }),

  /**
   * Get orders for a specific store
   * @param {string} storeId Store ID
   * @param {object} filters Optional filters: { status, start_date, end_date, page, limit }
   */
  getStoreOrders: (storeId, filters = {}) => {
    const params = new URLSearchParams();
    if (filters.status) params.append("status", filters.status);
    if (filters.start_date) params.append("start_date", filters.start_date);
    if (filters.end_date) params.append("end_date", filters.end_date);
    if (filters.page) params.append("page", filters.page);
    if (filters.limit) params.append("limit", filters.limit);
    const query = params.toString() ? `?${params.toString()}` : "";
    return request(`/inventory/inventory/stores/${storeId}/orders${query}`, {
      headers: authHeaders(),
    });
  },

  /**
   * Get a specific order by ID
   * @param {string} orderId Order ID
   */
  getOrder: (orderId) =>
    request(`/inventory/inventory/orders/${orderId}`, {
      headers: authHeaders(),
    }),

  /**
   * Get orders for a specific agent
   * @param {string} keycloakId Agent's Keycloak ID
   * @param {object} filters Optional filters: { status, start_date, end_date, page, limit }
   */
  getAgentOrders: (keycloakId, filters = {}) => {
    const params = new URLSearchParams({ agent_keycloak_id: keycloakId });
    if (filters.status) params.append("status", filters.status);
    if (filters.start_date) params.append("start_date", filters.start_date);
    if (filters.end_date) params.append("end_date", filters.end_date);
    if (filters.page) params.append("page", filters.page);
    if (filters.limit) params.append("limit", filters.limit);
    return request(`/inventory/inventory/orders?${params.toString()}`, {
      headers: authHeaders(),
    });
  },

  /**
   * Update order status
   * @param {string} orderId Order ID
   * @param {string} status New status (pending, completed, cancelled, etc.)
   */
  updateOrderStatus: (orderId, status) =>
    request(`/inventory/inventory/orders/${orderId}/status`, {
      method: "PUT",
      headers: authHeaders(),
      body: JSON.stringify({ status }),
    }),

  /**
   * Get order statistics for a store
   * @param {string} storeId Store ID
   * @param {object} dates Optional date range: { start_date, end_date }
   */
  getStoreOrderStats: (storeId, dates = {}) => {
    const params = new URLSearchParams();
    if (dates.start_date) params.append("start_date", dates.start_date);
    if (dates.end_date) params.append("end_date", dates.end_date);
    const query = params.toString() ? `?${params.toString()}` : "";
    return request(
      `/inventory/inventory/stores/${storeId}/orders/stats${query}`,
      {
        headers: authHeaders(),
      },
    );
  },
};

// -------------------------------------------------------------------
// Loyalty API (Agent-side)
// -------------------------------------------------------------------

export const loyaltyApi = {
  /** Enroll customer in loyalty */
  createAccount: (userId) =>
    request("/loyalty/loyalty/accounts", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ user_id: userId }),
    }),

  /** Get customer loyalty account */
  getAccount: (userId) =>
    request(`/loyalty/loyalty/accounts/${userId}`, {
      headers: authHeaders(),
    }),

  /** Earn loyalty points for a customer */
  earnPoints: (userId, data) =>
    request(`/loyalty/loyalty/accounts/${userId}/earn`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify(data),
    }),

  /** Spend/redeem loyalty points for a customer */
  spendPoints: (userId, data) =>
    request(`/loyalty/loyalty/accounts/${userId}/spend`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify(data),
    }),

  /** Get customer loyalty activity history */
  getActivities: (userId, params = {}) => {
    const query = new URLSearchParams();
    if (params.skip !== undefined) query.append("skip", String(params.skip));
    if (params.limit !== undefined) query.append("limit", String(params.limit));
    if (params.activity_type)
      query.append("activity_type", params.activity_type);
    const queryString = query.toString() ? `?${query.toString()}` : "";
    return request(
      `/loyalty/loyalty/accounts/${userId}/activities${queryString}`,
      {
        headers: authHeaders(),
      },
    );
  },
};

// -------------------------------------------------------------------
// Agent Training API
// -------------------------------------------------------------------

export const trainingApi = {
  getAgentDashboard: (agentId) =>
    request(`/training/api/v1/training/agents/${agentId}/dashboard`, {
      headers: authHeaders(),
    }),

  getComplianceStatus: (agentId) =>
    request(`/training/api/v1/training/agents/${agentId}/compliance-status`, {
      headers: authHeaders(),
    }),

  getCertificates: (agentId) =>
    request(`/training/api/v1/training/agents/${agentId}/certificates`, {
      headers: authHeaders(),
    }),

  listCourses: (skip = 0, limit = 50) =>
    request(`/training/api/v1/training/courses?skip=${skip}&limit=${limit}`, {
      headers: authHeaders(),
    }),

  enrollCourse: (agentId, courseId) =>
    request(`/training/api/v1/training/agents/${agentId}/enroll/${courseId}`, {
      method: "POST",
      headers: authHeaders(),
    }),

  enrollMandatory: (agentId) =>
    request(`/training/api/v1/training/agents/${agentId}/enroll-mandatory`, {
      method: "POST",
      headers: authHeaders(),
    }),

  completeLesson: (agentId, lessonId, timeSpentSeconds = 0) =>
    request(`/training/api/v1/training/agents/${agentId}/lessons/${lessonId}/complete`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ time_spent_seconds: timeSpentSeconds }),
    }),

  startQuiz: (agentId, quizId) =>
    request(`/training/api/v1/training/agents/${agentId}/quizzes/${quizId}/start`, {
      method: "POST",
      headers: authHeaders(),
    }),

  submitQuiz: (attemptId, answers) =>
    request(`/training/api/v1/training/attempts/${attemptId}/submit`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ answers }),
    }),
};

// -------------------------------------------------------------------
// Agent Gamification / Performance API
// -------------------------------------------------------------------

export const gamificationApi = {
  getLeaderboard: (limit = 50) =>
    request(`/loyalty/loyalty/leaderboard?limit=${limit}`, {
      headers: authHeaders(),
    }).catch(() =>
      request(`/commission/api/v1/leaderboard?limit=${limit}`, {
        headers: authHeaders(),
      })
    ),

  getAgentPoints: (agentId) =>
    request(`/loyalty/loyalty/accounts/${agentId}`, {
      headers: authHeaders(),
    }),

  getPerformanceMetrics: (agentId, days = 30) =>
    request(`/performance/api/v1/agents/${agentId}/metrics?days=${days}`, {
      headers: authHeaders(),
    }),

  getAgentCommissionSummary: (agentId) =>
    request(`/commission/api/v1/agents/${agentId}/summary`, {
      headers: authHeaders(),
    }),
};
