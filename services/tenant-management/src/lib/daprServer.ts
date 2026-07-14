import app from "../app";
import { DaprServer } from "@dapr/dapr";
import { type Express } from "express";
import { readEnv } from "../config/readEnv.config";
import logger from "../config/logger.config";

export class DaprServerService extends DaprServer {
  private static instance: DaprServerService | null = null;
  private readonly server: DaprServer;

  private constructor(
    serverHost: string,
    serverPort: string,
    serverHttp: Express,
    daprHost: string,
    daprPort: string
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
    this.server = this;
  }

  static getInstance(): DaprServerService {
    if (!DaprServerService.instance) {
      DaprServerService.instance = new DaprServerService(
        readEnv("APP_HOST") as string,
        String(readEnv("APP_PORT")),
        app,
        readEnv("DAPR_HOST") as string,
        readEnv("DAPR_HTTP_PORT") as string
      );
    }
    return DaprServerService.instance;
  }

  public async subscribe(pubSub: string, topic: string, callback: (data: any) => Promise<void> | void) {
    return this.server.pubsub.subscribe(pubSub, topic, async (data) => {
      logger.info(`Received ${topic} event..`);
      try {
        await callback(data);
      } catch (err) {
        logger.error(`Error while handling ${topic} event: ${err}`);
      }
    });
  }
}
