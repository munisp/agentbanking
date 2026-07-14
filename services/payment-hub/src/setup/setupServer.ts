import logger from "../config/logger.config";
import { readEnv } from "../config/readEnv.config";
import { subscribeToPubsubTopics } from "../events/listeners";
import { daprServer } from "../services";

const APP_PORT = Number(readEnv("APP_PORT", 3000));
const ENV = process.env.NODE_ENV || readEnv("NODE_ENV");

export default async function setupServer(tryInitializeDatabase: () => Promise<void>): Promise<void> {
  await tryInitializeDatabase();
  subscribeToPubsubTopics(daprServer);
  await daprServer.start();

  logger.info(`Application is running on Port: ${APP_PORT}`);
  logger.info(`Application is running in ${ENV} mode`);
}
