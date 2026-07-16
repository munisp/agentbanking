import createLogger from "../config/logger.config";
import { MojaloopApiClient } from "../lib/MojaloopApiClient";
import { IPostTransfer } from "../types";
import { extract_name_form_path } from "../utils/helpers";

const logger = createLogger(extract_name_form_path(__filename));

export const prepare_transfer = async (data: IPostTransfer) => {
  try {
    await MojaloopApiClient.getInstance().prepare_transfer(data);
  } catch (error) {
    logger.error("error prepare_transfer", error);
    throw error;
  }
};
