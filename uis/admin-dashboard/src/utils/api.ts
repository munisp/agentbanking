/**
 * Central API client for the 54agent admin dashboard.
 * Routes requests to appropriate API gateways based on service type.
 *
 * Core Banking Services (https://54agent.upi.dev):
 *   /admin/*             → admin-service
 *   /auth/*              → auth-service
 *   /orchestrator/*      → orchestrator
 *   /user/*              → user-service
 *   /account/*           → account-service (transfers, balances)
 *   /dispute/*           → dispute-service
 *   /tenant-management/* → tenant-management
 *
 * Agency Banking Services (https://54agent.upi.dev):
 *   /agent/*             → agent-service
 *   /inventory/*         → inventory-service
 *   /pos-terminal/*      → pos-terminal-management
 *   /network-operations/* → network-operations
 *   /commission/*      → commission-settlement
 *   /float/*           → float-management
 *   /compliance-kyc/*  → compliance-kyc
 *   /mdm/*             → mdm-service (mobile device management)
 *
 * Creation flows go through the orchestrator (Temporal workflows).
 * Listing / actions go directly to the respective microservice.
 */

import { getTenantHeaders } from "../services/tenant/getTenantHeaders";
import { tenantService } from "../services/tenant/tenantService";

const CORE_BANKING_BASE =
  import.meta.env.VITE_API_URL || "https://54agent.upi.dev";
const AGENT_BANKING_BASE =
  import.meta.env.VITE_AGENT_API_URL || "https://54agent.upi.dev";
const REALTIME_SERVICE_BASE =
  import.meta.env.VITE_REALTIME_API_URL || "https://54agent.upi.dev";

/**
 * Map service prefixes to their correct API gateway
 */
const SERVICE_BASE_URLS: Record<string, string> = {
  // Core Banking Services
  "/admin": AGENT_BANKING_BASE,//
  "/auth": AGENT_BANKING_BASE,//
  "/orchestrator": AGENT_BANKING_BASE,//
  "/user": AGENT_BANKING_BASE,//
  "/account": AGENT_BANKING_BASE,//
  "/dispute": AGENT_BANKING_BASE,//
  "/tenant-management": AGENT_BANKING_BASE,//
  "/ledger": AGENT_BANKING_BASE,//
  "/payment": AGENT_BANKING_BASE,//
  "/loan": AGENT_BANKING_BASE,//
  "/loyalty": AGENT_BANKING_BASE,//
  "/realtime": AGENT_BANKING_BASE,

  // Agency Banking Services
  "/agent": AGENT_BANKING_BASE,
  "/inventory": AGENT_BANKING_BASE,
  "/pos-terminals": AGENT_BANKING_BASE,
  "/network-operations": AGENT_BANKING_BASE,
  "/settlement": AGENT_BANKING_BASE,
  "/commission": AGENT_BANKING_BASE,
  "/float": AGENT_BANKING_BASE,
  "/compliance-kyc": AGENT_BANKING_BASE,
  "/compliance": AGENT_BANKING_BASE,
  "/pos-hardware": AGENT_BANKING_BASE,
  "/pos-integration": AGENT_BANKING_BASE,
  "/pos-management": AGENT_BANKING_BASE,
  "/mdm": AGENT_BANKING_BASE,
  "/erp": AGENT_BANKING_BASE,
  "/fraud-engine": AGENT_BANKING_BASE,
  "/vat": AGENT_BANKING_BASE,
  "/stablecoin": AGENT_BANKING_BASE,
  "/storefront": AGENT_BANKING_BASE,
  "/security-monitoring": AGENT_BANKING_BASE,
};

/**
 * Resolve the correct base URL for a given API path
 */
function getBaseUrlForPath(path: string): string {
  // Find the first matching service prefix
  for (const [prefix, baseUrl] of Object.entries(SERVICE_BASE_URLS)) {
    if (path.startsWith(prefix)) {
      return baseUrl;
    }
  }
  // Default to core banking for unknown services
  return CORE_BANKING_BASE;
}

// -------------------------------------------------------------------
// Role / access level constants (mirrors backend model definitions)
// -------------------------------------------------------------------

/** Numeric access level → human label (from ROLE_SYSTEM_QUICK_REF.py) */
export const ACCESS_LEVEL_OPTIONS: {
  value: string;
  label: string;
  desc: string;
}[] = [
  { value: "0", label: "Analyst", desc: "platform:analyst" },
  { value: "1", label: "Customer Support", desc: "platform:operations" },
  { value: "2", label: "Operations Officer", desc: "platform:operations" },
  { value: "3", label: "Finance Admin", desc: "platform:finance" },
  {
    value: "4",
    label: "Compliance Officer",
    desc: "platform:compliance, bank:compliance_officer",
  },
  { value: "5", label: "Technical Admin", desc: "platform:technical" },
  { value: "6", label: "Bank Admin", desc: "bank:admin" },
  { value: "7", label: "Super Admin", desc: "platform:super, bank:admin" },
  { value: "8", label: "Auditor", desc: "platform:auditor, bank:auditor" },
];

/** v2.perm tenant roles (bank/tenant-level staff) */
export const TENANT_ROLES: string[] = [
  "super_admin",
  "branch_manager",
  "operations_manager",
  "risk_manager",
  "internal_auditor",
  "it_admin",
  "relationship_manager",
  "trade_finance_admin",
  "vault_manager",
  "treasury_manager",
  "loan_officer",
  "compliance_officer",
  "support_agent",
];

/** Agent roles */
export const AGENT_ROLES: string[] = ["agent", "super_agent", "aggregator"];

// -------------------------------------------------------------------
// Header helpers
// -------------------------------------------------------------------

function getTenantHeadersFromStorage(): Record<string, string> {
  const tenantConfig = tenantService.getTenantConfig();
  if (!tenantConfig) {
    if (import.meta.env.DEV) {
      console.warn(
        "getTenantHeadersFromStorage: tenant_config not found in localStorage",
      );
    }
    return {};
  }
  return getTenantHeaders(tenantConfig);
}

function tenantHeaders(): Record<string, string> {
  return {
    "Content-Type": "application/json",
    ...getTenantHeadersFromStorage(),
  };
}

function fullHeaders(): Record<string, string> {
  const token = localStorage.getItem("auth_token");
  const tenantHeaders = getTenantHeadersFromStorage();

  // If x-keycloak-id is not in tenant headers, get it from localStorage
  if (!tenantHeaders["x-keycloak-id"]) {
    const keycloakId = localStorage.getItem("keycloakId");
    if (keycloakId) {
      tenantHeaders["x-keycloak-id"] = keycloakId;
    } else if (token && token !== "authenticated" && token !== "demo-token") {
      // Extract keycloak user ID from JWT sub claim as last resort
      try {
        const payload = JSON.parse(
          atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")),
        );
        if (payload.sub) {
          tenantHeaders["x-keycloak-id"] = payload.sub;
          localStorage.setItem("keycloakId", payload.sub);
        }
      } catch {
        // non-JWT token, skip
      }
    }
  }

  return {
    "Content-Type": "application/json",
    ...tenantHeaders,
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

// -------------------------------------------------------------------
// Auth API
// -------------------------------------------------------------------

export const authApi = {
  health: () => fetch(`${CORE_BANKING_BASE}/auth/health`).then((r) => r.json()),

  login: (email: string, password: string, tenantId?: string) => {
    // Get headers from tenant config
    const tenantConfig = tenantService.getTenantConfig();
    let headers: Record<string, string> = {
      "Content-Type": "application/json",
    };

    if (tenantConfig) {
      headers = { ...headers, ...getTenantHeaders(tenantConfig) };
    } else if (import.meta.env.DEV) {
      console.warn("Login attempted without tenant config loaded");
    }

    return request<{
      access_token: string;
      refresh_token: string;
      expires_in: number;
      keycloak_id?: string;
      user?: AdminRecord;
    }>("/auth/auth/login", {
      method: "POST",
      headers,
      body: JSON.stringify({ email, password }),
    });
  },

  refresh: (refreshToken: string) =>
    request<{ access_token: string; expires_in: number }>(
      "/auth/token/refresh",
      {
        method: "POST",
        headers: fullHeaders(),
        body: JSON.stringify({ refresh_token: refreshToken }),
      },
    ),

  logout: (refreshToken: string) =>
    request("/auth/auth/logout", {
      method: "POST",
      headers: fullHeaders(),
      body: JSON.stringify({ refresh_token: refreshToken }),
    }),
};

// -------------------------------------------------------------------
// Generic request wrapper
// -------------------------------------------------------------------

async function request<T = unknown>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const baseUrl = getBaseUrlForPath(path);
  const res = await fetch(`${baseUrl}${path}`, options);
  const json = await res.json();
  if (!res.ok) {
    throw new Error(
      json?.detail ?? json?.message ?? `${res.status} ${res.statusText}`,
    );
  }
  return json as T;
}

async function settlementServiceRequest<T = unknown>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  try {
    return await request<T>(`/commission/api/v1${path}`, options);
  } catch {
    return request<T>(`/api/v1${path}`, options);
  }
}

// -------------------------------------------------------------------
// API surface
// -------------------------------------------------------------------

export const api = {
  // ── Admins ──────────────────────────────────────────────────────
  /** List all admins for the current tenant. */
  getAdmins: () =>
    request<{ admins: AdminRecord[] }>("/admin/admin", {
      headers: fullHeaders(),
    }),

  /** Create an admin via Temporal workflow in the orchestrator. */
  createAdmin: (data: CreateAdminPayload) =>
    request("/orchestrator/admin", {
      method: "POST",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  /** Suspend an admin by their DB id. */
  suspendAdmin: (id: string) =>
    request(`/admin/admin/${id}/suspend`, {
      method: "PATCH",
      headers: fullHeaders(),
    }),

  /** Unsuspend an admin by their DB id. */
  unsuspendAdmin: (id: string) =>
    request(`/admin/admin/${id}/unsuspend`, {
      method: "PATCH",
      headers: fullHeaders(),
    }),

  // ── Agents ──────────────────────────────────────────────────────
  /** List all agents for the current tenant. */
  getAgents: () =>
    request<{ message: string; agents: AgentRecord[] }>("/agent/agent/tenant", {
      headers: fullHeaders(),
    }),

  /** Create an agent via Temporal workflow. */
  createAgent: (data: CreateAgentPayload) =>
    request("/orchestrator/agent", {
      method: "POST",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  /** Approve a pending agent (by keycloak_id). */
  approveAgent: (keycloakId: string) =>
    request(`/agent/agent/${keycloakId}/approve`, {
      method: "POST",
      headers: fullHeaders(),
    }),

  /** Suspend an agent (by keycloak_id). */
  suspendAgent: (keycloakId: string) =>
    request(`/agent/agent/${keycloakId}/suspend`, {
      method: "POST",
      headers: fullHeaders(),
    }),

  // ── Customers ───────────────────────────────────────────────────
  /** List all customers (users) for the current tenant. */
  getCustomers: () =>
    request<{ users: CustomerRecord[] }>("/user/user/tenant", {
      headers: fullHeaders(),
    }),

  /** Create a customer via Temporal workflow. */
  createCustomer: (data: CreateCustomerPayload) =>
    request("/orchestrator/customer", {
      method: "POST",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  // ── Accounts ────────────────────────────────────────────────────

  /** Get all accounts for the current tenant. */
  getAllAccounts: () => {
    const role =
      localStorage.getItem("platform_role") ||
      (() => {
        try {
          const u = JSON.parse(localStorage.getItem("admin_data") || localStorage.getItem("auth_user") || "{}");
          return u.access_level || u.user_role || u.role || "bank_admin";
        } catch { return "bank_admin"; }
      })();
    return request<any[]>("/chart-of-accounts/api/v1/accounts?include_balance=true", {
      headers: { ...fullHeaders(), "X-User-Role": role },
    });
  },

  // ── Inventory ───────────────────────────────────────────────────

  /** Get all stores in the platform (admin view) */
  getAllStores: () =>
    request<StoreRecord[]>("/inventory/stores", {
      headers: fullHeaders(),
    }),

  /** Delete a store */
  deleteStore: (storeId: number | string) =>
    request<{ message: string }>(`/inventory/stores/${storeId}`, {
      method: "DELETE",
      headers: fullHeaders(),
    }),

  /** Update a store */
  updateStore: (
    storeId: number | string,
    data: { name?: string; description?: string },
  ) =>
    request<StoreRecord>(`/inventory/stores/${storeId}`, {
      method: "PUT",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  /** Get all inventory items for a store with optional filters */
  getInventoryItems: (
    storeId: number | string,
    filters?: {
      search?: string;
      category?: string;
      status?: string;
    },
  ) => {
    const params = new URLSearchParams();
    if (filters?.search) params.append("search", filters.search);
    if (filters?.category) params.append("category", filters.category);
    if (filters?.status) params.append("status", filters.status);
    const query = params.toString() ? `?${params.toString()}` : "";
    return request<InventoryItem[]>(
      `/inventory/stores/${storeId}/items${query}`,
      {
        headers: fullHeaders(),
      },
    );
  },

  /** Get a specific inventory item for a store */
  getInventoryItem: (storeId: number | string, id: number) =>
    request<InventoryItem>(`/inventory/stores/${storeId}/items/${id}`, {
      headers: fullHeaders(),
    }),

  /** Create a new inventory item for a store */
  createInventoryItem: (
    storeId: number | string,
    data: CreateInventoryItemPayload,
  ) =>
    request<InventoryItem>(`/inventory/stores/${storeId}/items`, {
      method: "POST",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  /** Update an inventory item for a store */
  updateInventoryItem: (
    storeId: number | string,
    id: number,
    data: UpdateInventoryItemPayload,
  ) =>
    request<InventoryItem>(`/inventory/stores/${storeId}/items/${id}`, {
      method: "PUT",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  /** Delete an inventory item for a store */
  deleteInventoryItem: (storeId: number | string, id: number) =>
    request(`/inventory/stores/${storeId}/items/${id}`, {
      method: "DELETE",
      headers: fullHeaders(),
    }),

  /** Get stock alerts (low stock, critical, out of stock) */
  getStockAlerts: () =>
    request<InventoryItem[]>("/inventory/inventory/alerts", {
      headers: fullHeaders(),
    }),

  /** Create a sale and update inventory */
  createSale: (data: CreateSalePayload) =>
    request<SaleRecord>("/inventory/inventory/sales", {
      method: "POST",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  /** Get sales history */
  getSalesHistory: (limit?: number) => {
    const query = limit ? `?limit=${limit}` : "";
    return request<SaleRecord[]>(`/inventory/inventory/sales${query}`, {
      headers: fullHeaders(),
    });
  },

  /** Get inventory metrics */
  getInventoryMetrics: () =>
    request<InventoryMetrics>("/inventory/inventory/metrics", {
      headers: fullHeaders(),
    }),

  // ── POS Terminal Management ─────────────────────────────────────
  /** Get all POS terminals */
  getPOSTerminals: () =>
    request<POSTerminal[]>("/pos-terminals/terminals", {
      headers: fullHeaders(),
    }),

  /** Get a specific POS terminal */
  getPOSTerminal: (id: string) =>
    request<POSTerminal>(`/pos-terminals/terminals/${id}`, {
      headers: fullHeaders(),
    }),

  /** Create a new POS terminal */
  createPOSTerminal: (data: CreatePOSTerminalPayload) =>
    request<POSTerminal>("/pos-terminals/terminals", {
      method: "POST",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  /** Update a POS terminal */
  updatePOSTerminal: (id: string, data: UpdatePOSTerminalPayload) =>
    request<POSTerminal>(`/pos-terminals/terminals/${id}`, {
      method: "PUT",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  /** Delete a POS terminal */
  deletePOSTerminal: (id: string) =>
    request(`/pos-terminals/terminals/${id}`, {
      method: "DELETE",
      headers: fullHeaders(),
    }),

  /** Get terminals by status */
  getPOSTerminalsByStatus: (status: string) =>
    request<POSTerminal[]>(`/pos-terminals/terminals/status/${status}`, {
      headers: fullHeaders(),
    }),

  /** Search terminals */
  searchPOSTerminals: (query: string) => {
    const params = new URLSearchParams({ q: query });
    return request<POSTerminal[]>(`/pos-terminals/terminals/search?${params}`, {
      headers: fullHeaders(),
    });
  },

  // ── POS Hardware Inventory ─────────────────────────────────────
  /** Get POS hardware devices (inventory) */
  getPOSHardwareDevices: (
    filters: {
      page?: number;
      limit?: number;
      status?: string;
      type?: string;
      agent_id?: string;
      manufacturer?: string;
    } = {},
  ) => {
    const params = new URLSearchParams();
    if (filters.page) params.append("page", String(filters.page));
    if (filters.limit) params.append("limit", String(filters.limit));
    if (filters.status) params.append("status", filters.status);
    if (filters.type) params.append("type", filters.type);
    if (filters.agent_id) params.append("agent_id", filters.agent_id);
    if (filters.manufacturer)
      params.append("manufacturer", filters.manufacturer);
    const query = params.toString() ? `?${params.toString()}` : "";
    return request<POSHardwareListResponse>(
      `/pos-hardware/api/v1/pos-devices${query}`,
      {
        headers: fullHeaders(),
      },
    );
  },

  /** Register a new POS hardware device */
  registerPOSHardwareDevice: (data: CreatePOSHardwareDevicePayload) =>
    request("/pos-hardware/api/v1/pos-devices", {
      method: "POST",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  /** Update POS hardware device status */
  updatePOSHardwareDeviceStatus: (
    deviceId: string,
    data: { status: string; reason?: string; updated_by?: string },
  ) =>
    request(`/pos-hardware/api/v1/pos-devices/${deviceId}/status`, {
      method: "PATCH",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  /** Get POS hardware device health */
  getPOSHardwareDeviceHealth: (deviceId: string) =>
    request(`/pos-hardware/api/v1/pos-devices/${deviceId}/health`, {
      headers: fullHeaders(),
    }),

  // ── Device Catalog ──────────────────────────────────────────────
  getCatalogManufacturers: () =>
    request<{ manufacturers: CatalogManufacturer[]; count: number }>(
      "/pos-hardware/api/v1/catalog/manufacturers",
      { headers: fullHeaders() },
    ),

  createCatalogManufacturer: (data: { name: string; slug: string; logo_url?: string; website?: string }) =>
    request<CatalogManufacturer>("/pos-hardware/api/v1/catalog/manufacturers", {
      method: "POST",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  deleteCatalogManufacturer: (id: string) =>
    request(`/pos-hardware/api/v1/catalog/manufacturers/${id}`, {
      method: "DELETE",
      headers: fullHeaders(),
    }),

  getCatalogModels: (manufacturerId?: string) => {
    const qs = manufacturerId ? `?manufacturer_id=${manufacturerId}` : "";
    return request<{ models: CatalogModel[]; count: number }>(
      `/pos-hardware/api/v1/catalog/models${qs}`,
      { headers: fullHeaders() },
    );
  },

  createCatalogModel: (data: {
    manufacturer_id: string;
    name: string;
    slug: string;
    mdm_model_id: string;
    apk_variant: string;
    device_type?: string;
    connectivity?: string;
  }) =>
    request<CatalogModel>("/pos-hardware/api/v1/catalog/models", {
      method: "POST",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  updateCatalogModel: (id: string, data: Partial<CatalogModel>) =>
    request<CatalogModel>(`/pos-hardware/api/v1/catalog/models/${id}`, {
      method: "PUT",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  deleteCatalogModel: (id: string) =>
    request(`/pos-hardware/api/v1/catalog/models/${id}`, {
      method: "DELETE",
      headers: fullHeaders(),
    }),

  // ── Mobile Device Management (MDM) ─────────────────────────────
  /** List all available APK variants */
  getMdmApkVariants: () =>
    request<MdmApkVariantsResponse>("/mdm/api/v1/mdm/apk/variants", {
      headers: fullHeaders(),
    }),

  /** Get details for a single APK variant */
  getMdmApkVariant: (variant: string) =>
    request<MdmApkVariant>(`/mdm/api/v1/mdm/apk/variants/${variant}`, {
      headers: fullHeaders(),
    }),

  /** Get latest APK for a specific model */
  getMdmLatestApkByModel: (modelId: string) =>
    request<MdmLatestApkResponse>(`/mdm/api/v1/mdm/apk/latest/${modelId}`, {
      headers: fullHeaders(),
    }),

  /** Deploy APK to terminals */
  deployMdmApk: (data: MdmDeployApkPayload) =>
    request<MdmApkDeploymentResponse>("/mdm/api/v1/mdm/apk/deploy", {
      method: "POST",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  /** Deploy APK to terminals with uploaded APK file */
  deployMdmApkWithFile: (data: MdmDeployApkPayload, apkFile: File) => {
    const token = localStorage.getItem("auth_token");
    const form = new FormData();
    form.append("terminal_ids", data.terminal_ids.join(","));
    form.append("model_id", data.model_id);
    form.append("apk_variant", data.apk_variant);
    form.append("force", String(Boolean(data.force)));
    if (data.scheduled_at) {
      form.append("scheduled_at", data.scheduled_at);
    }
    form.append("apk_file", apkFile);

    return request<MdmApkDeploymentResponse>("/mdm/api/v1/mdm/apk/deploy", {
      method: "POST",
      headers: {
        ...getTenantHeadersFromStorage(),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: form,
    });
  },

  /** Track APK deployment status */
  getMdmApkDeploymentStatus: (deploymentId: string) =>
    request<MdmApkDeploymentStatus>(
      `/mdm/api/v1/mdm/apk/deploy/${deploymentId}/status`,
      {
        headers: fullHeaders(),
      },
    ),

  /** List firmware updates for a model */
  getMdmFirmwareUpdates: (modelId: string) =>
    request<MdmFirmwareUpdatesResponse>(
      `/mdm/api/v1/mdm/firmware/updates/${modelId}`,
      {
        headers: fullHeaders(),
      },
    ),

  /** Queue firmware deployment for one terminal */
  deployMdmFirmware: (data: MdmDeployFirmwarePayload) =>
    request<MdmFirmwareDeployResponse>("/mdm/api/v1/mdm/firmware/deploy", {
      method: "POST",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  /** Track firmware deployment status */
  getMdmFirmwareDeploymentStatus: (updateId: string) =>
    request<MdmFirmwareDeployStatus>(
      `/mdm/api/v1/mdm/firmware/deploy/${updateId}/status`,
      {
        headers: fullHeaders(),
      },
    ),

  /** Initiate device provisioning */
  provisionMdmDevice: (data: MdmProvisionPayload) =>
    request<MdmProvisionResponse>("/mdm/api/v1/mdm/provision", {
      method: "POST",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  /** Get provisioning/device status */
  getMdmProvisionedDevice: (terminalId: string) =>
    request<MdmDevice>(`/mdm/api/v1/mdm/provision/${terminalId}`, {
      headers: fullHeaders(),
    }),

  /** Mark provisioning as complete */
  completeMdmProvisioning: (
    terminalId: string,
    data: MdmCompleteProvisionPayload,
  ) =>
    request<MdmDeviceStateChangeResponse>(
      `/mdm/api/v1/mdm/provision/${terminalId}/complete`,
      {
        method: "PUT",
        headers: fullHeaders(),
        body: JSON.stringify(data),
      },
    ),

  /** List MDM devices with optional filters */
  getMdmDevices: (
    filters: {
      model_id?: string;
      state?: string;
      agent_id?: string;
    } = {},
  ) => {
    const params = new URLSearchParams();
    if (filters.model_id) params.append("model_id", filters.model_id);
    if (filters.state) params.append("state", filters.state);
    if (filters.agent_id) params.append("agent_id", filters.agent_id);
    const query = params.toString() ? `?${params.toString()}` : "";
    return request<MdmDevicesResponse>(`/mdm/api/v1/mdm/devices${query}`, {
      headers: fullHeaders(),
    });
  },

  /** Get a single MDM device */
  getMdmDevice: (terminalId: string) =>
    request<MdmDeviceDetail>(`/mdm/api/v1/mdm/devices/${terminalId}`, {
      headers: fullHeaders(),
    }),

  /** Update device state (active/suspended/etc) */
  updateMdmDeviceState: (
    terminalId: string,
    data: { state: string; reason?: string },
  ) =>
    request<MdmDeviceStateChangeResponse>(
      `/mdm/api/v1/mdm/devices/${terminalId}/state`,
      {
        method: "PUT",
        headers: fullHeaders(),
        body: JSON.stringify(data),
      },
    ),

  /** Decommission a device */
  decommissionMdmDevice: (terminalId: string) =>
    request<MdmDeviceStateChangeResponse>(
      `/mdm/api/v1/mdm/devices/${terminalId}`,
      {
        method: "DELETE",
        headers: fullHeaders(),
      },
    ),

  /** List available remote command types */
  getMdmCommandTypes: () =>
    request<MdmCommandTypesResponse>("/mdm/api/v1/mdm/commands/types", {
      headers: fullHeaders(),
    }),

  /** Issue a remote command */
  createMdmCommand: (data: MdmCreateCommandPayload) =>
    request<MdmCreateCommandResponse>("/mdm/api/v1/mdm/commands", {
      method: "POST",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  /** Get pending commands for terminal */
  getMdmPendingCommands: (terminalId: string) =>
    request<MdmPendingCommandsResponse>(
      `/mdm/api/v1/mdm/commands/${terminalId}/pending`,
      {
        headers: fullHeaders(),
      },
    ),

  /** Update command execution status */
  updateMdmCommandStatus: (
    commandId: string,
    data: MdmUpdateCommandStatusPayload,
  ) =>
    request<MdmCommandStatusResponse>(
      `/mdm/api/v1/mdm/commands/${commandId}/status`,
      {
        method: "PUT",
        headers: fullHeaders(),
        body: JSON.stringify(data),
      },
    ),

  /** Get model default config */
  getMdmModelConfig: (modelId: string) =>
    request<MdmModelConfigResponse>(`/mdm/api/v1/mdm/config/${modelId}`, {
      headers: fullHeaders(),
    }),

  /** Push config overrides to terminal */
  pushMdmConfig: (terminalId: string, data: Record<string, unknown>) =>
    request<MdmDeviceStateChangeResponse>(
      `/mdm/api/v1/mdm/config/${terminalId}/push`,
      {
        method: "POST",
        headers: fullHeaders(),
        body: JSON.stringify(data),
      },
    ),

  /** Read terminal current config */
  getMdmCurrentConfig: (terminalId: string) =>
    request<MdmConfig>(`/mdm/api/v1/mdm/config/${terminalId}/current`, {
      headers: fullHeaders(),
    }),

  /** Get terminal diagnostics */
  getMdmDiagnostics: (terminalId: string) =>
    request<MdmDiagnostics>(`/mdm/api/v1/mdm/diagnostics/${terminalId}`, {
      headers: fullHeaders(),
    }),

  /** Request fresh diagnostics capture */
  requestMdmDiagnostics: (terminalId: string) =>
    request<MdmDeviceStateChangeResponse>(
      `/mdm/api/v1/mdm/diagnostics/${terminalId}/request`,
      {
        method: "POST",
        headers: fullHeaders(),
      },
    ),

  /** List tamper alerts */
  getMdmTamperAlerts: () =>
    request<MdmTamperAlertsResponse>("/mdm/api/v1/mdm/tamper/alerts", {
      headers: fullHeaders(),
    }),

  /** Run a bulk command by model/agent */
  runMdmBulkCommand: (data: MdmBulkCommandPayload) =>
    request<MdmBulkActionResponse>("/mdm/api/v1/mdm/bulk/command", {
      method: "POST",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  /** Run a bulk APK deploy by model */
  runMdmBulkDeploy: (data: MdmBulkDeployPayload) =>
    request<MdmBulkActionResponse>("/mdm/api/v1/mdm/bulk/deploy", {
      method: "POST",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  /** Track bulk operation */
  getMdmBulkStatus: (batchId: string) =>
    request<MdmBulkStatusResponse>(`/mdm/api/v1/mdm/bulk/status/${batchId}`, {
      headers: fullHeaders(),
    }),

  /** Fleet-wide MDM stats */
  getMdmFleetStats: () =>
    request<MdmFleetStats>("/mdm/api/v1/mdm/stats/fleet", {
      headers: fullHeaders(),
    }),

  /** Stats for a specific model */
  getMdmModelStats: (modelId: string) =>
    request<MdmModelStats>(`/mdm/api/v1/mdm/stats/model/${modelId}`, {
      headers: fullHeaders(),
    }),

  // ── Businesses ──────────────────────────────────────────────────
  /** Get all businesses for the tenant */
  getBusinesses: (verifiedOnly?: boolean, agentKeycloakId?: string) => {
    const params = new URLSearchParams();
    if (verifiedOnly) params.append("verified_only", "true");
    if (agentKeycloakId) params.append("agent_keycloak_id", agentKeycloakId);
    const query = params.toString() ? `?${params.toString()}` : "";
    return request<AgentBusiness[]>(`/agent/agent/businesses/tenant${query}`, {
      headers: fullHeaders(),
    });
  },

  /** Get a specific business */
  getBusiness: (businessId: string) =>
    request<AgentBusiness>(`/agent/agent/businesses/${businessId}`, {
      headers: fullHeaders(),
    }),

  /** Get businesses for a specific agent */
  getAgentBusinesses: (agentKeycloakId: string) =>
    request<AgentBusiness[]>(
      `/agent/agent/businesses/agent/${agentKeycloakId}`,
      {
        headers: fullHeaders(),
      },
    ),

  /** Link a business to an agent */
  linkBusinessToAgent: (data: {
    agent_keycloak_id: string;
    business_id: string;
  }) =>
    request("/agent/businesses/link-agent", {
      method: "POST",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  /** Unlink a business from an agent */
  unlinkBusiness: (businessId: string) =>
    request(`/agent/agent/businesses/unlink/${businessId}`, {
      method: "DELETE",
      headers: fullHeaders(),
    }),

  /** Link a store to a business */
  linkStoreToBusiness: (storeId: number, businessId: string) =>
    request(
      `/inventory/stores/${storeId}/link-business?business_id=${businessId}`,
      {
        method: "PUT",
        headers: fullHeaders(),
      },
    ),

  /** Get stores for a business */
  getBusinessStores: (businessId: string) =>
    request<StoreRecord[]>(`/inventory/stores/business/${businessId}`, {
      headers: fullHeaders(),
    }),

  /** Link a POS terminal to a business */
  linkPOSTerminalToBusiness: (terminalId: string, businessId: string) =>
    request(`/pos-terminals/terminals/${terminalId}/link-business`, {
      method: "PUT",
      headers: fullHeaders(),
      body: JSON.stringify({ business_id: businessId }),
    }),

  /** Get POS terminals for a business */
  getBusinessPOSTerminals: (businessId: string) =>
    request<POSTerminal[]>(`/pos-terminals/terminals/business/${businessId}`, {
      headers: fullHeaders(),
    }),

  // ── Realtime Notification Service (Geofencing) ─────────────────
  /** Create a geofence for a POS terminal/agent */
  createGeofence: (data: CreateGeofencePayload) =>
    request<Geofence>("/realtime/api/v1/geofence/create", {
      method: "POST",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  /** Get all geofences for an agent */
  getAgentGeofences: (agentId: string) =>
    request<Geofence[]>(`/realtime/api/v1/geofence/list/${agentId}`, {
      headers: fullHeaders(),
    }),

  /** Get geofence details */
  getGeofence: (geofenceId: string) =>
    request<Geofence>(`/realtime/api/v1/geofence/${geofenceId}`, {
      headers: fullHeaders(),
    }),

  /** Update a geofence */
  updateGeofence: (geofenceId: string, data: Partial<CreateGeofencePayload>) =>
    request<Geofence>(`/realtime/api/v1/geofence/${geofenceId}`, {
      method: "PUT",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  /** Delete a geofence */
  deleteGeofence: (geofenceId: string) =>
    request(`/realtime/api/v1/geofence/${geofenceId}`, {
      method: "DELETE",
      headers: fullHeaders(),
    }),

  /** Get location history for a device */
  getDeviceLocationHistory: (
    deviceId: string,
    params?: { hours?: number; limit?: number },
  ) => {
    const queryParams = new URLSearchParams();
    if (params?.hours) queryParams.append("hours", String(params.hours));
    if (params?.limit) queryParams.append("limit", String(params.limit));
    const query = queryParams.toString() ? `?${queryParams.toString()}` : "";
    return request<LocationHistory[]>(
      `/realtime/api/v1/location/history/${deviceId}${query}`,
      {
        headers: fullHeaders(),
      },
    );
  },

  /** Get active geofence violations (admin) */
  // Removed duplicate getActiveViolations

  /** Get all geofence violations with filters (admin) */
  // Removed duplicate getAllViolations

  /** Mark violation as resolved */
  // Removed duplicate resolveViolation

  // ── Admin Geofence Violation Monitoring ───────────────────────────
  /** Get active (unresolved) geofence violations */
  getActiveViolations: (params?: {
    tenantId?: string;
    agentId?: string;
    hours?: number;
    limit?: number;
  }) => {
    const queryParams = new URLSearchParams();
    if (params?.tenantId) queryParams.append("tenant_id", params.tenantId);
    if (params?.agentId) queryParams.append("agent_id", params.agentId);
    if (params?.hours) queryParams.append("hours", String(params.hours));
    if (params?.limit) queryParams.append("limit", String(params.limit));
    const query = queryParams.toString() ? `?${queryParams.toString()}` : "";
    return request<ViolationsResponse>(
      `/realtime/api/v1/admin/violations/active${query}`,
      {
        headers: fullHeaders(),
      },
    );
  },

  /** Get all violations with filters */
  getAllViolations: (params?: {
    tenantId?: string;
    agentId?: string;
    deviceId?: string;
    days?: number;
    resolved?: boolean;
    limit?: number;
  }) => {
    const queryParams = new URLSearchParams();
    if (params?.tenantId) queryParams.append("tenant_id", params.tenantId);
    if (params?.agentId) queryParams.append("agent_id", params.agentId);
    if (params?.deviceId) queryParams.append("device_id", params.deviceId);
    if (params?.days) queryParams.append("days", String(params.days));
    if (params?.resolved !== undefined)
      queryParams.append("resolved", String(params.resolved));
    if (params?.limit) queryParams.append("limit", String(params.limit));
    const query = queryParams.toString() ? `?${queryParams.toString()}` : "";
    return request<ViolationsResponse>(
      `/realtime/api/v1/admin/violations/all${query}`,
      {
        headers: fullHeaders(),
      },
    );
  },

  /** Resolve a geofence violation */
  resolveViolation: (violationId: string, notes?: string) =>
    request<{ status: string; violation_id: string; resolved_at: string }>(
      `/realtime/api/v1/admin/violations/${violationId}/resolve`,
      {
        method: "PUT",
        headers: fullHeaders(),
        body: notes ? JSON.stringify({ notes }) : undefined,
      },
    ),

  /** Get violation statistics */
  getViolationStats: (params?: { tenantId?: string; days?: number }) => {
    const queryParams = new URLSearchParams();
    if (params?.tenantId) queryParams.append("tenant_id", params.tenantId);
    if (params?.days) queryParams.append("days", String(params.days));
    const query = queryParams.toString() ? `?${queryParams.toString()}` : "";
    return request<ViolationStats>(
      `/realtime/api/v1/admin/violations/stats${query}`,
      {
        headers: fullHeaders(),
      },
    );
  },

  // ── POS Requests (Agent Ordering) ──────────────────────────────
  /** Get all POS requests (admin view) */
  getAllPOSRequests: (status?: string, agentId?: string) => {
    const params = new URLSearchParams();
    if (status) params.append("status", status);
    if (agentId) params.append("agent_id", agentId);
    const query = params.toString() ? `?${params.toString()}` : "";
    return request<POSRequestRecord[]>(
      `/agent/agent/pos-requests/admin/all${query}`,
      {
        headers: fullHeaders(),
      },
    );
  },

  /** Get POS request statistics */
  getPOSRequestStats: () =>
    request<POSRequestStats>("/agent/agent/pos-requests/admin/stats", {
      headers: fullHeaders(),
    }),

  /** Review (approve/reject) a POS request */
  reviewPOSRequest: (requestId: string, data: POSRequestReview) =>
    request<POSRequestRecord>(`/agent/agent/pos-requests/${requestId}/review`, {
      method: "POST",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  /** Assign terminal to approved POS request */
  assignTerminalToPOSRequest: (requestId: string, data: POSRequestAssign) =>
    request<POSRequestRecord>(`/agent/agent/pos-requests/${requestId}/assign`, {
      method: "POST",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  // ── Disputes (Core Banking Service) ────────────────────────────
  /** Get all disputes for the current user */
  getDisputes: () =>
    request<Dispute[]>(`/dispute/api/v1/disputes`, {
      headers: fullHeaders(),
    }),

  /** Get all disputes for tenant (admin) */
  getTenantDisputes: () =>
    request<Dispute[]>(`/dispute/api/v1/dispute-resolution`, {
      headers: fullHeaders(),
    }),

  /** Get a specific dispute */
  getDispute: (disputeId: string) =>
    request<Dispute>(`/dispute/api/v1/disputes/${disputeId}`, {
      headers: fullHeaders(),
    }),

  /** Create a new dispute */
  createDispute: (data: {
    transaction_id: string;
    dispute_type: string;
    description: string;
  }) =>
    request("/dispute/api/v1/disputes", {
      method: "POST",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  /** Resolve a dispute (admin only) */
  resolveDispute: (disputeId: string, resolution: string) =>
    request(`/dispute/api/v1/administration/disputes/${disputeId}/resolve`, {
      method: "PUT",
      headers: fullHeaders(),
      body: JSON.stringify({ resolution }),
    }),

  /** @deprecated Legacy endpoint */
  getDisputeMessages: (disputeId: number) =>
    request<DisputeMessage[]>(`/dispute/disputes/${disputeId}/messages`, {
      headers: fullHeaders(),
    }),

  /** @deprecated Legacy endpoint */
  addDisputeMessage: (disputeId: number, data: CreateDisputeMessagePayload) =>
    request<DisputeMessage>(`/dispute/disputes/${disputeId}/messages`, {
      method: "POST",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  /** @deprecated Legacy endpoint */
  getDisputeStats: () =>
    request<DisputeStats>("/dispute/disputes/stats", {
      headers: fullHeaders(),
    }),

  // ── Settlement Reconciliation ───────────────────────────────────
  getSettlementReconciliations: (status?: string) => {
    const q = status ? `?status=${status}` : "";
    return request(`/commission/api/v1/settlement-reconciliation${q}`, { headers: fullHeaders() });
  },

  reconcileSettlementDate: (date: string) =>
    request("/commission/api/v1/settlement-reconciliation/reconcile", {
      method: "POST",
      headers: fullHeaders(),
      body: JSON.stringify({ date }),
    }),

  resolveSettlementDiscrepancy: (id: string, resolution_notes: string) =>
    request(`/commission/api/v1/settlement-reconciliation/${id}/resolve`, {
      method: "PUT",
      headers: fullHeaders(),
      body: JSON.stringify({ resolution_notes }),
    }),

  // ── Settlement Batch Processor ─────────────────────────────────
  listSettlementBatches: (params?: Record<string, string>) => {
    const q = params ? `?${new URLSearchParams(params)}` : "";
    return request(`/commission/api/v1/settlement-batches${q}`, { headers: fullHeaders() });
  },

  createCommissionSettlementBatch: (data: { date: string }) =>
    request("/commission/api/v1/settlement-batches", {
      method: "POST",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  processCommissionSettlementBatch: (batchId: string) =>
    request(`/commission/api/v1/settlement-batches/${batchId}/process`, {
      method: "POST",
      headers: fullHeaders(),
    }),

  reconcileSettlementBatch: (batchId: string) =>
    request(`/commission/api/v1/settlement-batches/${batchId}/reconcile`, {
      method: "POST",
      headers: fullHeaders(),
    }),

  getSettlementBatchDetails: (batchId: string) =>
    request(`/commission/api/v1/settlement-batches/${batchId}`, { headers: fullHeaders() }),

  // ── Chargeback Management ──────────────────────────────────────
  listChargebacks: (status?: string) => {
    const q = status ? `?status=${status}` : "";
    return request(`/dispute/api/v1/chargebacks${q}`, { headers: fullHeaders() });
  },

  resolveChargeback: (id: string, data: { outcome: string; refund_amount?: number }) =>
    request(`/dispute/api/v1/chargebacks/${id}/resolve`, {
      method: "PUT",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  // ── Dispute Arbitration ────────────────────────────────────────
  listArbitrationCases: (status?: string) => {
    const q = status ? `?status=${status}` : "";
    return request(`/dispute/api/v1/arbitration${q}`, { headers: fullHeaders() });
  },

  resolveArbitration: (id: string, data: { ruling: string; refund_amount?: number; panel_notes: string }) =>
    request(`/dispute/api/v1/arbitration/${id}/ruling`, {
      method: "PUT",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  // ── Dispute Resolution Queue ──────────────────────────────────
  listDisputeResolutionQueue: (params?: { status?: string; dispute_type?: string }) => {
    const query = new URLSearchParams();
    if (params?.status) query.set("status", params.status);
    if (params?.dispute_type) query.set("dispute_type", params.dispute_type);
    const q = query.toString() ? `?${query.toString()}` : "";
    return request(`/dispute/api/v1/dispute-resolution${q}`, {
      headers: fullHeaders(),
    });
  },

  resolveDisputeWithRefund: (
    disputeId: string,
    data: { resolution: string; refund_amount?: number; admin_notes?: string },
  ) =>
    request(`/dispute/api/v1/administration/disputes/${disputeId}/resolve`, {
      method: "PUT",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  // ── Customer Dispute Portal ───────────────────────────────────
  listCustomerPortalDisputes: (status?: string) => {
    const q = status ? `?status=${status}` : "";
    return request(`/dispute/api/v1/customer-dispute-portal${q}`, {
      headers: fullHeaders(),
    });
  },

  createCustomerPortalDispute: (data: {
    transaction_reference: string;
    reason: string;
    evidence?: string;
    customer_email?: string;
  }) =>
    request(`/dispute/api/v1/customer-dispute-portal`, {
      method: "POST",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  // ── Dispute Mediation AI ──────────────────────────────────────
  listMediationRecommendations: (status?: string) => {
    const q = status ? `?status=${status}` : "";
    return request(`/dispute/api/v1/dispute-mediation-ai${q}`, {
      headers: fullHeaders(),
    });
  },

  applyMediationDecision: (
    caseId: string,
    data: {
      recommendation: "full_refund" | "partial_refund" | "deny" | "escalate" | "merchant_credit";
      suggested_amount?: number;
      note?: string;
    },
  ) =>
    request(`/dispute/api/v1/dispute-mediation-ai/${caseId}/decision`, {
      method: "POST",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  // ── Dispute Auto Rules ────────────────────────────────────────
  listDisputeAutoRules: () =>
    request(`/dispute/api/v1/dispute-auto-rules`, {
      headers: fullHeaders(),
    }),

  upsertDisputeAutoRule: (data: {
    id?: string;
    name: string;
    dispute_type: string;
    threshold_amount: number;
    action: "full_refund" | "partial_refund" | "deny" | "escalate" | "merchant_credit";
    active: boolean;
  }) =>
    request(`/dispute/api/v1/dispute-auto-rules`, {
      method: "POST",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  // ── Network Status ──────────────────────────────────────────────
  /** @deprecated Use network operations endpoints below */
  getNetworkStatus: (timeWindow?: number) => {
    const query = timeWindow ? `?time_window=${timeWindow}` : "";
    return request<NetworkStatusResponse>(
      `/network-operations/status${query}`,
      {
        headers: fullHeaders(),
      },
    );
  },

  /** @deprecated Use network operations endpoints below */
  getNetworkTypeStatus: (networkType: string, timeWindow?: number) => {
    const query = timeWindow ? `?time_window=${timeWindow}` : "";
    return request<NetworkStatus>(
      `/network-operations/status/${networkType}${query}`,
      {
        headers: fullHeaders(),
      },
    );
  },

  /** @deprecated Use network operations endpoints below */
  recordTransactionResult: (data: TransactionResultPayload) =>
    request("/network-operations/transaction/result", {
      method: "POST",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  // ── Network Operations ──────────────────────────────────────────
  /**
   * List network transactions with filters and pagination
   */
  listNetworkTransactions: (
    filters: Record<string, string> = {},
    page: number = 1,
    limit: number = 20,
  ) => {
    const params = new URLSearchParams();
    params.append("page", String(page));
    params.append("limit", String(limit));
    Object.keys(filters).forEach((key) => {
      if (filters[key]) params.append(key, filters[key]);
    });
    return request(`/ledger/txn/?${params}`, {
      headers: fullHeaders(),
    });
  },

  /**
   * Get channel success rate predictions
   */
  getNetworkPredictions: (
    filters: {
      type?: string;
      channel?: string;
      medium?: string;
    } = {},
  ) => {
    const params = new URLSearchParams();
    if (filters.type) params.append("type", filters.type);
    if (filters.channel) params.append("channel", filters.channel);
    if (filters.medium) params.append("medium", filters.medium);
    const query = params.toString() ? `?${params.toString()}` : "";

    return request<{
      predictions: Array<{
        name: string;
        type: string;
        channel: string;
        rate: number;
        status: string;
        total_txns: number;
        confidence: string;
      }>;
    }>(`/network-operations/api/v1/predictions${query}`, {
      headers: fullHeaders(),
    });
  },

  /**
   * Get a specific transaction by ID
   */
  getNetworkTransaction: (id: string) =>
    request(`/network-operations/api/v1/transactions/${id}`, {
      headers: fullHeaders(),
    }),

  /**
   * Create a new transaction
   */
  createNetworkTransaction: (data: Record<string, unknown>) =>
    request("/network-operations/api/v1/transactions", {
      method: "POST",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  /**
   * Update transaction status
   */
  updateTransactionStatus: (id: string, data: Record<string, unknown>) =>
    request(`/network-operations/api/v1/transactions/${id}/status`, {
      method: "PATCH",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  /**
   * Create settlement batch
   */
  createSettlementBatch: (data: Record<string, unknown>) =>
    request("/network-operations/api/v1/settlements/batches", {
      method: "POST",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  /**
   * Get settlement batch by ID
   */
  getSettlementBatch: (id: string) =>
    request(`/network-operations/api/v1/settlements/batches/${id}`, {
      headers: fullHeaders(),
    }),

  /**
   * Process settlement batch
   */
  processSettlementBatch: (id: string) =>
    request(`/network-operations/api/v1/settlements/batches/${id}/process`, {
      method: "POST",
      headers: fullHeaders(),
    }),

  /**
   * Get agent cash position
   */
  getAgentCashPosition: (agentId: string, currency: string = "NGN") =>
    request(
      `/network-operations/api/v1/cash-positions/agents/${agentId}?currency=${currency}`,
      {
        headers: fullHeaders(),
      },
    ),

  /**
   * Initialize agent cash position
   */
  initializeAgentCashPosition: (
    agentId: string,
    data: { currency: string; initial_balance: number },
  ) =>
    request(
      `/network-operations/api/v1/cash-positions/agents/${agentId}/initialize`,
      {
        method: "POST",
        headers: fullHeaders(),
        body: JSON.stringify(data),
      },
    ),

  // ── Transfers ───────────────────────────────────────────────────
  /** Initiate a transfer (creates pending transfer) */
  initiateTransfer: (data: InitiateTransferPayload) =>
    request<Transfer>("/account/transfer/initiate", {
      method: "POST",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  /** Get pending transfers for current user */
  getPendingTransfers: () =>
    request<Transfer[]>("/account/transfer/pending", {
      headers: fullHeaders(),
    }),

  /** Accept or decline a transfer */
  transferAction: (transferId: string, data: TransferActionPayload) =>
    request<Transfer>(`/account/transfer/${transferId}/action`, {
      method: "POST",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  /** Check balance with PIN verification */
  checkBalance: (data: BalanceCheckPayload) =>
    request<BalanceResponse>("/account/transfer/balance/check", {
      method: "POST",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  /** Get transfer history */
  getTransferHistory: (limit?: number) => {
    const query = limit ? `?limit=${limit}` : "";
    return request<Transfer[]>(`/account/transfer/history${query}`, {
      headers: fullHeaders(),
    });
  },
};

// -------------------------------------------------------------------
// Commission & Settlement API  (commission-settlement service)
// -------------------------------------------------------------------

export const commissionApi = {
  // ── Commission Rules ────────────────────────────────────────────

  /** List all commission rules (optionally only active ones) */
  listRules: (activeOnly = false) =>
    request<{ rules: CommissionRule[]; total: number }>(
      `/commission/api/v1/commission-rules?active_only=${activeOnly}`,
      { headers: fullHeaders() },
    ),

  /** Get a single commission rule by ID */
  getRule: (id: string) =>
    request<CommissionRule>(`/commission/api/v1/commission-rules/${id}`, {
      headers: fullHeaders(),
    }),

  /** Create a new commission rule */
  createRule: (data: CreateCommissionRulePayload) =>
    request<CommissionRule>("/commission/api/v1/commission-rules", {
      method: "POST",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  /** Update an existing commission rule */
  updateRule: (id: string, data: Partial<CreateCommissionRulePayload>) =>
    request<CommissionRule>(`/commission/api/v1/commission-rules/${id}`, {
      method: "PUT",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  /** Deactivate (soft-delete) a commission rule */
  deleteRule: (id: string) =>
    request<{ message: string }>(`/commission/api/v1/commission-rules/${id}`, {
      method: "DELETE",
      headers: fullHeaders(),
    }),

  // ── Commissions ─────────────────────────────────────────────────

  /** List commissions — optionally filter by agent or date range */
  listCommissions: (
    params: {
      agent_id?: string;
      status?: string;
      start_date?: string;
      end_date?: string;
      page?: number;
      limit?: number;
    } = {},
  ) => {
    const qp = new URLSearchParams({
      page: String(params.page ?? 1),
      limit: String(params.limit ?? 50),
      ...(params.agent_id && { agent_id: params.agent_id }),
      ...(params.status && { status: params.status }),
      ...(params.start_date && { start_date: params.start_date }),
      ...(params.end_date && { end_date: params.end_date }),
    }).toString();
    return request<{
      commissions: CommissionRecord[];
      total: number;
      page: number;
      limit: number;
    }>(`/commission/api/v1/commissions?${qp}`, { headers: fullHeaders() });
  },

  // ── Settlements ──────────────────────────────────────────────────

  /** List all settlements across all agents (admin view) */
  listSettlements: (
    params: {
      agent_id?: string;
      status?: string;
      start_date?: string;
      end_date?: string;
      page?: number;
      limit?: number;
    } = {},
  ) => {
    const qp = new URLSearchParams({
      page: String(params.page ?? 1),
      limit: String(params.limit ?? 50),
      ...(params.agent_id && { agent_id: params.agent_id }),
      ...(params.status && { status: params.status }),
      ...(params.start_date && { start_date: params.start_date }),
      ...(params.end_date && { end_date: params.end_date }),
    }).toString();
    return request<{
      settlements: SettlementRecord[];
      total: number;
      page: number;
      limit: number;
    }>(`/commission/api/v1/settlements?${qp}`, { headers: fullHeaders() });
  },

  /** Process (approve & pay) a pending settlement */
  processSettlement: (id: string) =>
    request<{ message: string }>(
      `/commission/api/v1/settlements/${id}/process`,
      { method: "POST", headers: fullHeaders() },
    ),

  /** Update a settlement status/failure reason */
  updateSettlement: (
    id: string,
    data: { status?: string; failure_reason?: string },
  ) =>
    request<SettlementRecord>(`/commission/api/v1/settlements/${id}`, {
      method: "PUT",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  // ── Agent Balances ───────────────────────────────────────────────

  /** Get commission wallet balance for a specific agent */
  getAgentBalance: (agentId: string) =>
    request<AgentBalanceRecord>(
      `/commission/api/v1/agents/${agentId}/balance`,
      { headers: fullHeaders() },
    ),

  /** List all agent commission balances (admin overview) */
  listAgentBalances: (page = 1, limit = 50) =>
    request<{
      balances: AgentBalanceRecord[];
      total: number;
      page: number;
      limit: number;
    }>(`/commission/api/v1/agents?page=${page}&limit=${limit}`, {
      headers: fullHeaders(),
    }),

  /** Get a single commission record by ID */
  getCommission: (id: string) =>
    request<CommissionRecord>(`/commission/api/v1/commissions/${id}`, {
      headers: fullHeaders(),
    }),

  /** Create a new commission record (typically called by the payment processing pipeline) */
  createCommission: (data: {
    agent_id: string;
    transaction_id: string;
    transaction_ref: string;
    transaction_type: string;
    amount: number;
    rate: number;
    commission_amount: number;
    currency?: string;
    earned_at: string;
    metadata?: Record<string, unknown>;
  }) =>
    request<CommissionRecord>("/commission/api/v1/commissions", {
      method: "POST",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  /** Get a single settlement record by ID */
  getSettlement: (id: string) =>
    request<SettlementRecord>(`/commission/api/v1/settlements/${id}`, {
      headers: fullHeaders(),
    }),

  /** Create a new settlement batch for an agent */
  createSettlement: (data: {
    agent_id: string;
    currency?: string;
    notes?: string;
  }) =>
    request<SettlementRecord>("/commission/api/v1/settlements", {
      method: "POST",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  // ── Settlement Policy & EOD ─────────────────────────────────────

  /** Get platform-wide settlement policy */
  getPolicy: () =>
    request<Record<string, unknown>>("/commission/api/v1/policy", {
      headers: fullHeaders(),
    }),

  /** Update platform-wide settlement policy */
  updatePolicy: (data: Record<string, unknown>) =>
    request<Record<string, unknown>>("/commission/api/v1/policy", {
      method: "PUT",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  /** Run end-of-day settlement batch for all agents */
  runEod: () =>
    request<Record<string, unknown>>("/commission/api/v1/eod/run", {
      method: "POST",
      headers: fullHeaders(),
    }),

  // ── Settlement Service (services/settlement-service) ───────────

  listSettlementServiceRecords: (
    params: {
      status_filter?: SettlementServiceStatus;
      currency_filter?: string;
      skip?: number;
      limit?: number;
    } = {},
  ) => {
    const qp = new URLSearchParams({
      skip: String(params.skip ?? 0),
      limit: String(params.limit ?? 100),
      ...(params.status_filter && { status_filter: params.status_filter }),
      ...(params.currency_filter && { currency_filter: params.currency_filter }),
    }).toString();

    return settlementServiceRequest<SettlementServiceRecord[]>(
      `/settlements?${qp}`,
      { headers: fullHeaders() },
    );
  },

  getSettlementServiceRecord: (id: number) =>
    settlementServiceRequest<SettlementServiceRecord>(`/settlements/${id}`, {
      headers: fullHeaders(),
    }),

  createSettlementServiceRecord: (data: {
    settlement_date: string;
    amount: number;
    currency: string;
    transaction_count?: number;
    external_reference_id?: string;
    status?: SettlementServiceStatus;
  }) =>
    settlementServiceRequest<SettlementServiceRecord>("/settlements", {
      method: "POST",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  updateSettlementServiceRecord: (
    id: number,
    data: {
      status?: SettlementServiceStatus;
      amount?: number;
      transaction_count?: number;
      external_reference_id?: string;
    },
  ) =>
    settlementServiceRequest<SettlementServiceRecord>(`/settlements/${id}`, {
      method: "PUT",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  processSettlementServiceRecord: (id: number) =>
    settlementServiceRequest<SettlementServiceRecord>(`/settlements/${id}/process`, {
      method: "POST",
      headers: fullHeaders(),
    }),

  createSettlementServiceLog: (
    id: number,
    data: {
      level: SettlementServiceLogLevel;
      message: string;
      details?: string;
    },
  ) =>
    settlementServiceRequest<SettlementServiceLog>(`/settlements/${id}/log`, {
      method: "POST",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  // ── Legacy MDM alias ───────────────────────────────────────────
  apkManagement: () =>
    request<MdmApkVariantsResponse>("/mdm/api/v1/mdm/apk/variants", {
      headers: fullHeaders(),
    }),
};

// -------------------------------------------------------------------
// Loyalty API (loyalty-service)
// -------------------------------------------------------------------

export const loyaltyApi = {
  // Monitoring
  health: () => request<LoyaltyHealthResponse>("/loyalty/health"),
  status: () => request<LoyaltyStatusResponse>("/loyalty/api/v1/status"),
  metrics: () => request<LoyaltyMetricsResponse>("/loyalty/api/v1/metrics"),

  // Admin + shared account operations
  createAccount: (userId: string) =>
    request<LoyaltyAccountResponse>("/loyalty/loyalty/accounts", {
      method: "POST",
      headers: fullHeaders(),
      body: JSON.stringify({ user_id: userId }),
    }),

  getAccount: (userId: string) =>
    request<LoyaltyAccountResponse>(`/loyalty/loyalty/accounts/${userId}`, {
      headers: fullHeaders(),
    }),

  listAccounts: (params: { skip?: number; limit?: number } = {}) => {
    const query = new URLSearchParams();
    if (params.skip !== undefined) query.append("skip", String(params.skip));
    if (params.limit !== undefined) query.append("limit", String(params.limit));
    const queryString = query.toString() ? `?${query.toString()}` : "";
    return request<LoyaltyAccountResponse[]>(
      `/loyalty/loyalty/accounts${queryString}`,
      {
        headers: fullHeaders(),
      },
    );
  },

  updateAccount: (
    userId: string,
    data: { tier?: LoyaltyTier; current_points?: number },
  ) =>
    request<LoyaltyAccountResponse>(`/loyalty/loyalty/accounts/${userId}`, {
      method: "PUT",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  deleteAccount: (userId: string) =>
    request<null>(`/loyalty/loyalty/accounts/${userId}`, {
      method: "DELETE",
      headers: fullHeaders(),
    }),

  getActivities: (
    userId: string,
    params: {
      skip?: number;
      limit?: number;
      activity_type?: LoyaltyActivityType;
    } = {},
  ) => {
    const query = new URLSearchParams();
    if (params.skip !== undefined) query.append("skip", String(params.skip));
    if (params.limit !== undefined) query.append("limit", String(params.limit));
    if (params.activity_type)
      query.append("activity_type", params.activity_type);
    const queryString = query.toString() ? `?${query.toString()}` : "";
    return request<LoyaltyActivityResponse[]>(
      `/loyalty/loyalty/accounts/${userId}/activities${queryString}`,
      {
        headers: fullHeaders(),
      },
    );
  },
};

// -------------------------------------------------------------------
// Service Integrations API
// -------------------------------------------------------------------

export const serviceIntegrationsApi = {
  erpnext: {
    health: () => request<{ status: string; service: string }>("/erp/health"),
    setupAgent: (agentId: string, params: { agent_name: string; phone: string; email?: string; vat_number?: string }) => {
      const q = new URLSearchParams({ agent_name: params.agent_name, phone: params.phone, ...(params.email && { email: params.email }), ...(params.vat_number && { vat_number: params.vat_number }) });
      return request<unknown>(`/erp/erp/agents/${agentId}/setup?${q}`, { method: "POST", headers: fullHeaders() });
    },
    getSyncStatus: (agentId: string, limit = 50) =>
      request<unknown[]>(`/erp/erp/sync/${agentId}/status?limit=${limit}`, {
        headers: fullHeaders(),
      }),
    syncTransaction: (data: { transaction_id: string; agent_id: string; amount: number; transaction_type: string; [key: string]: unknown }) =>
      request<unknown>("/erp/erp/sync/transaction", {
        method: "POST",
        headers: fullHeaders(),
        body: JSON.stringify(data),
      }),
    retryFailedSyncs: (agentId: string) =>
      request<unknown>(`/erp/erp/sync/${agentId}/retry-failed`, {
        method: "POST",
        headers: fullHeaders(),
      }),
    getPerformanceReport: (agentId: string, fromDate: string, toDate: string) =>
      request<unknown>(
        `/erp/erp/reports/${agentId}/performance?from_date=${encodeURIComponent(fromDate)}&to_date=${encodeURIComponent(toDate)}`,
        { headers: fullHeaders() },
      ),
    getFinancialSummary: (data: { agent_id: string; from_date: string; to_date: string }) =>
      request<unknown>("/erp/erp/reports/financial-summary", {
        method: "POST",
        headers: fullHeaders(),
        body: JSON.stringify(data),
      }),
    getProfitLoss: (agentId: string, fromDate: string, toDate: string) =>
      request<unknown>(`/erp/erp/reports/${agentId}/profit-loss?from_date=${encodeURIComponent(fromDate)}&to_date=${encodeURIComponent(toDate)}`, {
        headers: fullHeaders(),
      }),
    getBalanceSheet: (agentId: string, asOfDate: string) =>
      request<unknown>(`/erp/erp/reports/${agentId}/balance-sheet?as_of_date=${encodeURIComponent(asOfDate)}`, {
        headers: fullHeaders(),
      }),
    getCashFlow: (agentId: string, fromDate: string, toDate: string) =>
      request<unknown>(`/erp/erp/reports/${agentId}/cash-flow?from_date=${encodeURIComponent(fromDate)}&to_date=${encodeURIComponent(toDate)}`, {
        headers: fullHeaders(),
      }),
    getTrialBalance: (agentId: string, fromDate: string, toDate: string) =>
      request<unknown>(`/erp/erp/reports/${agentId}/trial-balance?from_date=${encodeURIComponent(fromDate)}&to_date=${encodeURIComponent(toDate)}`, {
        headers: fullHeaders(),
      }),
    getCustomerLedger: (agentId: string, fromDate: string, toDate: string) =>
      request<unknown>(`/erp/erp/reports/${agentId}/customer-ledger?from_date=${encodeURIComponent(fromDate)}&to_date=${encodeURIComponent(toDate)}`, {
        headers: fullHeaders(),
      }),
  },

  fraudEngine: {
    health: () =>
      request<{ status?: string; service?: string }>("/fraud-engine/health"),
    getStats: () =>
      request<unknown>("/fraud-engine/api/v1/fraud/stats", {
        headers: fullHeaders(),
      }),
    getCases: () =>
      request<unknown[]>("/fraud-engine/api/v1/fraud/cases", {
        headers: fullHeaders(),
      }),
  },

  nigeriaVat: {
    health: () => request<{ status: string; service: string }>("/vat/health"),
    calculateVat: (taxableAmount: string, category: string) => {
      const query = new URLSearchParams({
        taxable_amount: taxableAmount,
        category,
      });
      return request<unknown>(`/vat/vat/calculate?${query.toString()}`, {
        method: "POST",
        headers: fullHeaders(),
      });
    },
    checkRegistration: (entityId: string) =>
      request<unknown>(`/vat/vat/registration-check/${entityId}`, {
        headers: fullHeaders(),
      }),
    listBusinesses: () =>
      request<unknown>("/vat/vat/businesses", {
        headers: fullHeaders(),
      }),
    listTransactions: () =>
      request<unknown>("/vat/vat/transactions", {
        headers: fullHeaders(),
      }),
    registerVat: (data: {
      entity_id: string;
      entity_name: string;
      entity_type: string;
      tin?: string;
      annual_turnover_ngn?: string | number;
    }) =>
      request<unknown>("/vat/vat/register", {
        method: "POST",
        headers: fullHeaders(),
        body: JSON.stringify(data),
      }),
    getSummary: (entityId: string, period: string) =>
      request<unknown>(`/vat/vat/summary/${entityId}/${period}`, {
        headers: fullHeaders(),
      }),
    getExemptCategories: () =>
      request<unknown>("/vat/vat/exempt-categories", {
        headers: fullHeaders(),
      }),
    generateReturn: (data: { entity_id: string; period: string }) =>
      request<unknown>("/vat/vat/returns/generate", {
        method: "POST",
        headers: fullHeaders(),
        body: JSON.stringify(data),
      }),
    fileReturn: (returnId: string, firsReceiptNumber?: string) => {
      const url = firsReceiptNumber
        ? `/vat/vat/returns/${returnId}/file?firs_receipt_number=${encodeURIComponent(firsReceiptNumber)}`
        : `/vat/vat/returns/${returnId}/file`;
      return request<unknown>(url, { method: "POST", headers: fullHeaders() });
    },
    recordReturnPayment: (
      returnId: string,
      data: { amount_paid: number; payment_reference?: string; payment_date: string },
    ) =>
      request<unknown>(`/vat/vat/returns/${returnId}/payment`, {
        method: "POST",
        headers: fullHeaders(),
        body: JSON.stringify(data),
      }),
    getScheduleCsv: (entityId: string, period: string) =>
      request<unknown>(`/vat/vat/schedule/${entityId}/${period}/csv`, {
        headers: fullHeaders(),
      }),
    getAnnualReport: (entityId: string, year: number) =>
      request<unknown>(`/vat/vat/annual-report/${entityId}/${year}`, {
        headers: fullHeaders(),
      }),
    getAutomationConfig: (entityId: string) =>
      request<{
        entity_id: string;
        auto_record_vat: boolean;
        auto_generate_return: boolean;
        auto_file_firs: boolean;
        updated_at: string | null;
      }>(`/vat/vat/automation/${entityId}`, { headers: fullHeaders() }),
    updateAutomationConfig: (
      entityId: string,
      data: { auto_record_vat: boolean; auto_generate_return: boolean; auto_file_firs: boolean },
    ) =>
      request<{
        entity_id: string;
        auto_record_vat: boolean;
        auto_generate_return: boolean;
        auto_file_firs: boolean;
        updated_at: string | null;
      }>(`/vat/vat/automation/${entityId}`, {
        method: "PUT",
        headers: fullHeaders(),
        body: JSON.stringify(data),
      }),
  },

  stablecoin: {
    health: () =>
      request<{ status: string; service: string }>("/stablecoin/health"),
    listStablecoins: () =>
      request<unknown[]>("/stablecoin/api/v1/stablecoins", {
        headers: fullHeaders(),
      }),
    listAccounts: () =>
      request<unknown[]>("/stablecoin/api/v1/accounts", {
        headers: fullHeaders(),
      }),
  },

  securityMonitoring: {
    listAlerts: (params: { status?: string; severity?: string; skip?: number; limit?: number } = {}) => {
      const q = new URLSearchParams({ skip: String(params.skip ?? 0), limit: String(params.limit ?? 100), ...(params.status && { status_filter: params.status }), ...(params.severity && { severity_filter: params.severity }) });
      return request<unknown[]>(`/security-monitoring/api/v1/alerts/?${q}`, { headers: fullHeaders() });
    },
    createAlert: (data: { alert_id: string; title: string; severity: string; source: string; description?: string; [key: string]: unknown }) =>
      request<unknown>("/security-monitoring/api/v1/alerts/", {
        method: "POST",
        headers: fullHeaders(),
        body: JSON.stringify(data),
      }),
    getAlert: (alertId: string) =>
      request<unknown>(`/security-monitoring/api/v1/alerts/${alertId}`, { headers: fullHeaders() }),
    updateAlert: (alertId: string, data: { status?: string; severity?: string; [key: string]: unknown }) =>
      request<unknown>(`/security-monitoring/api/v1/alerts/${alertId}`, {
        method: "PATCH",
        headers: fullHeaders(),
        body: JSON.stringify(data),
      }),
    deleteAlert: (alertId: string) =>
      request<unknown>(`/security-monitoring/api/v1/alerts/${alertId}`, {
        method: "DELETE",
        headers: fullHeaders(),
      }),
    addLog: (alertId: string, data: { user_id: string; action: string; notes?: string }) =>
      request<unknown>(`/security-monitoring/api/v1/alerts/${alertId}/logs`, {
        method: "POST",
        headers: fullHeaders(),
        body: JSON.stringify(data),
      }),
    getLogs: (alertId: string) =>
      request<unknown[]>(`/security-monitoring/api/v1/alerts/${alertId}/logs`, { headers: fullHeaders() }),
  },

  storefrontAdvertising: {
    health: () =>
      request<{ status: string; service: string }>("/storefront/health"),
    createAd: async (data: {
      merchant_id: string;
      merchant_name: string;
      ad_type: string;
      title: string;
      description?: string;
      image_url?: string;
      cta_text?: string;
      cta_url?: string;
      target_audience?: string;
      target_states?: string[];
      target_lgas?: string[];
      budget_ngn?: number;
      cost_per_click_ngn?: number;
      start_date?: string;
      end_date?: string;
      priority?: number;
    }) => {
      const created = await request<unknown>("/storefront/storefront/ads", {
        method: "POST",
        headers: fullHeaders(),
        body: JSON.stringify(data),
      });

      const createdAdId =
        typeof created === "object" && created !== null && "id" in created
          ? String((created as { id: unknown }).id || "")
          : "";

      if (createdAdId) {
        await request<unknown>(`/storefront/storefront/ads/${createdAdId}/approve`, {
          method: "POST",
          headers: fullHeaders(),
        });
      }

      return created;
    },
    getActiveAds: () =>
      request<unknown[]>("/storefront/storefront/ads/active", {
        headers: fullHeaders(),
      }),
    getActiveCampaigns: (merchantId: string) =>
      request<unknown[]>(`/storefront/storefront/promos/active/${merchantId}`, {
        headers: fullHeaders(),
      }),
  },
};

// -------------------------------------------------------------------
// Compliance KYC API
// -------------------------------------------------------------------

export const complianceKycApi = {
  listRecords: (skip = 0, limit = 100) =>
    request<{ records: any[]; total: number }>(`/compliance-kyc/records?skip=${skip}&limit=${limit}`, {
      headers: fullHeaders(),
    }),

  getRecord: (recordId: string) =>
    request<any>(`/compliance-kyc/records/${recordId}`, {
      headers: fullHeaders(),
    }),

  createRecord: (data: { customer_id: string; risk_level?: string; notes?: string }) =>
    request<any>("/compliance-kyc/records", {
      method: "POST",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  updateRecord: (recordId: string, data: { status?: string; risk_level?: string; notes?: string }) =>
    request<any>(`/compliance-kyc/records/${recordId}`, {
      method: "PATCH",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  addDocument: (recordId: string, data: { document_type: string; document_number?: string; expiry_date?: string; file_url?: string }) =>
    request<any>(`/compliance-kyc/records/${recordId}/documents`, {
      method: "POST",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  addCheck: (recordId: string, data: { check_type: string; status: string; result?: any; notes?: string }) =>
    request<any>(`/compliance-kyc/records/${recordId}/checks`, {
      method: "POST",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  getSummary: () =>
    request<any>("/compliance/api/v1/kyc/summary", {
      headers: fullHeaders(),
    }),
};

// -------------------------------------------------------------------
// Agent Training Academy API
// -------------------------------------------------------------------

export const trainingApi = {
  listCourses: (skip = 0, limit = 50) =>
    request<any[]>(`/training/api/v1/training/courses?skip=${skip}&limit=${limit}`, {
      headers: fullHeaders(),
    }),

  getCourse: (courseId: string) =>
    request<any>(`/training/api/v1/training/courses/${courseId}`, {
      headers: fullHeaders(),
    }),

  createCourse: (data: { title: string; description: string; code: string; is_mandatory?: boolean; passing_threshold?: number }) =>
    request<any>("/training/api/v1/training/courses", {
      method: "POST",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  publishCourse: (courseId: string) =>
    request<any>(`/training/api/v1/training/courses/${courseId}/publish`, {
      method: "POST",
      headers: fullHeaders(),
    }),

  enrollAgent: (agentId: string, courseId: string) =>
    request<any>(`/training/api/v1/training/agents/${agentId}/enroll/${courseId}`, {
      method: "POST",
      headers: fullHeaders(),
    }),

  enrollMandatory: (agentId: string) =>
    request<any>(`/training/api/v1/training/agents/${agentId}/enroll-mandatory`, {
      method: "POST",
      headers: fullHeaders(),
    }),

  getAgentDashboard: (agentId: string) =>
    request<any>(`/training/api/v1/training/agents/${agentId}/dashboard`, {
      headers: fullHeaders(),
    }),

  getComplianceStatus: (agentId: string) =>
    request<any>(`/training/api/v1/training/agents/${agentId}/compliance-status`, {
      headers: fullHeaders(),
    }),

  getCertificates: (agentId: string) =>
    request<any[]>(`/training/api/v1/training/agents/${agentId}/certificates`, {
      headers: fullHeaders(),
    }),

  getStats: () =>
    request<{
      total_courses: number;
      total_enrollments: number;
      total_completions: number;
      total_certificates: number;
      avg_pass_rate: number;
      mandatory_courses: number;
    }>("/training/api/v1/training/stats", {
      headers: fullHeaders(),
    }),
};

// -------------------------------------------------------------------
// Agent Gamification API (backed by loyalty service + commission data)
// -------------------------------------------------------------------

export const gamificationApi = {
  getLeaderboard: (limit = 50) =>
    request<any>(`/loyalty/loyalty/leaderboard?limit=${limit}`, {
      headers: fullHeaders(),
    }).catch(() =>
      request<any>(`/commission/api/v1/leaderboard?limit=${limit}`, {
        headers: fullHeaders(),
      })
    ),

  getAgentPoints: (agentId: string) =>
    request<any>(`/loyalty/loyalty/accounts/${agentId}`, {
      headers: fullHeaders(),
    }),

  getStats: () =>
    request<any>("/loyalty/loyalty/stats", {
      headers: fullHeaders(),
    }),

  getActivities: (agentId: string, limit = 50) =>
    request<any[]>(`/loyalty/loyalty/accounts/${agentId}/activities?limit=${limit}`, {
      headers: fullHeaders(),
    }),

  listBadges: () =>
    request<any[]>("/loyalty/loyalty/badges", {
      headers: fullHeaders(),
    }),

  listAchievements: () =>
    request<any[]>("/loyalty/loyalty/achievements", {
      headers: fullHeaders(),
    }),
};

// -------------------------------------------------------------------
// Agent Performance API (backed by commission service)
// -------------------------------------------------------------------

export const performanceApi = {
  getLeaderboard: (params: { days?: number; sortBy?: string; page?: number; limit?: number } = {}) => {
    const q = new URLSearchParams();
    if (params.days) q.append("days", String(params.days));
    if (params.sortBy) q.append("sort_by", params.sortBy);
    if (params.page) q.append("page", String(params.page));
    if (params.limit) q.append("limit", String(params.limit));
    return request<any>(`/commission/api/v1/agents/leaderboard?${q}`, {
      headers: fullHeaders(),
    });
  },

  getAgentMetrics: (agentId: string, days = 30) =>
    request<any>(`/commission/api/v1/agents/${agentId}/metrics?days=${days}`, {
      headers: fullHeaders(),
    }),

  getStats: () =>
    request<any>("/commission/api/v1/agents/performance/stats", {
      headers: fullHeaders(),
    }),
};

// -------------------------------------------------------------------
// Billing API (billing-aggregator/billing/*)
// -------------------------------------------------------------------

const B = "/billing-aggregator/billing";

export const billingApi = {
  // ── Ledger ────────────────────────────────────────────────────────
  getLiveSplitMetrics: () =>
    request<any>(`${B}/ledger/metrics`, { headers: fullHeaders() }),

  queryLedger: (params: {
    date_from?: string;
    date_to?: string;
    billing_model?: string;
    page?: number;
    page_size?: number;
  }) => {
    const qp = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, v]) => v != null).map(([k, v]) => [k, String(v)]))
    ).toString();
    return request<any>(`${B}/ledger?${qp}`, { headers: fullHeaders() });
  },

  aggregateRevenue: (params: { period?: string; date_from?: string; date_to?: string }) => {
    const qp = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, v]) => v != null).map(([k, v]) => [k, String(v)]))
    ).toString();
    return request<any>(`${B}/ledger/aggregate?${qp}`, { headers: fullHeaders() });
  },

  getClientBillingConfig: () =>
    request<any>(`${B}/ledger/config`, { headers: fullHeaders() }),

  recordSplit: (data: Record<string, unknown>) =>
    request<any>(`${B}/ledger/split`, {
      method: "POST",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  // ── Invoices ──────────────────────────────────────────────────────
  listInvoices: (params?: { page?: number; page_size?: number; status?: string }) => {
    const p = new URLSearchParams();
    if (params?.page) p.set("page", String(params.page));
    if (params?.page_size) p.set("page_size", String(params.page_size));
    if (params?.status) p.set("status", params.status);
    return request<any>(`${B}/invoices?${p}`, { headers: fullHeaders() });
  },

  generateInvoice: (data: { period_start: string; period_end: string; currency?: string; tax_rate?: number }) =>
    request<any>(`${B}/invoice`, {
      method: "POST",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  markPaid: (invoice_id: string, data: { payment_ref: string; paid_at?: string }) =>
    request<any>(`${B}/invoice/${invoice_id}/paid`, {
      method: "PUT",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  generateCreditNote: (invoice_id: string, data: { amount: number; reason: string }) =>
    request<any>(`${B}/invoice/${invoice_id}/credit`, {
      method: "POST",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),


  // ── Lifecycle ─────────────────────────────────────────────────────
  getAlerts: () =>
    request<any>(`${B}/lifecycle/alerts`, { headers: fullHeaders() }),

  getRevenueForecast: () =>
    request<any>(`${B}/lifecycle/forecast`, { headers: fullHeaders() }),

  listDisputes: () =>
    request<any>(`${B}/lifecycle/disputes`, { headers: fullHeaders() }),

  fileDispute: (data: { invoice_id: string; amount: number; reason: string; evidence?: string }) =>
    request<any>(`${B}/lifecycle/disputes`, {
      method: "POST",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  resolveDispute: (dispute_id: string, data: { resolution: string; adjustment_amount?: number; notes: string }) =>
    request<any>(`${B}/lifecycle/disputes/${dispute_id}/resolve`, {
      method: "PUT",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  suspendBilling: (data: { reason: string; suspend_until?: string }) =>
    request<any>(`${B}/lifecycle/suspend`, {
      method: "POST",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  reactivateBilling: () =>
    request<any>(`${B}/lifecycle/reactivate`, {
      method: "POST",
      headers: fullHeaders(),
      body: JSON.stringify({}),
    }),

  // ── Production ────────────────────────────────────────────────────
  triggerReconciliation: (data: { date_range: { start: string; end: string }; type: string }) =>
    request<any>(`${B}/production/reconciliation`, {
      method: "POST",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  getCreditBalance: () =>
    request<any>(`${B}/production/credits`, { headers: fullHeaders() }),

  topUpCredits: (data: { amount: number; payment_method: string }) =>
    request<any>(`${B}/production/credits/top-up`, {
      method: "POST",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  initializePayment: (data: { amount: number; email: string }) =>
    request<any>(`${B}/payment/initialize`, {
      method: "POST",
      headers: fullHeaders(),
      body: JSON.stringify(data),
    }),

  verifyPayment: (reference: string) =>
    request<any>(`${B}/payment/verify`, {
      method: "POST",
      headers: fullHeaders(),
      body: JSON.stringify({ reference }),
    }),

  getExchangeRates: () =>
    request<any>(`${B}/production/exchange-rates`, { headers: fullHeaders() }),
};

// -------------------------------------------------------------------
// Type shapes (reflect backend to_dict() output)
// -------------------------------------------------------------------

export interface AdminRecord {
  id: string | number;
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  uin?: string;
  tenant_id: string;
  keycloak_id: string;
  is_verified: boolean;
  is_suspended: boolean;
  /** v2.perm named role, e.g. "super_admin", "support_agent" */
  access_level: string;
  created_at: string | null;
  updated_at: string | null;
}

export interface AgentRecord {
  id: string;
  first_name: string;
  last_name: string;
  name: string;
  email: string;
  phone_number: string;
  uin?: string;
  keycloak_id: string;
  tenant_id: string;
  agent_role: string; // "agent" | "super_agent" | "aggregator"
  status: string;
  onboarding_status: string;
  kyc_verification_status: string;
  kyc_verification_url?: string;
  business_name?: string;
  business_address?: string;
  city?: string;
  state?: string;
  postal_code?: string;
  lga?: string;
  is_approved: boolean;
  approved_by?: string | null;
  created_at: string | null;
  updated_at: string | null;
  deleted_at?: string | null;
}

export interface CustomerRecord {
  id: string;
  first_name: string;
  last_name: string;
  name: string;
  email: string;
  phone_number: string;
  uin?: string;
  keycloak_id: string;
  tenant_id: string;
  status: string;
  kyc_verification_status: string;
  created_at: string | null;
}

export interface CreateAdminPayload {
  firstName: string;
  lastName: string;
  email: string;
  phone: string;
  uin: string;
  password?: string;
  accessLevel?: string; // numeric string "0"–"8"
}

export interface CreateAgentPayload {
  firstName: string;
  lastName: string;
  email: string;
  phone: string;
  uin: string;
  password: string;
  agentRole?: string;
  businessName?: string;
  businessAddress?: string;
  city?: string;
  state?: string;
  postalCode?: string;
  lga?: string;
}

export interface CreateCustomerPayload {
  firstName: string;
  lastName: string;
  email: string;
  phone: string;
  uin: string;
  password: string;
  address: string;
  city: string;
  state: string;
  postalCode: string;
}

// -------------------------------------------------------------------
// Inventory & POS Types
// -------------------------------------------------------------------

export interface StoreRecord {
  id: number;
  name: string;
  description?: string;
  account_number?: string;
  owner_keycloak_id: string;
  created_at: string;
  updated_at: string;
}

export interface InventoryItem {
  id: number;
  name: string;
  sku: string;
  category: string;
  quantity: number;
  reorder_level: number;
  unit_price: number;
  supplier?: string;
  location?: string;
  status: "in_stock" | "low_stock" | "critical" | "out_of_stock";
  barcode?: string;
  store_id: number;
  created_at: string;
  updated_at: string;
  images?: ItemImage[];
}

export interface ItemImage {
  id: number;
  item_id: number;
  url: string;
  uploaded_at: string;
}

export interface CreateInventoryItemPayload {
  name: string;
  sku: string;
  category: string;
  quantity?: number;
  reorder_level?: number;
  unit_price: number;
  supplier?: string;
  location?: string;
  barcode?: string;
}

export interface UpdateInventoryItemPayload {
  name?: string;
  quantity?: number;
  reorder_level?: number;
  unit_price?: number;
  supplier?: string;
  location?: string;
  status?: string;
}

export interface SaleItem {
  name: string;
  sku: string;
  quantity: number;
  unit_price: number;
  total: number;
}

export interface CreateSalePayload {
  customer_name: string;
  items: SaleItem[];
}

export interface SaleRecord {
  id: string;
  customer_name: string;
  subtotal: number;
  tax: number;
  total: number;
  items: string; // JSON string of SaleItem[]
  created_at: string;
}

export interface InventoryMetrics {
  total_items: number;
  total_value: number;
  low_stock: number;
  out_of_stock: number;
  unique_items: number;
}

export interface POSTerminal {
  id: string;
  location: string;
  status: string; // Active | Inactive | Maintenance
  last_service?: string;
  model: string; // JSON tag on Terminal struct is "model"
  serial_number: string;
  assigned_to?: string;
  business_id?: string;
  ip_address?: string;
  software_version?: string;
  notes?: string;
  configuration?: string;
  last_software_update?: string;
  next_maintenance_date?: string;
  is_online: boolean;
  battery_level?: number;
  last_transaction_time?: string;
  transaction_count: number;
  manufacturer?: string;
  purchase_date?: string;
  warranty_end_date?: string;
  created_at?: string;
  updated_at?: string;
}

export interface CatalogManufacturer {
  id: string;
  name: string;
  slug: string;
  logo_url?: string;
  website?: string;
  created_at: string;
  updated_at: string;
}

export interface CatalogModel {
  id: string;
  manufacturer_id: string;
  name: string;
  slug: string;
  mdm_model_id: string;
  apk_variant: string;
  device_type: string;
  connectivity: string;
  created_at: string;
  updated_at: string;
}

export interface POSHardwareDevice {
  id: string;
  device_id: string;
  device_name: string;
  device_type: string;
  device_status: string;
  manufacturer: string;
  model: string;
  serial_number: string;
  firmware_version?: string;
  hardware_version?: string;
  assigned_agent_id?: string;
  assigned_location?: string;
  installation_date?: string;
  last_maintenance_date?: string;
  next_maintenance_date?: string;
  mac_address?: string;
  ip_address?: string;
  connectivity_type?: string;
  network_ssid?: string;
  latitude?: number;
  longitude?: number;
  address?: string;
  timezone?: string;
  supports_contactless?: boolean;
  supports_chip_card?: boolean;
  supports_magnetic_stripe?: boolean;
  supports_biometric?: boolean;
  supports_receipt_printing?: boolean;
  supports_cash_drawer?: boolean;
  encryption_enabled?: boolean;
  tamper_detection_enabled?: boolean;
  secure_boot_enabled?: boolean;
  device_certificate?: string;
  last_security_scan?: string;
  uptime_percentage?: number;
  average_response_time_ms?: number;
  total_transactions_processed?: number;
  last_transaction_time?: string;
  battery_level?: number;
  is_charging?: boolean;
  power_source?: string;
  edge_computing_enabled?: boolean;
  cpu_cores?: number;
  ram_memory_mb?: number;
  storage_gb?: number;
  gpu_enabled?: boolean;
  last_heartbeat?: string;
  last_seen?: string;
  connection_quality?: string;
  created_by?: string;
  updated_by?: string;
  created_at?: string;
  updated_at?: string;
  metadata?: Record<string, any>;
}

export interface POSHardwareListResponse {
  data: POSHardwareDevice[];
  total: number;
  page: number;
  limit: number;
  total_pages: number;
}

export interface AgentBusiness {
  id: string;
  business_id: string;
  tenant_id: string;
  business_name: string;
  registration_number?: string;
  tin?: string;
  business_type?: string;
  industry?: string;
  country?: string;
  address?: string;
  agent_id?: string;
  agent_keycloak_id?: string;
  is_verified: boolean;
  verification_status?: string;
  verification_date?: string;
  contact_email?: string;
  contact_phone?: string;
  documents?: Array<{ title: string; url: string }>;
  metadata?: Record<string, any>;
  created_at?: string;
  updated_at?: string;
}

export interface POSRequestRecord {
  id: string;
  agent_id: string;
  agent_keycloak_id: string;
  agent_name?: string;
  agent_email?: string;
  agent_phone?: string;
  business_id?: string;
  business_name?: string;
  preferred_model?: string;
  quantity: number;
  deployment_location?: string;
  deployment_address?: string;
  city?: string;
  state?: string;
  justification?: string;
  status: "pending" | "approved" | "assigned" | "rejected" | "cancelled";
  reviewed_by?: string;
  reviewed_at?: string;
  admin_notes?: string;
  rejection_reason?: string;
  assigned_terminal_id?: string;
  assigned_terminal_serial?: string;
  assigned_at?: string;
  tenant_id: string;
  created_at?: string;
  updated_at?: string;
}

export interface POSRequestStats {
  total: number;
  pending: number;
  approved: number;
  assigned: number;
  rejected: number;
}

export interface POSRequestReview {
  action: "approve" | "reject";
  admin_notes?: string;
  rejection_reason?: string;
}

export interface POSRequestAssign {
  terminal_id: string;
  terminal_serial: string;
  admin_notes?: string;
}

export interface CreatePOSTerminalPayload {
  location: string;
  status: string;
  model: string;
  manufacturer: string;
  serial_number: string;
  device_id?: string; // For linking to hardware device
  operating_system?: string;
  processor?: string;
  memory_gb?: number;
  storage_gb?: number;
  network_type?: string;
  contact_person?: string;
  assigned_to?: string;
  ip_address?: string;
  software_version?: string;
  notes?: string;
}

export interface UpdatePOSTerminalPayload {
  location?: string;
  status?: string;
  model?: string;
  assigned_to?: string;
  ip_address?: string;
  software_version?: string;
  notes?: string;
  is_online?: boolean;
  battery_level?: number;
}

export interface CreatePOSHardwareDevicePayload {
  device_id: string;
  device_name: string;
  device_type: string;
  manufacturer: string;
  model: string;
  serial_number: string;
  connectivity_type?: string;
  address?: string;
  latitude?: number;
  longitude?: number;
  created_by?: string;
  metadata?: Record<string, any>;
}

// -------------------------------------------------------------------
// Dispute Types
// -------------------------------------------------------------------

export interface Dispute {
  id: number;
  dispute_id: string;
  customer_id: string;
  transaction_id: string;
  dispute_type: string;
  tenant_id: string;
  amount: string;
  description: string;
  status: string;
  resolution?: string;
  created_at: string;
  transaction?: {
    id: string;
    amount: string;
    currency: string;
    description: string;
    status: string;
    created_at: string;
  };
}

export interface CreateDisputePayload {
  title: string;
  description: string;
  category: string;
  priority: string;
  agent_id: string;
  evidence_urls?: string[];
}

export interface UpdateDisputePayload {
  title?: string;
  description?: string;
  category?: string;
  priority?: string;
  status?: string;
  admin_notes?: string;
}

export interface DisputeMessage {
  id: number;
  dispute_id: number;
  sender_type: string;
  sender_id: string;
  message: string;
  created_at: string;
}

export interface CreateDisputeMessagePayload {
  sender_type: string;
  sender_id: string;
  message: string;
}

export interface DisputeStats {
  total: number;
  open: number;
  investigating: number;
  resolved: number;
  closed: number;
  total_amount: string;
}

// -------------------------------------------------------------------
// Network Status Types
// -------------------------------------------------------------------

export interface NetworkStatus {
  network_type: string;
  status: string;
  success_rate: number;
  total_transactions: number;
  successful_transactions: number;
  failed_transactions: number;
  avg_response_time?: number;
  last_updated: string;
}

export interface NetworkStatusResponse {
  networks: NetworkStatus[];
  overall_health: string;
  timestamp: string;
}

export interface TransactionResultPayload {
  network_type: string;
  success: boolean;
  amount?: number;
  agent_id?: string;
  error_code?: string;
  bank_code?: string;
}

// -------------------------------------------------------------------
// Transfer Types
// -------------------------------------------------------------------

export interface Transfer {
  id: string;
  sender_account_id: string;
  recipient_account_id: string;
  amount: number;
  status: string;
  description?: string;
  decline_reason?: string;
  created_at: string;
  updated_at: string;
  completed_at?: string;
}

export interface InitiateTransferPayload {
  sender_account_id: string;
  recipient_account_id: string;
  amount: number;
  description?: string;
  pin: string;
}

export interface TransferActionPayload {
  action: "accept" | "decline";
  pin?: string;
  reason?: string;
}

export interface BalanceCheckPayload {
  account_id: string;
  pin: string;
}

export interface BalanceResponse {
  account_id: string;
  balance: number;
  currency: string;
}

// -------------------------------------------------------------------
// Commission types
// -------------------------------------------------------------------

export interface CommissionRule {
  id: string;
  agent_tier: string;
  transaction_type: string;
  min_amount: number;
  max_amount: number;
  rate: number; // decimal, e.g. 0.002 = 0.2%
  flat_fee: number;
  is_active: boolean;
  effective_from: string;
  effective_to?: string;
  created_at: string;
  updated_at: string;
}

// -------------------------------------------------------------------
// Geofence Types
// -------------------------------------------------------------------

export interface Geofence {
  id: string;
  agent_id: string;
  tenant_id: string;
  device_id?: string;
  name?: string;
  center_latitude: number;
  center_longitude: number;
  radius_km: number;
  is_active: boolean;
  created_at: string;
  updated_at?: string;
}

export interface CreateGeofencePayload {
  agent_id: string;
  tenant_id: string;
  device_id?: string;
  name?: string;
  center_latitude: number;
  center_longitude: number;
  radius_km: number;
}

export interface LocationHistory {
  id: string;
  device_id: string;
  agent_id: string;
  tenant_id: string;
  latitude: number;
  longitude: number;
  accuracy?: number;
  speed?: number;
  battery_level?: number;
  is_within_geofence: boolean;
  timestamp: string;
}

export interface GeofenceViolation {
  id: string;
  device_id: string;
  agent_id: string;
  tenant_id: string;
  geofence_name?: string;
  current_latitude: number;
  current_longitude: number;
  geofence_center_lat: number;
  geofence_center_lng: number;
  distance_from_center_km: number;
  radius_km: number;
  violation_time: string;
  was_resolved: boolean;
  resolved_at?: string;
  admin_notes?: string;
}

export interface ViolationsResponse {
  total: number;
  violations: GeofenceViolation[];
  filters?: any;
}

export interface ViolationStats {
  period_days: number;
  total_violations: number;
  active_violations: number;
  resolved_violations: number;
  top_agents: Array<{
    agent_id: string;
    violation_count: number;
  }>;
}

export interface CreateCommissionRulePayload {
  agent_tier: string;
  transaction_type: string;
  min_amount?: number;
  max_amount?: number;
  rate: number;
  flat_fee?: number;
  is_active?: boolean;
  effective_from: string;
  effective_to?: string;
}

export interface CommissionRecord {
  id: string;
  agent_id: string;
  transaction_id: string;
  transaction_ref: string;
  transaction_type: string;
  amount: number;
  rate: number;
  commission_amount: number;
  currency: string;
  status: "pending" | "settled" | "cancelled" | "disputed";
  settlement_id?: string;
  earned_at: string;
  settled_at?: string;
  created_at: string;
}

export interface SettlementRecord {
  id: string;
  settlement_ref: string;
  agent_id: string;
  total_amount: number;
  commission_count: number;
  currency: string;
  status: "pending" | "processing" | "completed" | "failed" | "cancelled";
  payment_method: string;
  payment_details: Record<string, unknown>;
  start_date: string;
  end_date: string;
  processed_at?: string;
  failure_reason?: string;
  created_at: string;
  updated_at: string;
}

export type SettlementServiceStatus =
  | "PENDING"
  | "PROCESSING"
  | "COMPLETED"
  | "FAILED"
  | "CANCELLED";

export type SettlementServiceLogLevel =
  | "INFO"
  | "WARNING"
  | "ERROR"
  | "DEBUG";

export interface SettlementServiceLog {
  id: number;
  settlement_id: number;
  timestamp: string;
  level: SettlementServiceLogLevel;
  message: string;
  details?: string;
}

export interface SettlementServiceRecord {
  id: number;
  settlement_date: string;
  status: SettlementServiceStatus;
  amount: number;
  currency: string;
  transaction_count: number;
  external_reference_id?: string;
  created_at: string;
  updated_at: string;
  logs: SettlementServiceLog[];
}

export interface AgentBalanceRecord {
  id: string;
  agent_id: string;
  pending_balance: number;
  available_balance: number;
  settled_balance: number;
  total_earned: number;
  currency: string;
  last_settlement_at?: string;
  created_at: string;
  updated_at: string;
}

// -------------------------------------------------------------------
// MDM Types
// -------------------------------------------------------------------

export interface MdmApkVariant {
  name: string;
  file_name: string;
  version: string;
  version_code: number;
  size_bytes: number;
  sha256: string;
  min_android_api: number;
  target_models: string[];
  features: string[];
  download_url: string;
  release_notes: string;
  released_at: string;
}

export interface MdmApkVariantsResponse {
  variants: MdmApkVariant[];
  count: number;
}

export interface MdmLatestApkResponse {
  model_id: string;
  variant_name: string;
  apk: Pick<
    MdmApkVariant,
    | "name"
    | "file_name"
    | "version"
    | "version_code"
    | "size_bytes"
    | "sha256"
    | "download_url"
    | "release_notes"
    | "released_at"
  >;
}

export interface MdmDeployApkPayload {
  terminal_ids: string[];
  model_id: string;
  apk_variant: string;
  force?: boolean;
  scheduled_at?: string;
}

export interface MdmApkDeploymentResponse {
  deployment_id: string;
  status: string;
  terminals: number;
}

export interface MdmApkDeploymentStatus {
  deployment_id: string;
  terminal_ids: string[];
  model_id: string;
  apk_variant: string;
  status: string;
  total: number;
  completed: number;
  failed: number;
  created_at: string;
}

export interface MdmFirmwareUpdate {
  update_id: string;
  model_id: string;
  version: string;
  previous_version?: string;
  sha256: string;
  size_bytes: number;
  download_url: string;
  mandatory: boolean;
  release_notes: string;
  released_at: string;
  deadline?: string | null;
}

export interface MdmFirmwareUpdatesResponse {
  model_id: string;
  updates: MdmFirmwareUpdate[];
  count: number;
}

export interface MdmDeployFirmwarePayload {
  terminal_id: string;
  model_id: string;
  version: string;
}

export interface MdmFirmwareDeployResponse {
  update_id: string;
  status: string;
  terminal_id: string;
}

export interface MdmFirmwareDeployStatus {
  update_id: string;
  terminal_id: string;
  model_id: string;
  version: string;
  status: string;
}

export interface MdmProvisionPayload {
  terminal_id: string;
  model_id: string;
  serial_number: string;
  agent_id: string;
  location_id?: string;
}

export interface MdmDevice {
  terminal_id: string;
  model_id: string;
  serial_number: string;
  agent_id: string;
  location_id: string;
  state: string;
  apk_version: string;
  firmware_version: string;
  last_seen?: string;
  battery_level?: number;
  signal_strength?: number;
  tamper_status: string;
  geofence_status: string;
  latitude?: number;
  longitude?: number;
  registered_at: string;
  updated_at: string;
}

export interface MdmProvisionResponse {
  status: string;
  terminal_id: string;
  apk_variant: string;
  apk_version: string;
  download_url: string;
  device: MdmDevice;
}

export interface MdmCompleteProvisionPayload {
  apk_version: string;
  firmware_version: string;
}

export interface MdmDevicesResponse {
  devices: MdmDevice[];
  count: number;
}

export interface MdmDeviceDetail extends MdmDevice {
  last_command?: string;
}

export interface MdmDeviceStateChangeResponse {
  status: string;
  terminal_id: string;
}

export interface MdmCommandTypesResponse {
  command_types: string[];
  count: number;
}

export interface MdmCreateCommandPayload {
  terminal_id: string;
  model_id: string;
  command_type: string;
  params?: Record<string, unknown>;
  priority?: number;
  issued_by: string;
}

export interface MdmCreateCommandResponse {
  command_id: string;
  terminal_id: string;
  command: string;
  status: string;
}

export interface MdmPendingCommand {
  command_id: string;
  terminal_id: string;
  model_id: string;
  command_type: string;
  params?: Record<string, unknown>;
  priority: number;
  issued_by: string;
  issued_at: string;
  expires_at?: string;
  status: string;
}

export interface MdmPendingCommandsResponse {
  commands: MdmPendingCommand[];
  count: number;
}

export interface MdmUpdateCommandStatusPayload {
  terminal_id: string;
  status: string;
  result?: string;
}

export interface MdmCommandStatusResponse {
  command_id: string;
  status: string;
}

export interface MdmConfig {
  api_base_url: string;
  ws_url: string;
  heartbeat_interval: number;
  sync_interval: number;
  offline_mode: boolean;
  max_offline_txns?: number;
  log_level: string;
  auto_update?: boolean;
  geofence_enabled: boolean;
  tamper_protection: boolean;
  paxstore_enabled?: boolean;
  paxstore_app_id?: string;
  [key: string]: unknown;
}

export interface MdmModelConfigResponse {
  model_id: string;
  config: MdmConfig;
}

export interface MdmDiagnostics {
  terminal_id: string;
  cpu_usage: number;
  memory_used_mb: number;
  memory_total_mb: number;
  storage_used_mb: number;
  storage_total_mb: number;
  uptime_seconds: number;
  last_transaction_at?: string;
  network_type: string;
  ip_address: string;
  apk_version: string;
  firmware_version: string;
  captured_at: string;
}

export interface MdmTamperAlert {
  terminal_id: string;
  alert_type: string;
  severity: string;
  details: string;
  timestamp: string;
}

export interface MdmTamperAlertsResponse {
  alerts: MdmTamperAlert[];
  count: number;
}

export interface MdmBulkCommandPayload {
  command_type: string;
  model_id: string;
  agent_id?: string;
  params?: Record<string, unknown>;
}

export interface MdmBulkDeployPayload {
  model_id: string;
  apk_variant: string;
}

export interface MdmBulkActionResponse {
  batch_id: string;
  terminals_targeted: number;
  command?: string;
  model_id?: string;
}

export interface MdmBulkStatusResponse {
  batch_id: string;
  status: string;
}

export interface MdmFleetStats {
  total_devices: number;
  by_model: Record<string, number>;
  by_state: Record<string, number>;
  by_apk_version: Record<string, number>;
}

export interface MdmModelStats {
  model_id: string;
  total: number;
  active: number;
}

export type LoyaltyTier = "Bronze" | "Silver" | "Gold" | "Platinum";
export type LoyaltyActivityType = "EARN" | "SPEND" | "EXPIRE" | "ADJUST";

export interface LoyaltyAccountResponse {
  id: number;
  user_id: string;
  current_points: number;
  tier: LoyaltyTier;
  last_activity_at: string;
  created_at: string;
  updated_at: string;
}

export interface LoyaltyActivityResponse {
  id: number;
  account_id: number;
  type: LoyaltyActivityType;
  points_change: number;
  description: string;
  reference_id?: string;
  created_at: string;
}

export interface LoyaltyHealthResponse {
  status: string;
  service: string;
  timestamp: string;
  uptime_seconds: number;
}

export interface LoyaltyStatusResponse {
  service: string;
  status: string;
  uptime: string;
}

export interface LoyaltyMetricsResponse {
  requests_total: number;
  requests_success: number;
  requests_failed: number;
  avg_response_time_ms: number;
  uptime_seconds: number;
}
