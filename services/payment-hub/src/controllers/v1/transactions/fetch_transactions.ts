import { Brackets } from "typeorm";
import { asyncHandler } from "../../../middlewares/async";
import { Transaction } from "../../../models/Transaction";
import { transactionRepository } from "../../../repositories/transactionRepo";
import { IPaginatedResponse } from "../../../types/api.response";
import { TransactionDirectionEnum, TransactionStatusEnum } from "../../../utils/enums";
import { getPagination } from "../../../utils/query";
import { v1_validations, validateRequest } from "../../../validations";

export const fetch_transactions = asyncHandler<IPaginatedResponse<Transaction>>(async (req, res) => {
  const payload = validateRequest(v1_validations.FetchTransactionsSchema, req.query);

  const { limit, skip } = getPagination(payload);

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

    queryBuilder.andWhere(
      new Brackets((qb) => {
        qb.where("transaction.transaction_id::text ILIKE :searchText", { searchText }).orWhere(
          "transaction.reference::text ILIKE :searchText",
          { searchText }
        );
      })
    );
  }

  if (payload.start_date && payload.end_date) {
    const startDate = new Date(payload.start_date).toISOString();
    const endDate = new Date(new Date(payload.end_date).getTime() + 24 * 60 * 60 * 1000).toISOString();
    queryBuilder.andWhere("transaction.created_at BETWEEN :startDate AND :endDate", { startDate, endDate });
  } else if (payload.start_date) {
    const startDate = new Date(payload.start_date).toISOString();
    queryBuilder.andWhere("transaction.created_at >= :startDate", { startDate });
  } else if (payload.end_date) {
    const endDate = new Date(new Date(payload.end_date).getTime() + 24 * 60 * 60 * 1000).toISOString();
    queryBuilder.andWhere("transaction.created_at <= :endDate", { endDate });
  }

  if (payload.successful_only === "true") {
    queryBuilder.andWhere("transaction.status = :status", {
      status: TransactionStatusEnum.success,
    });
  }

  if (payload.exclude_charges === "true") {
    queryBuilder.andWhere("transaction.tag <> :tag", { tag: "CHARGE" });
  }

  if (payload.retriable_only === "true") {
    queryBuilder.andWhere("transaction.status = :status", {
      status: TransactionStatusEnum.failed,
    });
    queryBuilder.andWhere("transaction.hold_id IS NOT NULL");
  }

  const { total = 0 } = await queryBuilder
    .clone()
    .select("COUNT(DISTINCT transaction.transaction_id)", "total") // Correct way to count unique groups
    .getRawOne();

  const transactions = await queryBuilder
    .select("transaction")
    .distinctOn(["transaction.transaction_id"])
    .getMany();

  // This sorting and slicing is done in-memory because distinctOn does not guarantee order
  // We need to find a better way to do this at the DB level for large datasets
  transactions.sort((a, b) => b.created_at.getTime() - a.created_at.getTime()).slice(skip, skip + limit);

  return res.json({ data: transactions, total: Number(total) });
});
