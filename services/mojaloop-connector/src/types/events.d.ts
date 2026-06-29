import {
  AmountTypeEnum,
  CurrencyEnum,
  PartyIdTypeEnum,
  TransactionDirectionEnum,
  TransactionTypeEnum,
} from "../utils/enums";

export interface IQuoteInitiatedEvent {
  quote_id: string;
  transaction_id: string;
  amount: { amount: string; currency: CurrencyEnum };
  amount_type: AmountTypeEnum;
  transaction_type: TransactionTypeEnum;
  sourceFsp: string;
  destinationFsp: string;
  transaction_direction: TransactionDirectionEnum;
  tenant: string;
  tag?: string;
  note?: string;
  fulfillment?: string;
  fulfilment_secret?: string;
  payer: { idType: PartyIdTypeEnum; idValue: string };
  payee: { idType: PartyIdTypeEnum; idValue: string };
  fees?: { amount: string; currency: CurrencyEnum };
  reference?: string;
  hold_id?: string;
}

export interface IQuoteAgreedEvent {
  quote_id: string;
}

export interface ITransactionFailedEvent {
  transaction_id: string;
  reason: string;
}

export interface ITransactionCompletedEvent {
  transaction_id: string;
  note?: string;
  direction: TransactionDirectionEnum;
  local_transaction_id?: string;
  fulfilment?: string;
  completed_at?: string;
}

export interface IQuoteFailedEvent {
  quote_id: string;
  reason: string;
}

export interface IUpdateLocalTxnId {
  transaction_id: string;
  local_transaction_id: string;
}

export interface IReverseTransactionEvent {
  local_transaction_id: string;
  id_type: PartyIdTypeEnum;
  id_value: string;
  currency: CurrencyEnum;
}
