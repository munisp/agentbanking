import * as z from "zod";

const CardDataSchema = z.object({
  pan: z.string(),
  expiryMonth: z.string().regex(/^(0[1-9]|1[0-2])$/, "Invalid expiry month"), // MM (01-12)
  expiryYear: z.string().regex(/^\d{2}$/, "Invalid expiry year"), // YY (last two digits of year)
  track2: z.string(),
  pinBlock: z.string(),
});

const EMVStandardPayloadSchema = z.object({
  amount: z.number().positive("Amount must be positive"),
  transactionCurrencyCode: z.string().length(3, "Currency code must be 3 characters"),
  transactionDate: z.string(),
  accountType: z.string(),
  cardData: CardDataSchema,
  serialNumber: z.string().optional(),
  cardSequenceNumber: z.string().optional(),
  iccData: z.string().optional(),
  terminalID: z.string(),
  agentId: z.string(),
  preferredChannel: z.number().optional(),
  applicationInterchangeProfile: z.string().optional(),
  atc: z.string().optional(),
  cryptogram: z.string().optional(),
  cryptogramInformationData: z.string().optional(),
  cvmResults: z.string().optional(),
  iad: z.string().optional(),
  terminalVerificationResult: z.string().optional(),
  terminalCountryCode: z.string().length(2, "Country code must be 2 characters").optional(),
  terminalType: z.string().optional(),
  terminalCapabilities: z.string().optional(),
  transDate: z.string().optional(),
  transactionType: z.string().optional(),
  unpredictableNumber: z.string().optional(),
  dedicatedFileName: z.string().optional(),
  stan: z.string().optional(),
  rrn: z.string().optional(),
  institutionCode: z.string().optional(),
});

export const ProcessCardPaymentSchema = EMVStandardPayloadSchema;
