// Design philosophy: restored original banking PWA shell.
// This adapter keeps the customer-facing shell populated in static deployments by using
// current platform endpoints when available and production-shaped empty-state helpers when they are not.

import {
  getAuditEntries,
  getAuthContext,
  getCustomers,
  getPlatformOverview,
  getTenantConfigurations,
  getWorkflowCases,
  type AuditResponse,
  type AuthContextResponse,
  type CustomerRecord as PlatformCustomerRecord,
  type OverviewResponse,
  type TenantConfiguration,
  type WorkflowCase as PlatformWorkflowCase,
} from "@/lib/platform";

export type CustomerExperienceCustomer = PlatformCustomerRecord;
export type CustomerExperienceWorkflow = PlatformWorkflowCase;

function emptyTenantConfigurations(): TenantConfiguration[] {
  return [];
}

function emptyAudit(): AuditResponse {
  return {
    asOf: new Date().toISOString(),
    role: "operations",
    total: 0,
    items: [],
  };
}

function emptyAuth(): AuthContextResponse {
  return {
    asOf: new Date().toISOString(),
    tenantId: "",
    role: "operations",
    actorId: "",
    issuer: "",
    authzEndpoint: "",
    gateway: "",
    permissions: [],
    visibleDomains: [],
    exportScopes: [],
    defaultRoute: "/",
  };
}

async function safe<T>(work: () => Promise<T>, fallback: () => T): Promise<T> {
  try {
    return await work();
  } catch {
    return fallback();
  }
}

export async function getCustomerDashboardPayload() {
  const [customers, workflows, audits, overview, tenantConfigurations] = await Promise.all([
    safe(() => getCustomers().then((response) => response.items ?? []), () => [] as CustomerExperienceCustomer[]),
    safe(() => getWorkflowCases().then((response) => response.items ?? []), () => [] as CustomerExperienceWorkflow[]),
    safe(() => getAuditEntries("operations").then((response) => response.items ?? []), () => emptyAudit().items),
    safe(() => getPlatformOverview("operations"), () => ({ asOf: new Date().toISOString(), products: [], serviceHealth: [], metrics: [] } as OverviewResponse)),
    safe(() => getTenantConfigurations().then((response) => response.items ?? []), () => emptyTenantConfigurations()),
  ]);

  const tenantConfiguration = tenantConfigurations[0] ?? emptyTenantConfigurations()[0] ?? null;

  return { customers, workflows, audits, overview, tenantConfiguration };
}

export async function getCustomerSettingsPayload() {
  const [customers, authContext, tenantConfigurations] = await Promise.all([
    safe(() => getCustomers().then((response) => response.items ?? []), () => [] as CustomerExperienceCustomer[]),
    safe(() => getAuthContext("operations"), () => emptyAuth()),
    safe(() => getTenantConfigurations().then((response) => response.items ?? []), () => emptyTenantConfigurations()),
  ]);

  const tenantConfiguration = tenantConfigurations.find((tenant) => tenant.tenantId === authContext.tenantId) ?? tenantConfigurations[0] ?? emptyTenantConfigurations()[0] ?? null;

  return {
    customer: customers[0] ?? null,
    authContext,
    tenantConfiguration,
  };
}
