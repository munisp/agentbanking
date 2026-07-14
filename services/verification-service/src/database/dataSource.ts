import path from "path";
import { DataSource } from "typeorm";
import { readEnv } from "../config/readEnv.config";

const DB_HOST = readEnv("DB_HOST");
const DB_PORT = readEnv("DB_PORT");
const DB_USER = readEnv("DB_USER");
const DB_PASSWORD = readEnv("DB_PASSWORD");
const DB_DATABASE = readEnv("DB_DATABASE");
const DB_DATABASE_TYPE = readEnv("DB_DATABASE_TYPE");
const DB_SSL_ENABLED = readEnv("DB_SSL_ENABLED");

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
          rejectUnauthorized: false,
        }
      : undefined,
});
