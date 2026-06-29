import * as z from "zod";
import createLogger from "../config/logger.config";
import httpStatus from "http-status";
import ApiError from "../utils/ApiError";
import {
  AmountTypeEnum,
  CurrencyEnum,
  PartyIdTypeEnum,
  PayerTypeEnum,
  TransactionInitiatorEnum,
  TransactionTypeEnum,
} from "../utils/enums";

const logger = createLogger(__filename.split("/").pop() || "UnknownFile");

/** VALIDATION FUNCTIONS **/
export function validateRequest<T>(schema: z.ZodType<T>, payload: any) {
  try {
    schema.parse(payload);
    return payload as z.infer<typeof schema>;
  } catch (e: any) {
    logger.error("Validation error: %o", e);
    throw new ApiError(httpStatus.UNPROCESSABLE_ENTITY, e.message ?? "Validation error");
  }
}

export const PaginationSchema = z.object({
  page: z.coerce.number().optional(),
  limit: z.coerce.number().optional(),
});

export const RegisterParticipantWithSwitchSchema = z.object({
  currency: z.nativeEnum(CurrencyEnum, { message: "Unsupported currency" }),
  identifier_type: z.nativeEnum(PartyIdTypeEnum, {
    message: "Unsupported identifier type",
  }),
  identifier: z.string().nonempty(),
  tenant_name: z.string(),
});

export const PutParticipantCallbackSchema = z.object({
  identifier_type: z.nativeEnum(PartyIdTypeEnum, {
    message: "Unsupported identifier type",
  }),
  identifier: z.string().nonempty(),
  fspId: z.string().nullable().optional().default(null),
});

export const LookupSchema = z.object({
  identifier: z.string(),
  identifier_type: z.nativeEnum(PartyIdTypeEnum),
  tenant_name: z.string(),
});

export const PutPartyCallbackSchema = z.object({
  identifier_type: z.nativeEnum(PartyIdTypeEnum, {
    message: "Unsupported identifier type",
  }),
  identifier: z.string().nonempty(),
  // fspId: z.string().nullable().optional().default(null),
});

export const SendLookupResponseToMojaloopSchema = z.object({
  response: z.any(),
  identifier_type: z.nativeEnum(PartyIdTypeEnum, {
    message: "Unsupported identifier type",
  }),
  identifier: z.string().nonempty(),
  fspId: z.string(),
  destination: z.string(),
});

export const TransferPartySchema = z.object({
  type: z.nativeEnum(PayerTypeEnum).optional(),
  idType: z.nativeEnum(PartyIdTypeEnum),
  idValue: z.string(),
  displayName: z.string().optional(),
  firstName: z.string().optional(),
  middleName: z.string().optional(),
  lastName: z.string().optional(),
  dateOfBirth: z.string().optional(),
  merchantClassificationCode: z.string().optional(),
});

export const PostQuotesSchema = z.object({
  amount: z.string(),
  currency: z.nativeEnum(CurrencyEnum),
  to: TransferPartySchema,
  from: TransferPartySchema,
  initiator_type: z.nativeEnum(PayerTypeEnum).optional().default(PayerTypeEnum.CONSUMER),
  geo_code: z
    .object({
      longitude: z.string(),
      latitude: z.string(),
    })
    .optional(),
  note: z.string().min(1).max(256).optional(),
  tag: z.string().optional(),
  destination: z.string(),
  reference: z.string().optional(),
  hold_id: z.string().optional(),
});

export const CreateQuoteSchema = z.object({
  quoteId: z.string().uuid(),
  transactionId: z.string().uuid(),
  payer: z.object({
    partyIdInfo: z.object({
      partyIdType: z.nativeEnum(PartyIdTypeEnum),
      partyIdentifier: z.string(),
      fspId: z.string(),
    }),
    merchantClassificationCode: z.string().optional(),
    name: z.string().optional(),
  }),
  payee: z.object({
    partyIdInfo: z.object({
      partyIdType: z.nativeEnum(PartyIdTypeEnum),
      partyIdentifier: z.string(),
      fspId: z.string(),
    }),
    merchantClassificationCode: z.string().optional(),
    name: z.string().optional(),
  }),
  amountType: z.nativeEnum(AmountTypeEnum),
  amount: z.object({
    currency: z.nativeEnum(CurrencyEnum),
    amount: z.string().regex(/^([0]|([1-9][0-9]{0,17}))([.][0-9]{0,3}[1-9])?$/), // Ensure amount has up to two decimal places
  }),
  fees: z
    .object({
      currency: z.nativeEnum(CurrencyEnum),
      amount: z.string().regex(/^([0]|([1-9][0-9]{0,17}))([.][0-9]{0,3}[1-9])?$/),
    })
    .optional(),
  transactionType: z.object({
    scenario: z.nativeEnum(TransactionTypeEnum),
    initiator: z.nativeEnum(TransactionInitiatorEnum),
    initiatorType: z.nativeEnum(PayerTypeEnum),
  }),
  geoCode: z
    .object({
      latitude: z.string(),
      longitude: z.string(),
    })
    .optional(),
  expiration: z.string().optional(),
  note: z.string().min(1).max(128).optional(),
});

export const PutQuoteCallbackSchema = z.object({
  quote_id: z.string(),
  ilpPacket: z.string(),
  condition: z.string(),
  transferAmount: z.object({
    currency: z.nativeEnum(CurrencyEnum),
    amount: z.string().regex(/^([0]|([1-9][0-9]{0,17}))([.][0-9]{0,3}[1-9])?$/), // Ensure amount has up to two decimal places
  }),
  expiration: z.string(),
});

export const PrepareTransferSchema = z.object({
  transferId: z.string(),
  amount: z.object({
    amount: z.string(),
    currency: z.nativeEnum(CurrencyEnum),
  }),
  condition: z.string(),
  ilpPacket: z.string(),
  payeeFsp: z.string(),
  payerFsp: z.string(),
});

export const PostTransferSchema = z.object({
  transferId: z.string(),
  amount: z.string(),
  currency: z.string(),
  quote: PostQuotesSchema,
  from: TransferPartySchema,
  to: TransferPartySchema,
  amountType: z.nativeEnum(AmountTypeEnum),
  transactionType: z.nativeEnum(TransactionTypeEnum),
  note: z.string().optional(),
  ilpPacket: z.any(), // TODO: define the ILP Packet object
});

export const MojaloopErrorSchema = z.object({
  errorInformation: z.object({
    errorCode: z.string(),
    errorDescription: z.string(),
  }),
});

export const PutTransferErrorCallback = z
  .object({
    transfer_id: z.string(),
  })
  .and(MojaloopErrorSchema);

export const PutLookupErrorCallback = z
  .object({
    identifier_type: z.nativeEnum(PartyIdTypeEnum),
    identifier: z.string().nonempty(),
  })
  .and(MojaloopErrorSchema);

export const PutQouteErrorCallback = z
  .object({
    quote_id: z.string(),
  })
  .and(MojaloopErrorSchema);

export const PutTransferCallback = z.object({
  transfer_id: z.string(),
  fulfilment: z.string(),
  completedTimestamp: z.string(),
  transferState: z.string(),
});
