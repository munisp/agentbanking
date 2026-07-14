import { asyncHandler } from "../../../middlewares/async";
import { Transaction } from "../../../models/Transaction";
import { transactionRepository } from "../../../repositories/transactionRepo";
import { validateRequest } from "../../../validations";
import { FetchTxnIdTransactionsSchema } from "../../../validations/v1";

export const fetch_txn_records_by_txn_id = asyncHandler<Transaction[]>(
  async (req, res) => {
    const payload = validateRequest(FetchTxnIdTransactionsSchema, req);
    const transactions =
      await transactionRepository.fetch_txn_records_by_txn_id(
        payload.params.transaction_id,
        payload.headers.tenant
      );
    res.json(transactions);
  }
);
