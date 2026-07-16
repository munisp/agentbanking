import httpStatus from "http-status";
import * as z from "zod";
import logger from "../config/logger.config";
import { ApiError } from "../middlewares/error";

export function validateRequest<T>(schema: z.ZodType<T>, payload: any) {
  try {
    schema.parse(payload);
    return payload as z.infer<typeof schema>;
  } catch (e: any) {
    logger.error("Validation error: %o", e);
    throw new ApiError(
      httpStatus.UNPROCESSABLE_ENTITY,
      e.message ?? "Validation error",
      "VER-422-00",
      "verification-service",
    );
  }
}

export async function validateRequestAsync<T>(
  schema: z.ZodTypeAny,
  payload: T,
  validationFunction?: Function,
) {
  try {
    schema.parse(payload);
    validationFunction && (await validationFunction());
  } catch (e: any) {
    throw new ApiError(
      httpStatus.UNPROCESSABLE_ENTITY,
      "Validation error",
      "VER-422-00",
      "verification-service",
    );
  }
}
