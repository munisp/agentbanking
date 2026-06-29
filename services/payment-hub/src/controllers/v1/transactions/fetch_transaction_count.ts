import { asyncHandler } from "../../../middlewares/async";
import { v1_validations, validateRequest } from "../../../validations";
import { transactionRepository } from "../../../repositories/transactionRepo";
import { Brackets } from "typeorm";
import { TransactionDirectionEnum, TransactionStatusEnum } from "../../../utils/enums";

export const fetch_transaction_count = asyncHandler<{ count: number }>(async (req, res) => {
  const payload = validateRequest(v1_validations.FetchTransactionsSchema, req.query);

  const queryBuilder = transactionRepository.repo.createQueryBuilder("transaction");

  if (payload.id_value) {
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
  }

  if (payload.search_text) {
    const searchText = `%${payload.search_text}%`;
    queryBuilder.andWhere("transaction.id::text ILIKE :searchText", {
      searchText,
    });
  }

  if (payload.successful_only === "true") {
    queryBuilder.andWhere("transaction.status = :status", {
      status: TransactionStatusEnum.success,
    });
  }

  if (payload.start_date && payload.end_date) {
    const startDate = new Date(payload.start_date);
    const endDate = new Date(new Date(payload.end_date).setHours(23, 59, 59, 999)); // Enforce end of day

    queryBuilder.andWhere("transaction.created_at BETWEEN :startDate AND :endDate", { startDate, endDate });
  }

  const count = await queryBuilder.getCount();

  return res.json({ count });
});
