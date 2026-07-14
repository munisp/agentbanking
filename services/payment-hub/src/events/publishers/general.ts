import { v4 as uuidv4 } from "uuid";
import { PhEventTypeEnum } from "../../utils/enums";
import { daprClient } from "../../services/daprClient";
import logger from "../../config/logger.config";
import { BaseEventSchema } from "../../validations/v1";
import { readEnv } from "../../config/readEnv.config";

const topic = readEnv("GENERAL_EVENT_TOPIC", "paymenthub-transaction");

export const publishGeneralEvent = async <T extends object>(
  payload: T,
  eventType: PhEventTypeEnum,
  aggregateId?: string
) => {
  const event = {
    event_id: uuidv4(),
    idempotency_key: uuidv4(),
    aggregate_id: aggregateId ?? uuidv4(),
    event_version: 1,
    timestamp: new Date().toISOString(),
    payload,
    event_type: eventType,
  };

  // Validate event structure
  BaseEventSchema.parse(event);

  logger.info("Publishing event:", event);

  await daprClient.publishGeneralEvent(topic!, event);

  logger.info(`Event ${event.event_id} published`);
};
