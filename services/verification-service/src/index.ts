import "reflect-metadata";
import { readEnv } from "./config/readEnv.config";
import app from "./app";
import setupServer from "./setup/setupServer";
import { tryInitializeDatabase } from "./setup/setupServiceInitializers";
import logger from "./config/logger.config";

const APP_HOST = readEnv("APP_HOST");
const APP_PORT = readEnv("APP_PORT");

setupServer(app, APP_HOST, APP_PORT, tryInitializeDatabase);

// Shutdown server on SIGUSR2
process.on("SIGUSR2", () => {
  logger.info("Restart detected, Restarting...");
  process.exit();
});
