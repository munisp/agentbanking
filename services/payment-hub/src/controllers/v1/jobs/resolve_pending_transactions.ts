import httpStatus from "http-status";
import { asyncHandler } from "../../../middlewares/async";
import { transactionRepository } from "../../../repositories/transactionRepo";
import { TransactionStatusEnum } from "../../../utils/enums";
import logger from "../../../config/logger.config";
import { CoreBankingApiClient } from "../../../lib/CoreBankingApiClient";

export const resolve_pending_transactions = asyncHandler(async (_, res) => {
  res.status(httpStatus.ACCEPTED).json({ message: "Accepted" });

  logger.info("Running resolve pending transactions job..");

  const queryBuilder = transactionRepository.repo.createQueryBuilder("transaction");

  queryBuilder.andWhere("transaction.status = :status", {
    status: TransactionStatusEnum.pending,
  });

  const now = new Date();
  const startDate = new Date(now.getTime() - 24 * 60 * 60 * 1000); // 24 hours ago
  const endDate = new Date(now.getTime() - 1 * 60 * 60 * 1000); // 1 hour ago

  queryBuilder.andWhere("transaction.created_at BETWEEN :startDate AND :endDate", {
    startDate,
    endDate,
  });

  const transactions = await queryBuilder.select("transaction").getMany(); // Re-attempt 50 transactions only

  logger.info(`Found ${transactions.length} pending transactions..`);

  if (transactions.length == 0) return;

  transactions.forEach(async (transaction) => {
    // Refresh own hold_id if exists
    if (transaction.hold_id) {
      // Release funds, incase not already released
      await CoreBankingApiClient.getInstance().release_reserved_funds(
        transaction.payer.idValue,
        transaction.hold_id
      );

      // Re-reserve funds for retry
      const reserve_funds_response = await CoreBankingApiClient.getInstance().reserve_funds(
        transaction.payer.idValue,
        transaction.amount,
        "Failed Retriable Transaction"
      );

      transaction.hold_id = reserve_funds_response?.resourceId || transaction.hold_id;

      await transactionRepository.repo.save(transaction);
    }

    // Refresh parent hold_id if exists
    if (transaction?.reference) {
      const parentTransaction = await transactionRepository.repo.findOne({
        where: {
          transaction_id: transaction.reference,
        },
      });

      if (parentTransaction && parentTransaction.hold_id) {
        await CoreBankingApiClient.getInstance().release_reserved_funds(
          parentTransaction.payer.idValue,
          parentTransaction.hold_id
        );

        // Re-reserve funds for retry
        const reserve_funds_response = await CoreBankingApiClient.getInstance().reserve_funds(
          parentTransaction.payer.idValue,
          parentTransaction.amount,
          "Failed Retriable Transaction"
        );

        parentTransaction.hold_id = reserve_funds_response?.resourceId || parentTransaction.hold_id;

        await transactionRepository.repo.save(parentTransaction);
      }
    }
  });

  // --- Bulk update ---
  await transactionRepository.repo
    .createQueryBuilder()
    .update()
    .set({ status: TransactionStatusEnum.failed })
    .where("id IN (:...ids)", { ids: transactions.map((t) => t.id) })
    .execute();

  logger.info(`Resolved ${transactions.length} pending transactions to failed.`);
});
