import path from "path";
import { type TransformableInfo } from "logform";
import winston from "winston";
import { readEnv } from "./readEnv.config";

const log_path = readEnv("LOG_PATH", "./logs") as string;

const pod_name = readEnv("POD_NAME", "") as string;

const log_directory = path.join(log_path, pod_name);

const createLogger = (label: string) => {
  const logger = winston.createLogger({
    level: readEnv("LOG_LEVEL", "info") as string,
    format: winston.format.combine(
      winston.format.splat(),
      winston.format.label({ label }),
      winston.format.timestamp(),
      winston.format.json()
    ),
    defaultMeta: { service: "mojaloop-connector" },
    transports: [
      new winston.transports.File({
        filename: path.join(log_directory, "error.log"),
        level: "error",
      }),
      new winston.transports.File({
        filename: path.join(log_directory, "info.log"),
        level: "info",
      }),
      new winston.transports.File({
        filename: path.join(log_directory, "debug.log"),
        level: "debug",
      }),
      new winston.transports.File({
        filename: path.join(log_directory, "all_combined.log"),
      }),
    ],
  });

  if (process.env.NODE_ENV !== "test") {
    logger.add(
      new winston.transports.Console({
        format: winston.format.combine(
          winston.format.splat(),
          winston.format.colorize(),
          winston.format.label({ label }),
          winston.format.timestamp(),
          winston.format.printf(
            // eslint-disable-next-line @typescript-eslint/restrict-template-expressions
            (info: TransformableInfo) =>
              `${info.label}: ${info.timestamp} ${info.level}: ${info.message}`
          )
        ),
      })
    );
  }

  logger.silent = readEnv("LOG_SILENT") === "true";
  if (logger.silent) {
    console.log("Logger is disabled");
  }

  return logger;
};

export default createLogger;
