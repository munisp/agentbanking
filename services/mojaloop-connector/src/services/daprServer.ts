import app from "../app";
import { DaprServer } from "@dapr/dapr";
import { type Express } from "express";
import { readEnv } from "../config/readEnv.config";
import createLogger from "../config/logger.config";

const logger = createLogger(__filename.split("/").pop() || "UnknownFile");

export class DaprServerService extends DaprServer {
  private static instance: DaprServerService | null = null;

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
  }

  static getInstance(): DaprServerService {
    if (!DaprServerService.instance) {
      logger.info("Initialized Dapr Server Class");
      DaprServerService.instance = new DaprServerService(
        readEnv("APP_HOST") as string,
        readEnv("APP_PORT") as string,
        app,
        readEnv("DAPR_HOST") as string,
        readEnv("DAPR_HTTP_PORT") as string
      );
    }
    return DaprServerService.instance;
  }
}

export const daprServer = DaprServerService.getInstance();
