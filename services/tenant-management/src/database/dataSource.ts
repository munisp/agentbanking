import path from "path";
import { DataSource } from "typeorm";
import { devEnvironment, readEnv } from "../config/readEnv.config";
import { SupportedDatabaseTypes } from "../utils/enums";

const DB_HOST = readEnv("DB_HOST");
const DB_PORT = readEnv("DB_PORT");
const DB_USER = readEnv("DB_USER");
const DB_PASSWORD = readEnv("DB_PASSWORD");
const DB_DATABASE = readEnv("DB_DATABASE");
const DB_DATABASE_TYPE = readEnv("DB_DATABASE_TYPE");

// TLS certificate verification for the database connection is ON by default.
// It may ONLY be disabled via the explicit opt-in env var
// DB_SSL_INSECURE_TLS=true (e.g. a local dev database with a self-signed
// certificate). In production this is a startup-fatal misconfiguration:
// disabling verification exposes the database connection to MITM attacks.
const DB_SSL_INSECURE_TLS = process.env.DB_SSL_INSECURE_TLS === "true";
if (DB_SSL_INSECURE_TLS && (process.env.NODE_ENV === "production" || process.env.ENVIRONMENT === "production")) {
  throw new Error(
    "FATAL: DB_SSL_INSECURE_TLS=true is not allowed in production — database TLS certificate verification must stay enabled."
  );
}

export const AppDataSource = new DataSource({
  type: DB_DATABASE_TYPE as SupportedDatabaseTypes,
  host: DB_HOST,
  port: DB_PORT,
  username: DB_USER,
  password: DB_PASSWORD,
  database: DB_DATABASE,
  synchronize: false,
  migrationsRun: true,
  migrationsTransactionMode: "each",
  logging: false,
  entities: [path.join(__dirname, "../entity/*.{js,ts}")],
  migrations: [path.join(__dirname, "../migration/*.{js,ts}")],
  subscribers: [],
  ssl: devEnvironment()
    ? undefined
    : {
        rejectUnauthorized: !DB_SSL_INSECURE_TLS,
      },
});
