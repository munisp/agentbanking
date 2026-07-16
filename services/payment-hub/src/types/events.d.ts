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
  tag?: string;
  reference?: string;
  note?: string;
  destinationFsp: string;
  fulfillment?: string;
  transaction_direction: TransactionDirectionEnum;
  tenant: string;
  fulfilment_secret?: string;
  fees?: { amount: string; currency: CurrencyEnum };
  payer: { idType: PartyIdTypeEnum; idValue: string };
  payee: { idType: PartyIdTypeEnum; idValue: string };
  hold_id?: string;
}

export interface ITransactionInitiatedEvent {
  transaction_id: string;
  sourceFsp: string;
  destinationFsp: string;
  amount: { amount: string; currency: CurrencyEnum };
  amount_type: AmountTypeEnum;
  transaction_direction: TransactionDirectionEnum;
  transaction_type: TransactionTypeEnum;
  tenant: string;
  tag?: string;
  note?: string;
  fees?: { amount: string; currency: CurrencyEnum };
  payer: { idType: PartyIdTypeEnum; idValue: string };
  payee: { idType: PartyIdTypeEnum; idValue: string };
  local_transaction_id?: string;
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
  processor?: string;
}

export interface IQuoteFailedEvent {
  quote_id: string;
  reason: string;
}

export interface IUpdateLocalTxnIdEvent {
  transaction_id: string;
  local_transaction_id: string;
}

export interface IReverseTransactionEvent {
  local_transaction_id: string;
  id_type: PartyIdTypeEnum;
  id_value: string;
  currency: CurrencyEnum;
  amount: string;
  tenant: string;
}
