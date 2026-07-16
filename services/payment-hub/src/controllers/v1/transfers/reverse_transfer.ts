import httpStatus from "http-status";
import util from "util";
import logger from "../../../config/logger.config";
import { asyncHandler } from "../../../middlewares/async";
import { transactionRepository } from "../../../repositories/transactionRepo";
import { daprClient } from "../../../services";
import {
    IReverseTransactionEvent,
    ITransactionFailedEvent,
} from "../../../types/events";
import { PubSubTopics, TransactionDirectionEnum } from "../../../utils/enums";
import { validateRequest } from "../../../validations";
import { ReverseTransferSchema } from "../../../validations/v1";

export const reverse_transfer = asyncHandler(async (req, res) => {
  const { body: payload, headers } = validateRequest(ReverseTransferSchema, {
    body: req.body,
    headers: req.headers,
  });

  const transactions = await transactionRepository.fetch_txn_records_by_txn_id(
    payload.transaction_id,
    headers.tenant,
  );

  logger.info(`Reverse transaction ID: ${payload.transaction_id}`);
  logger.info(util.inspect(transactions, false, 4));

  const promises = transactions
    .filter((e) => Boolean(e.local_transaction_id))
    .map(async (txn) => {
      return await daprClient.publishTxnNotification<IReverseTransactionEvent>(
        PubSubTopics.reverse_transfer,
        {
          local_transaction_id: txn.local_transaction_id!,
          currency: txn.currency,
          amount: txn.amount,
          tenant: txn.tenant,
          id_type:
            txn.transaction_direction === TransactionDirectionEnum.incoming
              ? txn.payee.idType
              : txn.payer.idType,
          id_value:
            txn.transaction_direction === TransactionDirectionEnum.incoming
              ? txn.payee.idValue
              : txn.payer.idValue,
        },
      );
    });

  await Promise.all(promises);

  (async () => {
    try {
      logger.info("Submitted reversal request successfully...");
      logger.info("Emit failed event on reversal...");
      await daprClient.publishTxnNotification<ITransactionFailedEvent>(
        PubSubTopics.transaction_failed,
        {
          reason: payload.reason || "Reversal",
          transaction_id: payload.transaction_id,
        },
      );
    } catch (error) {
      logger.error(error);
    }
  })();

  return res.status(httpStatus.OK).json({
    message: "Submitted reversal request successfully...",
  });
});
