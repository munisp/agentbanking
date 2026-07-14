import { DataSource } from "typeorm";
import path from "path";
import { readEnv } from "../config/readEnv.config";
import createLogger from "../config/logger.config";
import { extract_name_form_path } from "../utils/helpers";

const logger = createLogger(extract_name_form_path(__filename));

const DB_HOSTNAME: string = readEnv("DB_HOST", "") as string;
const PORT: number = Number(readEnv("DB_PORT", 3306)) as number;
const DB_USERNAME: string = readEnv("DB_USERNAME", "") as string;
const DB_PASSWORD: string = readEnv("DB_PASSWORD", "") as string;
const DB_DATABASE: string = readEnv("DB_DATABASE", "") as string;
const DB_SCHEMA: string = readEnv("DB_SCHEMA", "mojaloop") as string;
const DB_DATABASE_TYPE: string = readEnv("DB_DATABASE_TYPE", "") as string;
const DB_SSL = (readEnv("DB_SSL", "false") as string) == "true";

export const AppDataSource = new DataSource({
  type: <"postgres">DB_DATABASE_TYPE,
  host: DB_HOSTNAME,
  port: PORT,
  username: DB_USERNAME,
  password: DB_PASSWORD,
  database: DB_DATABASE,
  schema: DB_SCHEMA,
  synchronize: false,
  logging: true,
  entities: [path.join(__dirname, "../models/*.{js,ts}")],
  migrations: [path.join(__dirname, "migrations/*.{js,ts}")],
  subscribers: [],
  ssl: DB_SSL ? { rejectUnauthorized: false } : undefined,
});
