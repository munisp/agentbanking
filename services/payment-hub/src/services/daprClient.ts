import { DaprClient, HttpMethod } from "@dapr/dapr";
import logger from "../config/logger.config";
import { readEnv } from "../config/readEnv.config";

class DaprClientService {
  private static instance: DaprClientService | null = null;
  private readonly client: DaprClient;

  private constructor() {
    this.client = new DaprClient();
  }

  static getInstance(): DaprClientService {
    if (!DaprClientService.instance) {
      DaprClientService.instance = new DaprClientService();
    }
    return DaprClientService.instance;
  }

  async publishTxnNotification<T extends object>(
    topic: string,
    data: T,
    pubsub: string = readEnv("TXN_PUBSUB_NAME", "54agent-txn-pubsub") as string,
  ) {
    try {
      const topic_prefix = readEnv("DAPR_PUBSUB_TOPIC_PREFIX", "") as string;
      const prefixed_topic = topic_prefix + topic;

      logger.info(`publishTxnNotification ${prefixed_topic} pubsub: ${pubsub}`);
      return await this.client.pubsub.publish(pubsub, prefixed_topic, data);
    } catch (error) {
      logger.info(`Error ${JSON.stringify(error)}`);
      throw error;
    }
  }

  async publishExternalEvent<T extends object>(
    topic: string,
    data: T,
    pubsub: string = readEnv(
      "EXTERNAL_DAPR_EVENT_PUBSUB_NAME",
      "54agent-ph-event-pubsub",
    ) as string,
  ) {
    try {
      const topic_prefix = readEnv("DAPR_PUBSUB_TOPIC_PREFIX", "") as string;
      const prefixed_topic = topic_prefix + topic;

      logger.info(`publishExternalEvent ${prefixed_topic} pubsub: ${pubsub}`);
      return await this.client.pubsub.publish(pubsub, prefixed_topic, data);
    } catch (error) {
      logger.info(`Error ${JSON.stringify(error)}`);
      throw error;
    }
  }

  async publishGeneralEvent<T extends object>(
    topic: string,
    data: T,
    pubsub: string = readEnv("DAPR_PUBSUB_NAME", "pubsub") as string,
  ) {
    try {
      const topic_prefix = readEnv("DAPR_PUBSUB_TOPIC_PREFIX", "") as string;
      const prefixed_topic = topic_prefix + topic;

      logger.info(`publishGeneralEvent ${prefixed_topic} pubsub: ${pubsub}`);
      return await this.client.pubsub.publish(pubsub, prefixed_topic, data);
    } catch (error) {
      logger.info(`Error ${JSON.stringify(error)}`);
      throw error;
    }
  }

  async invoke<T extends object>(
    appId: string,
    methodName: string,
    method: HttpMethod,
    data: T,
    headers: any = {},
  ) {
    try {
      logger.info(`invoke ${appId} ${methodName} ${method}`);
      return await this.client.invoker.invoke(
        appId,
        methodName,
        method,
        method === HttpMethod.GET ? undefined : data,
        {
          headers,
        },
      );
    } catch (error) {
      logger.info(`Error ${JSON.stringify(error)}`);
      throw error;
    }
  }
}

export const daprClient = DaprClientService.getInstance();
