import logger from "../config/logger.config";
import { INotificationPayload } from "../types/notification";
import { PubsubTopics } from "../utils/constants";
import { readEnv } from "../config/readEnv.config";
import { DaprClientService } from "../lib/daprClient";

class NotificationService {
  event = async (notificationPayload: INotificationPayload) => {
    logger.info("Publishing notification event..");

    logger.info("Notification Payload: " + JSON.stringify(notificationPayload));

    // await DaprClientService.getInstance().publish<INotificationPayload>(
    //   readEnv("DAPR_PUBSUB_NAME"),
    //   readEnv("DAPR_PUBSUB_TOPIC_PREFIX") + PubsubTopics.NEW_NOTIFICATION,
    //   notificationPayload
    // );
  };
}

export const notificationService = new NotificationService();
