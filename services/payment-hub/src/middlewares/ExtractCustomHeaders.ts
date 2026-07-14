import httpStatus from "http-status";
import logger from "../config/logger.config";
import { tenantRepository } from "../repositories/tenantRepo";
import ApiError from "../utils/ApiError";
import { AppAmsEnum, AppSwitchEnum } from "../utils/enums";
import { v1_validations, validateRequest } from "../validations";
import { asyncHandler } from "./async";

export const extract_custom_headers = asyncHandler(async (req, _, next) => {
  const payload = validateRequest(v1_validations.HeaderSchema, req.headers);

  const tenant_name = payload["x-tenant-name"] as string;
  const switch_name = payload["x-switch-name"] as AppSwitchEnum;
  const ams_name = payload["x-ams-name"] as AppAmsEnum;

  logger.info(
    `Extracted request context tenant=${tenant_name} switch=${switch_name} ams=${ams_name} path=${req.originalUrl}`,
  );

  let tenantExists = false;
  try {
    tenantExists = await tenantRepository.repo.existsBy({
      dfsp_id: tenant_name,
    });
  } catch (error: any) {
    logger.error(
      `Tenant lookup failed tenant=${tenant_name} path=${req.originalUrl} error=${error?.message || error}`,
    );
    throw error;
  }

  if (!tenantExists) {
    logger.warn(
      `Tenant not found tenant=${tenant_name} path=${req.originalUrl}`,
    );
    throw new ApiError(httpStatus.NOT_FOUND, "Tenant not found");
  }

  req.context = { tenant_name, switch_name, ams_name };

  next();
});
