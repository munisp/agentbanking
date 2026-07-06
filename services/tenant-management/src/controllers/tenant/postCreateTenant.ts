import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";
import { PostCreateTenantSchema, validateRequest } from "../../validations";
import { tenantRepository } from "../../repositories/tenantRepository";
import { BillingPeriod, BillingPlan } from "../../utils/enums";
import logger from "../../config/logger.config";

export const postCreateTenant = asyncHandler(async (req, res) => {
  const payload = validateRequest(PostCreateTenantSchema, req.body);
  const tenantId = req.headers["x-tenant-id"] as string;

  try {
    const tenant = await tenantRepository.createTenant({ ...payload, tenantId });

    const plan = payload?.plan || BillingPlan.STANDARD;
    const billingPeriod = payload?.billingPeriod || BillingPeriod.MONTHLY;

    // If this call fails, the tenant row above is already committed with no
    // compensation — recovery works via retry since changeBillingPlan (billing-aggregator
    // side) is idempotent per tenantId, so a repeat PUT /billing call is safe.
    const billingProfile = await tenantRepository.createBillingProfile(tenantId, plan, billingPeriod);

    return res.status(httpStatus.CREATED).json({
      status: "success",
      tenant,
      billingProfile,
    });
  } catch (error: any) {
    logger.error("[postCreateTenant] Request failed", {
      tenantId,
      errorMessage: error?.message,
      stack: error?.stack,
    });
    throw error;
  }
});
