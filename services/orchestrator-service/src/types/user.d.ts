export interface IUserProfilePayload {
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  uin: string;
  keycloak_id: string;
  tenant_id: string;
  address: string;
  city: string;
  state: string;
  postal_code: string;
}

export interface IUserProfileResponse {}

export interface IUser {
  email: string;
  phone_number: string;
  name?: string;
  first_name: string;
  last_name: string;
  status: string;
  uin: string;
  tenant_id: string;
}
