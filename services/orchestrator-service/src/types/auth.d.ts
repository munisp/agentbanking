export interface IAuthProfilePayload {
  email: string;
  user_role: string;
  tenant_id: string;
  keycloak_realm: string;
  keycloak_pub_key: string;
  platform_role?: string; // v2.perm `platform` entity role (e.g. "super_admin", "it_admin")
  tenant_role?: string; // v2.perm `tenants` entity role (e.g. "branch_manager", "loan_officer")
}

export interface IAuthProfileResponse {
  auth: {
    email: string;
    keycloak_id: string;
  };
}

export interface ISetupPassword {
  keycloak_id: string;
  password: string;
  confirm_password: string;
  tenant_id: string;
  keycloak_realm: string;
  keycloak_pub_key: string;
}
