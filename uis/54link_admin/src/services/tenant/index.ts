export { tenantService, GLOBAL_FEATURE_CATALOG, default } from './tenantService';
export { getTenantHeaders } from './getTenantHeaders';
export type {
  Tenant,
  TenantContact,
  TenantBranding,
  TenantBilling,
  FeatureFlagConfig,
  GetTenantResponse,
  GetAllTenantsResponse,
  TenantMetrics,
  // COMMENTED OUT: UserRole removed - app is only for 54link
  // UserRole,
} from './tenantService';

