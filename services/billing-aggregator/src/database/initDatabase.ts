import { AppDataSource } from "./dataSource";
import logger from "../config/logger.config";
import { initTigerBeetle } from "../config/tigerbeetle.config";

export const initializeDatabase = async (): Promise<void> => {
  logger.info("Connecting to database...");

  await AppDataSource.initialize()
    .then(async () => {
      logger.info("Database connection success...");
      initTigerBeetle();
    })
    .catch((error: unknown) => {
      throw error;
    });
};
