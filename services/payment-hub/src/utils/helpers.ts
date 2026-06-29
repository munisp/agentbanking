import { readEnv } from "../config/readEnv.config";

export function devEnvironment() {
  return readEnv("NODE_ENV", "development") === "development";
}

/**
 * Utility method to build a set of headers required by the SDK outbound API
 *
 * @returns {object} - Object containing key/value pairs of HTTP headers
 */
export const buildJSONHeaders = (): Record<string, any> => {
  const tenant = readEnv("TENANT_NAME", "default");

  const headers = {
    "Content-Type": "application/json",
    Accept: "application/json",
    Date: new Date().toUTCString(),
    "x-tenant-id": tenant,
  };

  return headers;
};
