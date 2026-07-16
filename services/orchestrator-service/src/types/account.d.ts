export interface ICreateAccountPayload {
  name: string;
  logo?: string;
  tenant_id: string;
  keycloak_id: string;
  ledger_id: string;
  bank?: {
    create: boolean;
    name: string;
    logo: string;
  };
}

export interface ICreateBankPayload {
  name: string;
  logo?: string;
  tenant_id: string;
  keycloak_id: string;
  ledger_id: string;
}

export interface ICreateAccountResponse {
  account: {
    id: number;
    entity_id: string;
    keycloak_id: string;
    account_number: string;
  };
}
