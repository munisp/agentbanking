import {
  AmountTypeEnum,
  CurrencyEnum,
  PartyIdTypeEnum,
  TransactionDirectionEnum,
  TransactionQuoteStatusEnum,
  TransactionStatusEnum,
  TransactionTypeEnum,
} from "../utils/enums";

export type UnwrapPromise<T> = T extends Promise<infer U> ? U : T;

export interface IGetWithdrawalChargesResponse {
  amount: string;
  currency: CurrencyEnum;
}

export interface IPayerQuoteCache {
  charge: IGetWithdrawalChargesResponse;
  workflow_id: string;
  amount: {
    amount: string;
    currency: CurrencyEnum;
  };
}

export interface IPartyIdInfo {
  partyIdType: PartyIdTypeEnum;
  partyIdentifier: string;
  fspId: string;
}

export interface IPayerOrPayee {
  partyIdInfo: IPartyIdInfo;
  merchantClassificationCode?: string;
  name?: string;
}

export interface IAmount {
  currency: CurrencyEnum;
  amount: string;
}

export interface ITransactionType {
  scenario: TransactionTypeEnum;
  initiator: TransactionInitiatorEnum;
  initiatorType: string;
}

export interface IQuotePayload {
  quoteId: string;
  transactionId: string;
  payer: IPayerOrPayee;
  payee: IPayerOrPayee;
  amountType: AmountTypeEnum;
  tag?: string;
  note?: string;
  amount: IAmount;
  transactionType: ITransactionType;
  geoCode?: { latitude: string; longitude: string };
  expiration?: string; // Optional field
  reference?: string;
}

export interface IPostTransfer {
  transferId: string;
  payeeFsp: string;
  payerFsp: string;
  amount: {
    currency: CurrencyEnum;
    amount: string;
  };
  ilpPacket: string;
  condition: string;
  expiration: string;
  extensionList?: {
    extension: Array<{
      key: string;
      value: string;
    }>;
  };
  holdId?: string;
}

export interface IMojaloopError {
  errorInformation: {
    errorDescription: string;
    errorCode: string;
  };
}

export interface ICachedQuoteData {
  ilpAddress: string;
  amount: string;
  fulfillment: string;
  secret: string;
}

export interface IIlpPrepTxnData {
  note?: string;
  transactionId: string;
  currency: CurrencyEnum;
}

export interface ITransactionParty {
  idType: PartyIdTypeEnum;
  idValue: string;
}

export interface ITransaction {
  status: TransactionStatusEnum;
  completed_at: string | null;
  failed_at: string | null;
  reason: string | null;
  amount_type: AmountTypeEnum;
  amount: string;
  fees: string;
  currency: CurrencyEnum;
  quote_id: string;
  quote_status: TransactionQuoteStatusEnum;
  transaction_id: string;
  ilp_packet: string | null;
  fulfillment: string | null;
  fulfillment_secret: string | null;
  transaction_type: TransactionTypeEnum;
  transaction_direction: TransactionDirectionEnum;
  payerFsp: string;
  payeeFsp: string;
  payer: ITransactionParty;
  payee: ITransactionParty;
  tenant: string;
  local_transaction_id: string | null;
  note: string | null;
}
