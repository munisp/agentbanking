import httpStatus from "http-status";
import createLogger from "../../config/logger.config";
import { asyncHandler } from "../../middlewares/async";
import { extract_name_form_path } from "../../utils/helpers";
import { PutTransferErrorCallback, validateRequest } from "../../validations";
import { daprClient, redisClient } from "../../services";
import { initiate_transfer_workflow_error_signal } from "../../workflows";
import { PubSubTopics, TransactionDirectionEnum } from "../../utils/enums";
import { IReverseTransactionEvent, ITransactionFailedEvent } from "../../types/events";
import { readEnv } from "../../config/readEnv.config";
import { HttpMethod } from "@dapr/dapr";
import { ITransaction } from "../../types";
import { setupTemporalClient } from "../../setup/setupTemporalClient";

const logger = createLogger(extract_name_form_path(__filename));
const tenant = readEnv("TENANT_NAME", "ucard") as string;

export const put_transfer_error_callback = asyncHandler(async (req, res) => {
  logger.info("put_transfer_error_callback");
  logger.info(JSON.stringify(req.headers));

  const payload = validateRequest(PutTransferErrorCallback, {
    ...req.params,
    ...req.body,
  });

  res.status(httpStatus.OK).send();

  const client = await setupTemporalClient();

  try {
    const workflow_id = (await redisClient.get(`transaction:${payload.transfer_id}:workflow`)) as
      | string
      | undefined;

    if (workflow_id) {
      const handle = client.getHandle(workflow_id);

      logger.info(`send error signal ${JSON.stringify(payload)}`);

      try {
        await handle.signal(initiate_transfer_workflow_error_signal, payload);
      } catch (error) {
        logger.error("Error signaling transction", error);
      }
    }

    // fetch the transaction that has a local_id and is for this tenant and publish a reverse transaction event
    const transactions = (await daprClient.invoke(
      readEnv("CORE_DAPR_ID") as string,
      `api/v1/transactions/${payload.transfer_id}/records`,
      HttpMethod.GET,
      undefined,
      { tenant }
    )) as ITransaction[];

    const promises = transactions
      .filter((e) => Boolean(e.local_transaction_id))
      .map(async (txn) => {
        return await daprClient.publishTxnNotification<IReverseTransactionEvent>(
          PubSubTopics.reverse_transfer,
          {
            local_transaction_id: txn.local_transaction_id!,
            currency: txn.currency,
            id_type:
              txn.transaction_direction === TransactionDirectionEnum.incoming
                ? txn.payee.idType
                : txn.payer.idType,
            id_value:
              txn.transaction_direction === TransactionDirectionEnum.incoming
                ? txn.payee.idValue
                : txn.payer.idValue,
          }
        );
      });

    await Promise.all([
      daprClient.publishTxnNotification<ITransactionFailedEvent>(PubSubTopics.transaction_failed, {
        reason: payload.errorInformation.errorDescription,
        transaction_id: payload.transfer_id,
      }),
      ...promises,
    ]);
  } catch (error) {
    logger.error("Error processing callback", error);
  }
});
