import { DaprServer } from "@dapr/dapr";
import { type Express } from "express";
import app from "../app";
import logger from "../config/logger.config";
import { readEnv } from "../config/readEnv.config";

export class DaprServerService extends DaprServer {
  private static instance: DaprServerService | null = null;

  private constructor(
    serverHost: string,
    serverPort: string,
    serverHttp: Express,
    daprHost: string,
    daprPort: string,
  ) {
    super({
      serverHost,
      serverPort,
      serverHttp,
      clientOptions: {
        daprHost,
        daprPort,
      },
    });
  }

  static getInstance(): DaprServerService {
    if (!DaprServerService.instance) {
      logger.info("Initialized Dapr Server Class");
      DaprServerService.instance = new DaprServerService(
        readEnv("APP_HOST") as string,
        readEnv("APP_PORT") as string,
        app,
        readEnv("DAPR_HOST") as string,
        readEnv("DAPR_HTTP_PORT") as string,
      );
    }
    return DaprServerService.instance;
  }

  subscribe(
    topic: string,
    callback: (data: any) => Promise<void>,
    pubsub = readEnv("TXN_PUBSUB_NAME", "54agent-txn-pubsub") as string,
  ) {
    const topic_prefix = readEnv("DAPR_PUBSUB_TOPIC_PREFIX", "") as string;
    const prefixed_topic = topic_prefix + topic;

    logger.info(`Subscribe to topic: ${prefixed_topic} pubsub: ${pubsub}`);
    return this.pubsub.subscribe(pubsub, prefixed_topic, async (data) => {
      logger.info(`Received ${prefixed_topic} event..`);
      await callback(data);
    });
  }
}

export const daprServer = DaprServerService.getInstance();
