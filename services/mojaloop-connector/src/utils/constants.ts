import { readEnv } from "../config/readEnv.config";
import { CurrencyEnum } from "./enums";

export const TEMPORAL_ADDRESS = readEnv("TEMPORAL_ADDRESS") as string;
export const TEMPORAL_NAMESPACE = readEnv("TEMPORAL_NAMESPACE") as string;
export const TEMPORAL_TASK_QUEUE = readEnv("TEMPORAL_TASK_QUEUE") as string;

export const TRANSFER_EXPIRATION_SECONDS = 300; // 5 minutes

export const lowerDenominatorMultiplier: Record<CurrencyEnum, number> = {
  [CurrencyEnum.NGN]: 100,
};
