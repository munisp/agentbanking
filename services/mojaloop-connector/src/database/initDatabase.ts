import createLogger from "../config/logger.config";
import { extract_name_form_path } from "../utils/helpers";
import { AppDataSource } from "./dataSource";

const logger = createLogger(extract_name_form_path(__filename));

export const initializeDatabase = async (): Promise<void> => {
  logger.info("Connecting to database...");

  await AppDataSource.initialize()
    .then(async () => {
      logger.info("Database connection success.");
    })
    .catch((error: any) => {
      /* istanbul ignore next */
      throw error;
    });
};
