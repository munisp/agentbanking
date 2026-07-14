import { v4 } from "uuid";
import { asyncHandler } from "../../middlewares/async";
import createLogger from "../../config/logger.config";
import { extract_name_form_path, parseAndValidateAmount, runWorkflow } from "../../utils/helpers";
import { PostQuotesSchema, validateRequest } from "../../validations";
import {
  AmountTypeEnum,
  PayerTypeEnum,
  TransactionInitiatorEnum,
  TransactionTypeEnum,
} from "../../utils/enums";
import { readEnv } from "../../config/readEnv.config";
import { daprClient, redisClient } from "../../services";
import { HttpMethod } from "@dapr/dapr";
import { IGetWithdrawalChargesResponse, IQuotePayload } from "../../types";
import { initiate_transfer_workflow } from "../../workflows";
import { IInitiateTransfer } from "../../types/workflow";
import { uuid4 } from "@temporalio/workflow";
import { TRANSFER_EXPIRATION_SECONDS } from "../../utils/constants";

const logger = createLogger(extract_name_form_path(__filename));
const tenant = readEnv("TENANT_NAME", "ucard") as string;
// use core banking Dapr app id instead of Fineract
const core_banking_dapr_id = readEnv(
  "CORE_BANKING_CONNECT_DAPR_ID",
  "core-banking"
) as string;

export const initiate_transfer = asyncHandler(async (req, res) => {
  logger.info({ message: "initiate transfer" });

  const {
    from,
    to,
    currency,
    amount: money_to_transfer,
    geo_code,
    initiator_type = PayerTypeEnum.CONSUMER,
    destination,
    tag,
    note,
    reference,
    hold_id,
  } = validateRequest(PostQuotesSchema, req.body);

  const workflow_id = uuid4();
  const quote_id = v4();
  const expiration = new Date();
  expiration.setSeconds(expiration.getSeconds() + TRANSFER_EXPIRATION_SECONDS);

  const quote_payload: IQuotePayload = {
    quoteId: quote_id,
    transactionId: v4(),
    payer: {
      partyIdInfo: {
        partyIdType: from.idType,
        partyIdentifier: from.idValue,
        fspId: tenant,
      },
      merchantClassificationCode: from.merchantClassificationCode,
      name: from.displayName,
    },
    tag,
    payee: {
      partyIdInfo: {
        partyIdType: to.idType,
        partyIdentifier: to.idValue,
        fspId: destination,
      },
      merchantClassificationCode: to.merchantClassificationCode,
      name: to.displayName,
    },
    amountType: AmountTypeEnum.RECEIVE, // meaning that the amount is what the payee fsp gets regardless of fees
    amount: {
      currency,
      amount: parseAndValidateAmount(money_to_transfer),
    },
    transactionType: {
      scenario: TransactionTypeEnum.TRANSFER,
      initiator: TransactionInitiatorEnum.PAYER,
      initiatorType: initiator_type,
    },
    note,
    geoCode: geo_code,
    expiration: expiration.toISOString(),
    reference,
  };

  logger.info({
    message: "Initiate Transfer - Generated Quote Payload",
    category: "transaction",
    data: quote_payload,
    quote_id: quote_id,
  });

  const quotePersistKey = `quote:payer:${quote_payload.quoteId}`;

  // get fees from core banking service
  const charge = (await daprClient.invoke(
    core_banking_dapr_id,
    `charges/withdrawal/${from.idType}/${encodeURIComponent(
      from.idValue
    )}?currency=${currency}&amount=${parseAndValidateAmount(money_to_transfer)}`,
    HttpMethod.GET
  )) as IGetWithdrawalChargesResponse;

  logger.info({
    message: "Payer Dfsp Charges",
    category: "transaction",
    data: charge,
    quote_id: quote_id,
  });

  await redisClient.set(
    quotePersistKey,
    JSON.stringify({ charge, workflow_id, amount: quote_payload.amount }),
    "EX",
    60
  );

  const txn_id_key = `transaction:${quote_payload.transactionId}:workflow`;

  await redisClient.set(txn_id_key, workflow_id, "EX", 60);

  const workflow_payload = {
    destination,
    fsp_id: tenant,
    payload: quote_payload,
    fees: charge,
    hold_id,
  };

  logger.info({
    message: `Starting workflow for initiate_transfer_workflow from ${workflow_payload.fsp_id} to ${destination}`,
    category: "transaction",
    quote_id: quote_id,
    data: { workflow_id, workflow_payload },
  });

  await runWorkflow<IInitiateTransfer, void>(initiate_transfer_workflow, {
    args: workflow_payload,
    workflowId: workflow_id,
    awaitResult: false,
  });

  res.setHeader("Content-Type", "application/json");

  return res.json({
    success: true,
    message: "Transaction submitted successfully",
    transaction_id: quote_payload.transactionId,
  });
});
