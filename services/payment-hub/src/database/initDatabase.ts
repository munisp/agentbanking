import logger from "../config/logger.config";
import { readEnv } from "../config/readEnv.config";
import { AppDataSource } from "./dataSource";

export const initializeDatabase = async (): Promise<void> => {
  logger.info("Connecting to database...");
  logger.info(
    `Database target host=${readEnv("DB_HOST", "undefined")} port=${readEnv("DB_PORT", "undefined")} database=${readEnv("DB_DATABASE", "undefined")} schema=${readEnv("DB_SCHEMA", "undefined")} ssl=${readEnv("DB_SSL", "false")}`,
  );

  await AppDataSource.initialize()
    .then(async () => {
      logger.info("Database connection success.");
      const [{ current_database, current_schema }] = (await AppDataSource.query(
        "SELECT current_database(), current_schema()",
      )) as Array<{ current_database: string; current_schema: string }>;
      logger.info(
        `Database session confirmed database=${current_database} schema=${current_schema}`,
      );
    })
    .catch((error: any) => {
      /* istanbul ignore next */
      throw error;
    });
};
