import path from "path";
import { DataSource } from "typeorm";
import logger from "../config/logger.config";
import { readEnv } from "../config/readEnv.config";

const DB_HOST = readEnv("DB_HOST");
const DB_PORT = readEnv("DB_PORT");
const DB_USER = readEnv("DB_USER");
const DB_PASSWORD = readEnv("DB_PASSWORD");
const DB_DATABASE = readEnv("DB_DATABASE");
const DB_DATABASE_TYPE = readEnv("DB_DATABASE_TYPE");
const DB_SSL_ENABLED = readEnv("DB_SSL_ENABLED");
// TLS certificate verification for the database connection is ON by default.
// It may ONLY be disabled via the explicit opt-in env var
// DB_SSL_INSECURE_TLS=true (e.g. a local dev database with a self-signed
// certificate). Never enable this in production: disabling verification
// exposes the database connection to MITM attacks.
const DB_SSL_INSECURE_TLS = readEnv("DB_SSL_INSECURE_TLS") === "true";
if (DB_SSL_INSECURE_TLS) {
  // SEC-12 hardening: escalate from warn to startup-fatal in production.
  if (process.env.NODE_ENV === "production" || process.env.ENVIRONMENT === "production") {
    throw new Error(
      "FATAL: DB_SSL_INSECURE_TLS=true is not allowed in production — database TLS certificate verification must stay enabled."
    );
  }
  logger.warn(
    "WARNING: DB_SSL_INSECURE_TLS=true — TLS certificate verification is DISABLED for the database connection. Do not use in production."
  );
}

export const AppDataSource = new DataSource({
  type: <"mysql" | "postgres">DB_DATABASE_TYPE,
  host: DB_HOST,
  port: Number(DB_PORT),
  username: DB_USER,
  password: DB_PASSWORD,
  database: DB_DATABASE,
  synchronize: true,
  logging: false,
  entities: [path.join(__dirname, "../entity/*.{js,ts}")],
  migrations: [path.join(__dirname, "../migration/*.{js,ts}")],
  subscribers: [],
  ssl:
    DB_SSL_ENABLED === "true"
      ? {
          rejectUnauthorized: !DB_SSL_INSECURE_TLS,
        }
      : undefined,
});
