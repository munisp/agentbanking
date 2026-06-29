import httpStatus from "http-status";
import { v4 } from "uuid";
import logger from "../../../config/logger.config";
import { readEnv } from "../../../config/readEnv.config";
import { CoreBankingApiClient } from "../../../lib/CoreBankingApiClient";
import { asyncHandler } from "../../../middlewares/async";
import { transactionRepository } from "../../../repositories/transactionRepo";
import ApiError from "../../../utils/ApiError";
import {
    AmountTypeEnum,
    AppAmsEnum,
    PartyIdTypeEnum,
    SUPPORTED_CORE_AMS,
    TransactionDirectionEnum,
    TransactionStatusEnum,
    TransactionTypeEnum,
} from "../../../utils/enums";
import { validateRequest } from "../../../validations";
import { PostManualFundSchema } from "../../../validations/v1";

export const fund = asyncHandler(async (req, res) => {
  const ams = req.context.ams_name;

  if (SUPPORTED_CORE_AMS.includes(ams)) {
    const data = validateRequest(PostManualFundSchema, req.body);

    const { resourceId } =
      await CoreBankingApiClient.getInstance().manual_fund_account(
        data,
        req.context.tenant_name,
      );

    const { id: transaction_id } =
      await transactionRepository.create_from_generic_initiate_event(
        {
          amount: data.amount,
          amount_type: AmountTypeEnum.RECEIVE,
          destinationFsp: req.context.tenant_name,
          payee: {
            idType: PartyIdTypeEnum.ACCOUNT_ID,
            idValue: data.accountId,
          },
          payer: {
            idType: PartyIdTypeEnum.ALIAS,
            idValue: (
              readEnv("TENANT_NAME", "54agent") as string
            ).toLocaleUpperCase(),
          },
          sourceFsp: data.source,
          tenant: req.context.tenant_name,
          transaction_direction: TransactionDirectionEnum.incoming,
          transaction_id: v4(),
          transaction_type: TransactionTypeEnum.TRANSFER,
          note: data.note,
          tag: "MANUAL FUNDING",
          local_transaction_id: resourceId.toString(),
        },
        TransactionStatusEnum.success,
      );

    logger.info(`transaction_id: ${transaction_id}`);

    return res.json({ success: true, transaction_id });
  }

  throw new ApiError(
    httpStatus.BAD_GATEWAY,
    `Ams ${ams} is not supported for this operation`,
  );
});
