import * as z from "zod";
import { SupportedDatabaseTypes } from "../utils/enums";

export const EnvSchema = z.object({
  NODE_ENV: z.string(),
  APP_HOST: z.string(),
  APP_PORT: z.coerce.number(),
  LOG_PATH: z.string().optional().default("./logs"),
  LOG_LEVEL: z.string().optional().default("info"),
  LOG_SILENT: z.string().optional().default("false"),
  DB_HOST: z.string(),
  DB_PORT: z.coerce.number(),
  DB_USER: z.string(),
  DB_PASSWORD: z.string(),
  DB_DATABASE: z.string(),
  DB_DATABASE_TYPE: z.nativeEnum(SupportedDatabaseTypes),
  DAPR_HOST: z.string(),
  DAPR_HTTP_PORT: z.string(),
  // billing-aggregator is a separate Dapr-invoked service (unlike corebanking's
  // billing-service, which is bundled in the same pod and reached over raw HTTP).
  BILLING_SERVICE_APP_ID: z.string().optional().default("billing-aggregator"),
});
