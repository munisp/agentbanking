export interface IAdminProfilePayload {
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  uin: string;
  keycloak_id: string;
  tenant_id: string;
  platform_role?: string; // v2.perm `platform` entity role
  tenant_role?: string; // v2.perm `tenants` entity role
}
