export interface IAgentProfilePayload {
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  uin: string;
  keycloak_id: string;
  tenant_id: string;
  agent_role?: string;
  business_name?: string;
  business_address?: string;
  city?: string;
  state?: string;
  postal_code?: string;
  lga?: string;
}
