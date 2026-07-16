import logger from "../../config/logger.config";
import { transactionRepository } from "../../repositories/transactionRepo";
import { IQuoteInitiatedEvent } from "../../types/events";
import { validateRequest } from "../../validations";
import { QuoteInitiatedEventSchema } from "../../validations/v1/events";

export const quote_initiated = async (data: IQuoteInitiatedEvent) => {
  try {
    logger.info(`quote_initiated event: ${JSON.stringify(data)}`);

    const payload = validateRequest(QuoteInitiatedEventSchema, data);

    await transactionRepository.create_from_quote_initiated_event(payload);

    logger.info(`quote_initiated end`);
  } catch (error) {
    logger.error("quote_initiated failed:", error);
  }
};
