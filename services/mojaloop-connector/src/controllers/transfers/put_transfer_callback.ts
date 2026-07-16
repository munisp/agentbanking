import httpStatus from "http-status";
import createLogger from "../../config/logger.config";
import { asyncHandler } from "../../middlewares/async";
import { extract_name_form_path } from "../../utils/helpers";
import { PutTransferCallback, validateRequest } from "../../validations";
import { daprClient } from "../../services";
import { PubSubTopics, TransactionDirectionEnum } from "../../utils/enums";
import { ITransactionCompletedEvent } from "../../types/events";

const logger = createLogger(extract_name_form_path(__filename));

export const put_transfer_callback = asyncHandler(async (req, res) => {
  logger.info("put_transfer_callback");
  logger.info(JSON.stringify(req.headers));

  const payload = validateRequest(PutTransferCallback, {
    ...req.params,
    ...req.body,
  });

  daprClient.publishTxnNotification<ITransactionCompletedEvent>(PubSubTopics.transaction_completed, {
    transaction_id: payload.transfer_id,
    direction: TransactionDirectionEnum.outgoing,
    completed_at: payload.completedTimestamp,
    fulfilment: payload.fulfilment,
  });

  res.status(httpStatus.OK).send();

  logger.info("put_transfer_callback end");
});
