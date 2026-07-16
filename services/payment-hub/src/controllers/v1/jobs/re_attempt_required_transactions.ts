import httpStatus from "http-status";
import { asyncHandler } from "../../../middlewares/async";
import { transactionRepository } from "../../../repositories/transactionRepo";
import { AppAmsEnum, AppSwitchEnum, TransactionStatusEnum } from "../../../utils/enums";
import { initiate_transfer_mojaloop } from "../transfers/initiate_transfer";
import logger from "../../../config/logger.config";

export const re_attempt_required_transactions = asyncHandler(async (req, res) => {
  res.status(httpStatus.ACCEPTED).json({ message: "Accepted" });

  logger.info("Running re-attempt required transactions job..");

  const queryBuilder = transactionRepository.repo.createQueryBuilder("transaction");

  queryBuilder.andWhere("transaction.status = :status", {
    status: TransactionStatusEnum.failed,
  });

  queryBuilder.andWhere("transaction.hold_id IS NOT NULL");

  const endDate = new Date();
  const startDate = new Date(endDate.getTime() - 3 * 24 * 60 * 60 * 1000); // 24 hours ago

  queryBuilder.andWhere("transaction.created_at BETWEEN :startDate AND :endDate", {
    startDate,
    endDate,
  });

  const transactions = await queryBuilder.select("transaction").take(100).getMany(); // Re-attempt 50 transactions only

  logger.info(`Found ${transactions.length} required but failed transactions..`);

  if (transactions.length == 0) return;

  for (const transaction of transactions) {
    logger.info(`Re-attempting transaction - ${transaction.id}`);

    try {
      await initiate_transfer_mojaloop({
        switch_name: AppSwitchEnum.mojaloop,
        amount: String(transaction.amount),
        currency: transaction.currency,
        to: transaction.payee,
        from: transaction.payer,
        note: transaction.note ?? undefined,
        destination: transaction.payeeFsp,
        tag: transaction.tag,
        reference: transaction.transaction_id,
      });
    } catch (e) {
      logger.error(`Re-attempt for transaction - ${transaction.id} failed with error - ${e}`);
    }
  }
});
