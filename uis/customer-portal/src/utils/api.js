// API client for customer-portal
// Requests are routed to the correct APISIX gateway based on service prefix:
//   Core Banking  (VITE_CORE_BANKING_URL)  → auth, user, orchestrator, account,
//                                             payment-processing, loan, tenant-management, dispute
//   Agent Banking (VITE_API_URL)            → agent, inventory, pos-*, network-operations
//
// Tenant headers are resolved dynamically from the cached tenant config in localStorage.

const CORE_BANKING_BASE =
  import.meta.env.VITE_CORE_BANKING_URL || "https://54agent.upi.dev";
const AGENT_BANKING_BASE =
  import.meta.env.VITE_API_URL || "https://54agent.upi.dev";
const DEFAULT_TENANT_ID = import.meta.env.VITE_TENANT_ID || "54agent";

/**
 * Map service path prefixes to their gateway base URL.
 * Checked in order — first match wins.
 */
const SERVICE_BASE_URLS = {
  // ── Core Banking ──────────────────────────────────────────────────
  "/auth": AGENT_BANKING_BASE,
  "/user": AGENT_BANKING_BASE,
  "/orchestrator": AGENT_BANKING_BASE,
  "/account": AGENT_BANKING_BASE,
  "/payment-processing": AGENT_BANKING_BASE,
  "/loan": AGENT_BANKING_BASE,
  "/dispute": AGENT_BANKING_BASE,
  "/tenant-management": AGENT_BANKING_BASE,
  "/savings": AGENT_BANKING_BASE,
  "/card": AGENT_BANKING_BASE,
  // ── Agent Banking ─────────────────────────────────────────────────
  "/agent": AGENT_BANKING_BASE,
  "/inventory": AGENT_BANKING_BASE,
  "/network-operations": AGENT_BANKING_BASE,
  "/pos-terminals": AGENT_BANKING_BASE,
  "/pos-hardware": AGENT_BANKING_BASE,
  "/pos-management": AGENT_BANKING_BASE,
  "/store-map": AGENT_BANKING_BASE,
  "/messaging": AGENT_BANKING_BASE,
  "/translation": AGENT_BANKING_BASE,
  "/storefront": AGENT_BANKING_BASE,
};

/** Resolve the correct base URL for a given request path */
function getBaseUrl(path) {
  for (const [prefix, baseUrl] of Object.entries(SERVICE_BASE_URLS)) {
    if (path.startsWith(prefix)) return baseUrl;
  }
  // Default to core banking for unrecognised paths
  return CORE_BANKING_BASE;
}

const STORAGE = {
  TOKEN: "customer_portal_token",
  REFRESH_TOKEN: "customer_portal_refresh_token",
  TOKEN_EXPIRY: "customer_portal_token_expiry",
  USER: "customer_portal_user",
  KEYCLOAK_ID: "customer_portal_keycloak_id",
};

export { STORAGE };

/**
 * Read tenant headers from the cached tenant config stored by tenantService.
 * Falls back to env variables when no config is cached yet.
 */
function getTenantHeadersFromConfig() {
  const configStr = localStorage.getItem("tenant_config");
  if (!configStr) {
    return { "x-tenant-id": DEFAULT_TENANT_ID };
  }

  try {
    const tenant = JSON.parse(configStr);
    const headers = {};

    headers["x-tenant-id"] = tenant.tenant_id || DEFAULT_TENANT_ID;

    const featureFlags = Array.isArray(tenant.feature_flags)
      ? tenant.feature_flags
      : [];
    const authFeature = featureFlags.find((f) => f.name === "auth");
    const accountFeature = featureFlags.find((f) => f.name === "account");
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
    // Always set x-ledger-id regardless of whether auth config is present
    headers["x-ledger-id"] = String(
      accountFeature?.config?.account?.ledger_id || "1",
    );

    return headers;
  } catch (error) {
    console.error("Error parsing tenant config:", error);
    return { "x-tenant-id": DEFAULT_TENANT_ID };
  }
}

/** Extract the tenant_id string from cached config */
function getTenantId() {
  try {
    const cfg = JSON.parse(localStorage.getItem("tenant_config") || "{}");
    return cfg.tenant_id || DEFAULT_TENANT_ID;
  } catch {
    return DEFAULT_TENANT_ID;
  }
}

/** Headers required for all requests (no auth) */
const tenantHeaders = () => ({
  "Content-Type": "application/json",
  ...getTenantHeadersFromConfig(),
});

/** Headers for authenticated requests */
const authHeaders = () => {
  const token = localStorage.getItem(STORAGE.TOKEN);
  const keycloakId = localStorage.getItem(STORAGE.KEYCLOAK_ID);
  return {
    ...tenantHeaders(),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(keycloakId ? { "x-keycloak-id": keycloakId } : {}),
  };
};

const handleResponse = async (res) => {
  if (res.status === 204) return null;
  const json = await res.json().catch(() => null);
  if (!res.ok) {
    const message =
      json?.detail ?? json?.message ?? `Request failed: ${res.status}`;
    throw new Error(message);
  }
  return json;
};

/**
 * Central request wrapper — automatically resolves the base URL and injects
 * the correct headers (tenant + optional auth token) for every call.
 *
 * @param {string} path        - e.g. "/auth/auth/login"
 * @param {object} options     - standard fetch options (method, body, …)
 * @param {boolean} withAuth   - include Bearer token + x-keycloak-id (default true)
 */
async function request(path, options = {}, withAuth = true) {
  const baseUrl = getBaseUrl(path);
  const headers = {
    ...(withAuth ? authHeaders() : tenantHeaders()),
    ...options.headers,
  };
  const res = await fetch(`${baseUrl}${path}`, { ...options, headers });
  return handleResponse(res);
}

// ─── Auth ─────────────────────────────────────────────────────────────────────
// Routes to: CORE_BANKING_BASE
export const authApi = {
  login: (email, password) =>
    request(
      "/auth/auth/login",
      { method: "POST", body: JSON.stringify({ email, password }) },
      false, // no token yet
    ),

  refresh: (refreshToken) =>
    request(
      "/auth/token/refresh",
      { method: "POST", body: JSON.stringify({ refresh_token: refreshToken }) },
      false,
    ),

  logout: (refreshToken) =>
    request(
      "/auth/auth/logout",
      { method: "POST", body: JSON.stringify({ refresh_token: refreshToken }) },
      false,
    ),
};

// ─── User / Customer ──────────────────────────────────────────────────────────
// Routes to: CORE_BANKING_BASE
export const userApi = {
  getProfile: (keycloakId) => request(`/user/user?keycloak_id=${keycloakId}`),

  updateProfile: (keycloakId, data) =>
    request(`/user/user/${keycloakId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  getTransactions: (accountNumber, params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return request(
      `/ledger/txn/account-number/${accountNumber}${qs ? "?" + qs : ""}`,
    );
  },

  getAccounts: () => request("/user/user/accounts"),
};

// ─── Account ──────────────────────────────────────────────────────────────────
// GET /account/account/keycloak/{keycloakId}  → account details & balance
// Routes to: CORE_BANKING_BASE
export const accountApi = {
  getByKeycloakId: (keycloakId) =>
    request(`/account/account/keycloak/${keycloakId}`),

  /** Set up PIN for an account */
  setupPin: async (accountNumber, pin) => {
    return request(`/account/account/setup-pin`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ account_number: accountNumber, pin }),
    });
  },
};

// ─── Orchestrator ─────────────────────────────────────────────────────────────
// POST /orchestrator/customer  → register a new customer
// Routes to: CORE_BANKING_BASE
// No auth token required — public registration endpoint
export const orchestratorApi = {
  registerCustomer: (data) =>
    request(
      "/orchestrator/customer",
      { method: "POST", body: JSON.stringify(data) },
      false,
    ),
};

/**
 * Inventory/Store API for customer portal
 */
export const inventoryApi = {
  /** Get all stores */
  getStores: async () => {
    return request("/inventory/stores", {
      headers: authHeaders(),
    });
  },

  /** Get all items for a store */
  getStoreItems: async (storeId, filters = {}) => {
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

  /** Get all items from all stores (marketplace view) */
  getAllItems: async (filters = {}) => {
    const params = new URLSearchParams();
    if (filters.search) params.append("search", filters.search);
    if (filters.category && filters.category !== "all")
      params.append("category", filters.category);
    if (filters.status) params.append("status", filters.status);
    if (filters.limit) params.append("limit", filters.limit.toString());
    const query = params.toString() ? `?${params.toString()}` : "";
    return request(`/inventory/items${query}`, {
      headers: authHeaders(),
    });
  },

  /** Place an order (customer workflow) */
  placeOrder: async (orderData) => {
    return request("/inventory/orders", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify(orderData),
    });
  },
};
// -------------------------------------------------------------------
// Store Map API (Store Map Service)
// -------------------------------------------------------------------

// ─── Messaging ───────────────────────────────────────────────────────────────
// Routes to: AGENT_BANKING_BASE  (/messaging/*)
export const messagingApi = {
  /** Get all conversations for the current customer */
  getConversations: () => {
    const tenantId = getTenantId();
    const keycloakId = localStorage.getItem(STORAGE.KEYCLOAK_ID);
    if (!keycloakId) return Promise.reject(new Error("Not authenticated"));
    return request(
      `/messaging/conversations?tenant_id=${tenantId}&keycloak_id=${keycloakId}&user_type=customer`,
    );
  },

  /** Create or get existing conversation with a store/agent */
  createConversation: (agentKeycloakId, agentName) => {
    const tenantId = getTenantId();
    const keycloakId = localStorage.getItem(STORAGE.KEYCLOAK_ID);
    const user = JSON.parse(localStorage.getItem(STORAGE.USER) || "{}");
    const customerName =
      `${user.first_name || ""} ${user.last_name || ""}`.trim() || "Customer";
    if (!keycloakId) return Promise.reject(new Error("Not authenticated"));
    return request(`/messaging/conversations?tenant_id=${tenantId}`, {
      method: "POST",
      body: JSON.stringify({
        agent_keycloak_id: agentKeycloakId,
        customer_keycloak_id: keycloakId,
        agent_name: agentName,
        customer_name: customerName,
      }),
    });
  },

  /** Get messages for a conversation */
  getMessages: (conversationId, limit = 50, offset = 0) => {
    const tenantId = getTenantId();
    return request(
      `/messaging/conversations/${conversationId}/messages?tenant_id=${tenantId}&limit=${limit}&offset=${offset}`,
    );
  },

  /** Send a message */
  sendMessage: (conversationId, content) => {
    const tenantId = getTenantId();
    const keycloakId = localStorage.getItem(STORAGE.KEYCLOAK_ID);
    const user = JSON.parse(localStorage.getItem(STORAGE.USER) || "{}");
    const displayName =
      `${user.first_name || ""} ${user.last_name || ""}`.trim() || "Customer";
    if (!keycloakId) return Promise.reject(new Error("Not authenticated"));
    const qs = new URLSearchParams({
      tenant_id: tenantId,
      sender_keycloak_id: keycloakId,
      sender_name: displayName,
      sender_type: "customer",
    });
    return request(`/messaging/messages?${qs}`, {
      method: "POST",
      body: JSON.stringify({ conversation_id: conversationId, content }),
    });
  },

  /** Mark a conversation as read */
  markAsRead: (conversationId) => {
    const tenantId = getTenantId();
    const keycloakId = localStorage.getItem(STORAGE.KEYCLOAK_ID);
    if (!keycloakId) return Promise.reject(new Error("Not authenticated"));
    const qs = new URLSearchParams({
      tenant_id: tenantId,
      keycloak_id: keycloakId,
      user_type: "customer",
    });
    return request(
      `/messaging/conversations/${conversationId}/mark-read?${qs}`,
      { method: "POST" },
    );
  },

  /** WebSocket for real-time messages */
  connectWebSocket: (onMessage) => {
    const keycloakId = localStorage.getItem(STORAGE.KEYCLOAK_ID);
    if (!keycloakId) throw new Error("Not authenticated");
    const wsUrl = AGENT_BANKING_BASE.replace("https://", "wss://").replace(
      "http://",
      "ws://",
    );
    const ws = new WebSocket(`${wsUrl}/messaging/ws/${keycloakId}`);
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (onMessage) onMessage(data);
      } catch {
        /* ignore non-JSON frames (e.g. pongs) */
      }
    };
    ws.onerror = (err) => console.error("WebSocket error:", err);
    const heartbeat = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) ws.send("ping");
    }, 30000);
    ws.onclose = () => clearInterval(heartbeat);
    return ws;
  },
};

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

// ─── Storefront Advertising ────────────────────────────────────────────────
// Routes to: AGENT_BANKING_BASE  (/storefront-advertising/*)
export const storefrontAdvertisingApi = {
  /** Get all active ads (customer view) */
  getActiveAds: () =>
    request("/storefront/storefront/ads/active", {
      headers: authHeaders(),
    }),

  /** Get ads by target audience filter */
  getAdsByAudience: (targetAudience) =>
    request(`/storefront/storefront/ads/audience/${targetAudience}`, {
      headers: authHeaders(),
    }),

  /** Get ads for a specific merchant */
  getMerchantAds: (merchantId) =>
    request(`/storefront/storefront/ads/merchant/${merchantId}`, {
      headers: authHeaders(),
    }),

  /** Record ad impression (analytics) */
  recordImpression: (adId) =>
    request(`/storefront/storefront/ads/${adId}/impression`, {
      method: "POST",
      headers: authHeaders(),
    }),

  /** Record ad click (analytics) */
  recordClick: (adId) =>
    request(`/storefront/storefront/ads/${adId}/click`, {
      method: "POST",
      headers: authHeaders(),
    }),
};
