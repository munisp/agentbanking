import dotenv from "dotenv";
import path from "path";

export function configureEnvironment(): void {
  dotenv.config({
    path: path.resolve(process.cwd(), ".env"),
    override: true,
  });
}

configureEnvironment();

export function readEnv<T>(key: string, defaultValue?: T): T | undefined {
  const value = process.env[key] as T;
  return value ?? defaultValue;
}
