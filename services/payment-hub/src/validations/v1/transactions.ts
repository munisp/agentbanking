import * as z from "zod";
import { PaginationSchema } from "..";
import { CurrencyEnum } from "../../utils/enums";

export const FetchTransactionsSchema = z
  .object({
    id_value: z.string().optional(),
    SearchText: z.string().optional(),
    successful_only: z.enum(["true", "false"]).default("false"),
    retriable_only: z.enum(["true", "false"]).default("false"),
    exclude_charges: z.enum(["true", "false"]).default("false"),
  })
  .and(PaginationSchema);

export const GetLastSuccessfulTxnSchema = z.object({
  id_value: z.string(),
  max_date: z.string(),
});

export const FetchTxnIdTransactionsSchema = z.object({
  headers: z.object({ tenant: z.string() }),
  params: z.object({ transaction_id: z.string() }),
});

export const FetchTransactionStatusSchema = z.object({
  headers: z.object({ tenant: z.string() }),
  params: z.object({ transaction_id: z.string() }),
});

export const FetchTransactionsByDateSchema = z.object({
  date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "Date must be in YYYY-MM-DD format"),
});

export const PostManualFundSchema = z.object({
  accountId: z.coerce.string(),
  amount: z.object({
    currency: z.nativeEnum(CurrencyEnum),
    amount: z.string(),
  }),
  source: z.string(),
  note: z.string().optional(),
  reference: z.string(),
  transaction_date: z.string().datetime(),
});
