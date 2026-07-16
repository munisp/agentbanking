import * as z from "zod";
import logger from "../config/logger.config";
import httpStatus from "http-status";
import ApiError from "../utils/ApiError";

/** VALIDATION FUNCTIONS **/
export function validateRequest<T>(schema: z.ZodType<T>, payload: any) {
  try {
    return schema.parse(payload);
  } catch (e: any) {
    logger.error("Validation error: %o", e);
    throw new ApiError(httpStatus.UNPROCESSABLE_ENTITY, e.message ?? "Validation error");
  }
}

export const PaginationSchema = z.object({
  page: z.coerce.number().optional(),
  limit: z.coerce.number().optional(),
  search_text: z.string().optional(),
  start_date: z.string().optional(),
  end_date: z.string().optional(),
});

export * as v1_validations from "./v1";
