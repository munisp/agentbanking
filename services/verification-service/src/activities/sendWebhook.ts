import axios from "axios";
import httpStatus from "http-status";
import * as https from "https";
import logger from "../config/logger.config";
import { KycWorkflowResult } from "../types/workflow";

export async function sendWebhook(url: string, result: KycWorkflowResult) {
  const response = await axios.post(url, result, {
    headers: {
      "Content-Type": "application/json",
    },
    httpsAgent: new https.Agent({ rejectUnauthorized: false }),
    timeout: 30000,
  });

  if (
    response.status != httpStatus.OK &&
    response.status != httpStatus.CREATED &&
    response.status != httpStatus.ACCEPTED
  ) {
    logger.warn("Got an invalid webhook response... Retrying...");
    throw new Error("Invalid webhook response...");
  }

  return true;
}
