import { DaprClient, HttpMethod } from "@dapr/dapr";
import { readEnv } from "../config/readEnv.config";
import createLogger from "../config/logger.config";

const logger = createLogger(__filename.split("/").pop() || "UnknownFile");

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

  async publishTxnNotification<T extends object>(topic: string, data: T) {
    const pubsub = readEnv("TXN_PUBSUB_NAME") as string;
    const pubsub_topic_prefix = readEnv("DAPR_PUBSUB_TOPIC_PREFIX") as string;
    const prefixed_topic = pubsub_topic_prefix + topic;

    try {
      logger.info(`publishTxnNotification ${prefixed_topic} pubsub: ${pubsub}`);
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
    data?: T,
    headers: any = {}
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
        }
      );
    } catch (error) {
      logger.error("Error Invoking dapr service", error);
      throw error;
    }
  }
}

export const daprClient = DaprClientService.getInstance();
