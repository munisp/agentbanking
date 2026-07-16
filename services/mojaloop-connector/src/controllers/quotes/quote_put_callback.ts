import httpStatus from "http-status";
import createLogger from "../../config/logger.config";
import { asyncHandler } from "../../middlewares/async";
import { daprClient, redisClient } from "../../services";
import { IPayerQuoteCache } from "../../types";
import ApiError from "../../utils/ApiError";
import { extract_name_form_path } from "../../utils/helpers";
import { PutQuoteCallbackSchema, validateRequest } from "../../validations";
import { initiate_transfer_workflow_quote_response } from "../../workflows";
import { PubSubTopics } from "../../utils/enums";
import { IQuoteAgreedEvent } from "../../types/events";
import { setupTemporalClient } from "../../setup/setupTemporalClient";

const logger = createLogger(extract_name_form_path(__filename));

export const quote_put_callback = asyncHandler(async (req, res) => {
  const client = await setupTemporalClient();

  const payload = validateRequest(PutQuoteCallbackSchema, {
    ...req.params,
    ...req.body,
  });

  try {
    logger.info({
      message: `Received quote response`,
      category: "transaction",
      quote_id: payload.quote_id,
      data: payload,
    });

    const quote_persist_key = `quote:payer:${payload.quote_id}`;

    const cachedData = (await redisClient.get(quote_persist_key)) as string;

    if (!cachedData) {
      logger.error({
        message: `Quote has expired`,
        category: "transaction",
        quote_id: payload.quote_id,
        data: { quote_persist_key },
      });
      throw new ApiError(httpStatus.BAD_REQUEST, "Quote has expired");
    }

    const parsedCachedData = JSON.parse(cachedData) as IPayerQuoteCache;

    if (
      parsedCachedData.amount.amount != payload.transferAmount.amount ||
      parsedCachedData.amount.currency !== payload.transferAmount.currency
    ) {
      logger.error({
        message: `Amount received does not match amount sent in original quote`,
        category: "transaction",
        quote_id: payload.quote_id,
        data: {
          original_amount: parsedCachedData.amount,
          received_amount: payload.transferAmount,
        },
      });
      throw new ApiError(httpStatus.CONFLICT, "Amount mismatch");
    }

    res.status(httpStatus.OK).send();

    const { workflow_id } = parsedCachedData;

    const handle = client.getHandle(workflow_id);

    logger.info({ message: "Send signal to workflow", data: payload });

    await handle.signal(initiate_transfer_workflow_quote_response, payload);

    daprClient.publishTxnNotification<IQuoteAgreedEvent>(PubSubTopics.quote_agreed, {
      quote_id: payload.quote_id,
    });
  } catch (error) {
    logger.error({
      message: "Error Processing Quote:",
      quote_id: payload.quote_id,
      category: "transaction",
      data: JSON.stringify(error),
    });
    logger.error(error);
    throw error;
  }
});
