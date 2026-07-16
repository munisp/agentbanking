import logger from "../../config/logger.config";
import { transactionRepository } from "../../repositories/transactionRepo";
import { IQuoteAgreedEvent } from "../../types/events";
import { validateRequest } from "../../validations";
import { QuoteAgreedEventSchema } from "../../validations/v1/events";

export const quote_agreed = async (data: IQuoteAgreedEvent) => {
  try {
    logger.info(`quote_agreed event: ${JSON.stringify(data)}`);

    const { quote_id } = validateRequest(QuoteAgreedEventSchema, data);

    await transactionRepository.update_from_quote_agreed_event(quote_id);

    logger.info(`quote_agreed end`);
  } catch (error) {
    logger.error("quote_agreed failed:", error);
  }
};
