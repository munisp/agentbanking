import axios from "axios";
import httpStatus from "http-status";
import * as https from "https";
import logger from "../config/logger.config";
import { readEnv } from "../config/readEnv.config";
import { KycWorkflowResult } from "../types/workflow";

// TLS certificate verification is ON by default. It may ONLY be disabled via
// the explicit opt-in env var WEBHOOK_INSECURE_TLS=true (e.g. a local dev
// webhook receiver with a self-signed certificate). Never enable this in
// production: disabling verification exposes webhook payloads (KYC PII) to
// MITM attacks.
const insecureTls = readEnv("WEBHOOK_INSECURE_TLS") === "true";
if (insecureTls) {
  // SEC-12 hardening: escalate from warn to startup-fatal in production.
  if (process.env.NODE_ENV === "production" || process.env.ENVIRONMENT === "production") {
    throw new Error(
      "FATAL: WEBHOOK_INSECURE_TLS=true is not allowed in production — TLS certificate verification must stay enabled."
    );
  }
  logger.warn(
    "WARNING: WEBHOOK_INSECURE_TLS=true — TLS certificate verification is DISABLED for outbound webhooks. Do not use in production."
  );
}

export async function sendWebhook(url: string, result: KycWorkflowResult) {
  const response = await axios.post(url, result, {
    headers: {
      "Content-Type": "application/json",
    },
    httpsAgent: new https.Agent({ rejectUnauthorized: !insecureTls }),
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
