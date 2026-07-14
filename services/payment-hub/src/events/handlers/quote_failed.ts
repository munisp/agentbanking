import logger from "../../config/logger.config";
import { transactionRepository } from "../../repositories/transactionRepo";
import { IQuoteFailedEvent } from "../../types/events";
import { validateRequest } from "../../validations";
import { QuoteFailedEventSchema } from "../../validations/v1/events";

export const quote_failed = async (data: IQuoteFailedEvent) => {
  try {
    logger.info(`quote_failed event: ${JSON.stringify(data)}`);

    const { quote_id, reason } = validateRequest(QuoteFailedEventSchema, data);

    await transactionRepository.update_from_quote_failed_event(
      quote_id,
      reason
    );

    logger.info(`quote_failed end`);
  } catch (error) {
    logger.error("quote_failed failed:", error);
  }
};
