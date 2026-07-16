export interface IKycVerificationPayload {
  identityProvider?: string;
  user: {
    firstName: string;
    lastName: string;
    phone: string;
    UIN: string;
  };
  metadata: {
    keycloak_id: string;
    tenant_id: string;
    is_admin?: boolean;
    is_agent?: boolean;
    first_name?: string;
    last_name?: string;
  };
}

export interface IKycVerificationResponse {
  id: string;
  url: string;
}
