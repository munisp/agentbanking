import * as z from "zod";
import {
    AmountTypeEnum,
    AppAmsEnum,
    AppSwitchEnum,
    CurrencyEnum,
    PartyIdTypeEnum,
    TransactionDirectionEnum,
    TransactionTypeEnum,
} from "../../utils/enums";

const TransactionPartySchema = z.object({
  idType: z.nativeEnum(PartyIdTypeEnum),
  idValue: z.string(),
});

export const BaseEventSchema = z.object({
  event_id: z.string().uuid(),
  idempotency_key: z.string().uuid(),
  aggregate_id: z.string().uuid(),
  event_version: z.number().int(),
  timestamp: z.string().datetime(),
  payload: z.unknown(),
  event_type: z.string(),
});

export const QuoteInitiatedEventSchema = z.object({
  quote_id: z.string(),
  transaction_id: z.string(),
  amount: z.object({
    amount: z.string(),
    currency: z.nativeEnum(CurrencyEnum),
  }),
  amount_type: z.nativeEnum(AmountTypeEnum),
  transaction_type: z.nativeEnum(TransactionTypeEnum),
  sourceFsp: z.string(),
  destinationFsp: z.string(),
  fees: z
    .object({
      amount: z.string(),
      currency: z.nativeEnum(CurrencyEnum),
    })
    .optional(),
  payer: TransactionPartySchema,
  payee: TransactionPartySchema,
  transaction_direction: z.nativeEnum(TransactionDirectionEnum),
  tenant: z.string(),
  reference: z.string().optional(),
  hold_id: z.string().optional(),
});

export const TransactionInitiatedEventSchema = z.object({
  transaction_id: z.string(),
  amount: z.object({
    amount: z.string(),
    currency: z.nativeEnum(CurrencyEnum),
  }),
  amount_type: z.nativeEnum(AmountTypeEnum),
  transaction_type: z.nativeEnum(TransactionTypeEnum),
  sourceFsp: z.string(),
  destinationFsp: z.string(),
  fees: z
    .object({
      amount: z.string(),
      currency: z.nativeEnum(CurrencyEnum),
    })
    .optional(),
  payer: TransactionPartySchema,
  payee: TransactionPartySchema,
  transaction_direction: z.nativeEnum(TransactionDirectionEnum),
  tenant: z.string(),
  tag: z.string().optional(),
  hold_id: z.string().optional(),
});

export const QuoteAgreedEventSchema = z.object({
  quote_id: z.string(),
});

export const QuoteFailedEventSchema = z.object({
  quote_id: z.string(),
  reason: z.string(),
});

export const TxnFailedEventSchema = z.object({
  transaction_id: z.string(),
  reason: z.string(),
});

export const TxnCompletedEventSchema = z.object({
  transaction_id: z.string(),
  local_transaction_id: z.string().optional(),
  note: z.string().optional(),
  direction: z.nativeEnum(TransactionDirectionEnum),
  fulfilment: z.string().optional(),
  completed_at: z.string().optional(),
});

export const UpdateLocalTxnIdEventSchema = z.object({
  transaction_id: z.string(),
  local_transaction_id: z.string(),
});

export const ReverseTransferEventSchema = z.object({
  local_transaction_id: z.string(),
  id_type: z.nativeEnum(PartyIdTypeEnum),
  id_value: z.string(),
  currency: z.nativeEnum(CurrencyEnum),
  amount: z.string(),
  tenant: z.string(),
});

export const VfdInflowSchema = z.object({
  reference: z.string(),
  amount: z.string(),
  account_number: z.string(),
  originator_narration: z.string().optional(),
  originator_account_number: z.string(),
  originator_account_name: z.string(),
  originator_bank: z.string(),
  timestamp: z.string(),
  session_id: z.string(),
  transaction_channel: z.string(),
  switch_name: z
    .nativeEnum(AppSwitchEnum)
    .optional()
    .default(AppSwitchEnum.vfd),
  ams_name: z
    .nativeEnum(AppAmsEnum)
    .optional()
    .default(AppAmsEnum.core_banking),
});
export type TVfdInflowSchema = z.infer<typeof VfdInflowSchema>;

export const InflowSchema = z.object({
  reference: z.string(),
  amount: z.string(),
  payee_account_number: z.string(),
  currency: z.nativeEnum(CurrencyEnum).optional().default(CurrencyEnum.NGN),
  fees: z.string().optional(),
  payer_account_number: z.string(),
  payer_account_name: z.string(),
  payer_fsp: z.string(),
  timestamp: z.string(),
  switch_name: z.nativeEnum(AppSwitchEnum),
  ams_name: z
    .nativeEnum(AppAmsEnum)
    .optional()
    .default(AppAmsEnum.core_banking),
  processor: z.string().optional(),
  metadata: z.record(z.any()).optional(),
  tag: z.string().optional(),
  note: z.string().optional(),
});
export type TInflowSchema = z.infer<typeof InflowSchema>;
