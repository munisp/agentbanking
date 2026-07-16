export interface ICoreBankingCreateSubAccountResponse {
  savingsId: number;
}

export interface ICoreBankingCreateAccountResponse {
  savingsId: number;
  resourceId: number;
  clientId: number;
  officeId: number;
  vfd_account_number: string | null;
  vfd_account_name: string | null;
}

export type IFineractCreateSubAccountResponse = ICoreBankingCreateSubAccountResponse;
export type IFineractCreateAccountResponse = ICoreBankingCreateAccountResponse;
export interface IGetTenantResponse {
  name: string;
  dfsp_id: string;
}

export interface IPaginatedResponse<T extends object> {
  data: T[];
  total: number;
}

export interface IGenricResponse {
  success: boolean;
}
