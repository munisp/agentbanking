import { asyncHandler } from "../../../middlewares/async";
import { Transaction } from "../../../models/Transaction";
import { v1_validations, validateRequest } from "../../../validations";
import logger from "../../../config/logger.config";
import { inspect } from "util";
import { transactionRepository } from "../../../repositories/transactionRepo";
import { Brackets } from "typeorm";
import { TransactionDirectionEnum, TransactionStatusEnum } from "../../../utils/enums";

export const fetch_last_transaction = asyncHandler<{
  transaction: Transaction | null;
}>(async (req, res) => {
  const payload = validateRequest(v1_validations.GetLastSuccessfulTxnSchema, req.query);

  logger.info(`fetch last transaction: ${inspect(payload, false, 3)}`);

  const queryBuilder = transactionRepository.repo.createQueryBuilder("transaction");

  const values = payload.id_value.split(",");

  queryBuilder.andWhere(
    new Brackets((qb) => {
      values.forEach((value, index) => {
        const idValueJson = JSON.stringify({ idValue: value.trim() });

        const payerCondition = `(transaction.payer::jsonb @> :payerIdValue${index} AND transaction.transaction_direction = :outgoing${index})`;
        const payeeCondition = `(transaction.payee::jsonb @> :payeeIdValue${index} AND transaction.transaction_direction = :incoming${index})`;

        const parameters = {
          [`payerIdValue${index}`]: idValueJson,
          [`payeeIdValue${index}`]: idValueJson,
          [`outgoing${index}`]: TransactionDirectionEnum.outgoing,
          [`incoming${index}`]: TransactionDirectionEnum.incoming,
        };

        if (index === 0) {
          qb.where(`${payerCondition} OR ${payeeCondition}`, parameters);
        } else {
          qb.orWhere(`${payerCondition} OR ${payeeCondition}`, parameters);
        }
      });
    })
  );

  queryBuilder.andWhere("transaction.status = :status", {
    status: TransactionStatusEnum.success,
  });

  queryBuilder.andWhere("transaction.created_at <= :maxDate", {
    maxDate: payload.max_date,
  });

  const transactions = await queryBuilder
    .select("transaction")
    .orderBy("transaction.created_at", "DESC")
    .take(1)
    .getMany();

  if (values.includes("3")) {
    logger.info("Result of last transaction");

    logger.info(inspect(transactions, false, 4));
  }

  return res.json({ transaction: transactions[0] || null });
});
