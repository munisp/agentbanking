import { DataSource } from "typeorm";
import { ClientTypeEnum, CurrencyEnum, GenderEnum, PartyIdTypeEnum } from "../utils/enums";

export interface ISeeder {
  tenantData: any;
  seed(dataSource: DataSource, forceSeed: boolean): Promise<void>;
}

export interface IFineractCreateAccount {
  dateOfBirth: string;
  emailAddress: string;
  externalId?: string;
  accountExternalId?: string;
  firstname: string;
  fullname: string;
  groupId?: number;
  lastname: string;
  middlename?: string;
  mobileNo: string;
  officeId: number;
  clientType: ClientTypeEnum;
  clientTypeId?: number;
  gender?: GenderEnum;
  accountProductIdentifier?: string;
}

export interface IFineractCreateSubAccount extends IFineractCreateAccount {
  accountProductIdentifier: string;
  clientId: number;
}

export interface IRegisterParticipantInput {
  tenant_name: string;
  identifier: string;
  identifier_type?: PartyIdTypeEnum;
  currency?: CurrencyEnum;
}

export interface ICreateVfdWalletInput {
  bvn: string;
  date_of_birth: string;
  allow_sub_wallet?: boolean;
}

export interface ICreateVfdSubWalletInput {
  prev_account_no: string;
}

export interface ICreateVfdWalletResponse {
  account_no: string;
  account_name: string;
}

export interface IFineractFundingResponse {
  resourceId: number | string;
}

export interface IVfdLookupResponse {
  name: string;
  account: {
    number: string;
    id: string;
  };
  status: string;
  currency: string;
  bank: string;
}

export interface IFineractFundAccount {
  payee: {
    partyIdType: PartyIdTypeEnum;
    partyIdentifier: string;
  };
  amount: {
    currency: CurrencyEnum;
    amount: string;
  };
  source: string;
  note?: string;
  transaction_id: string;
}

export interface IFineractManualFundAccount {
  accountId: string;
  amount: {
    currency: CurrencyEnum;
    amount: string;
  };
  source: string;
  note?: string;
  reference: string;
  transaction_date: string;
}
