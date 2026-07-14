import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";
import createLogger from "../../config/logger.config";
import { extract_name_form_path } from "../../utils/helpers";
import { PutQouteErrorCallback, validateRequest } from "../../validations";
import { daprClient, redisClient } from "../../services";
import { initiate_transfer_workflow_error_signal } from "../../workflows";
import { PubSubTopics } from "../../utils/enums";
import { IQuoteFailedEvent } from "../../types/events";
import { setupTemporalClient } from "../../setup/setupTemporalClient";

const logger = createLogger(extract_name_form_path(__filename));

export const quote_error_callback = asyncHandler(async (req, res) => {
  logger.info("quote_error_callback");
  logger.info(JSON.stringify(req.headers));
  logger.info(JSON.stringify({ ...req.params, ...req.query, ...req.body }));

  const payload = validateRequest(PutQouteErrorCallback, {
    ...req.params,
    ...req.body,
  });

  res.status(httpStatus.OK).send();

  try {
    const quotePersistKey = `quote:payer:${payload.quote_id}`;

    const stringData = await redisClient.get(quotePersistKey);

    if (stringData) {
      const parsed_quote_data = JSON.parse(stringData);
      if (parsed_quote_data.workflow_id) {
        const client = await setupTemporalClient();

        const handle = client.getHandle(parsed_quote_data.workflow_id);

        logger.info(`send error signal ${JSON.stringify(payload)}`);

        await Promise.all([
          handle.signal(initiate_transfer_workflow_error_signal, payload),
          daprClient.publishTxnNotification<IQuoteFailedEvent>(PubSubTopics.quote_failed, {
            reason: payload.errorInformation.errorDescription,
            quote_id: payload.quote_id,
          }),
        ]);
      }
    }
  } catch (error) {
    logger.error("Error processing callback", error);
  }
});
