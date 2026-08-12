// Design philosophy: restored original banking PWA shell.
// This adapter aggregates live platform endpoints for the customer-facing shell.
// It fails loudly: request errors propagate to callers (which render explicit
// error states) instead of silently substituting empty data.

import {
  getAuditEntries,
  getAuthContext,
  getCustomers,
  getPlatformOverview,
  getTenantConfigurations,
  getWorkflowCases,
  type CustomerRecord as PlatformCustomerRecord,
  type WorkflowCase as PlatformWorkflowCase,
} from "@/lib/platform";

export type CustomerExperienceCustomer = PlatformCustomerRecord;
export type CustomerExperienceWorkflow = PlatformWorkflowCase;

export async function getCustomerDashboardPayload() {
  const [customersResponse, workflowsResponse, auditsResponse, overview, tenantConfigurationsResponse] = await Promise.all([
    getCustomers(),
    getWorkflowCases(),
    getAuditEntries("operations"),
    getPlatformOverview("operations"),
    getTenantConfigurations(),
  ]);

  const tenantConfiguration = tenantConfigurationsResponse.items[0] ?? null;

  return {
    customers: customersResponse.items ?? [],
    workflows: workflowsResponse.items ?? [],
    audits: auditsResponse.items ?? [],
    overview,
    tenantConfiguration,
  };
}

export async function getCustomerSettingsPayload() {
  const [customersResponse, authContext, tenantConfigurationsResponse] = await Promise.all([
    getCustomers(),
    getAuthContext("operations"),
    getTenantConfigurations(),
  ]);

  const tenantConfiguration =
    tenantConfigurationsResponse.items.find((tenant) => tenant.tenantId === authContext.tenantId) ??
    tenantConfigurationsResponse.items[0] ??
    null;

  return {
    customer: customersResponse.items[0] ?? null,
    authContext,
    tenantConfiguration,
  };
}
