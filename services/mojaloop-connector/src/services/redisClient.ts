import { Redis } from "ioredis";
import { readEnv } from "../config/readEnv.config";
import createLogger from "../config/logger.config";
import { extract_name_form_path } from "../utils/helpers";

const logger = createLogger(extract_name_form_path(__filename));

class RedisClient {
  private static instance: RedisClient | null = null;
  readonly client: Redis;

  constructor() {
    this.client = new Redis({
      host: readEnv("REDIS_HOST") as string,
      port: Number(readEnv("REDIS_PORT")),
      password: readEnv("REDIS_PASSWORD") as string | undefined,
      keyPrefix: readEnv("REDIS_CACHE_PREFIX") as string,
    });

    this.client.on("connect", () => logger.info("Redis connection successful"));

    this.client.on("error", (error) => logger.error("Redis connection failed", error));
  }

  static getInstance(): RedisClient {
    if (!RedisClient.instance) {
      RedisClient.instance = new RedisClient();
    }
    return RedisClient.instance;
  }
}

export const redisClient = RedisClient.getInstance().client;
