import httpStatus from "http-status";
import { Brackets } from "typeorm";
import { asyncHandler } from "../../../middlewares/async";
import { transactionRepository } from "../../../repositories/transactionRepo";
import ApiError from "../../../utils/ApiError";
import { SUPPORTED_CORE_AMS, TransactionDirectionEnum, TransactionStatusEnum } from "../../../utils/enums";
import { getPagination } from "../../../utils/query";
import { v1_validations, validateRequest } from "../../../validations";

export const query_wallet_transactions = asyncHandler(async (req, res) => {
  if (!SUPPORTED_CORE_AMS.includes(req.context.ams_name)) {
    throw new ApiError(httpStatus.BAD_REQUEST, "Unsupported Ams");
  }

  const payload = validateRequest(v1_validations.FetchTransactionsSchema, req.body);
  const { skip } = getPagination(payload);
  const page = Math.abs(Number(payload.page)) || 1;
  const pageLimit = Math.abs(Number(payload.limit)) || 20;

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

  if (payload.SearchText) {
    const searchText = `%${payload.SearchText}%`;

    queryBuilder.andWhere(
      new Brackets((qb) => {
        qb.where("transaction.transaction_id::text ILIKE :searchText", { searchText }).orWhere(
          "transaction.reference::text ILIKE :searchText",
          { searchText }
        );
      })
    );
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
    .select("COUNT(DISTINCT transaction.transaction_id)", "total")
    .getRawOne();

  const transactions = await queryBuilder.select("transaction").distinctOn(["transaction.transaction_id"]).getMany();

  const result = transactions
    .sort((a, b) => b.created_at.getTime() - a.created_at.getTime())
    .slice(skip, skip + pageLimit);

  return res.json({
    result,
    totalRows: Number(total),
    currentPage: page,
    totalPages: pageLimit > 0 ? Math.ceil(Number(total) / pageLimit) : 1,
  });
});
