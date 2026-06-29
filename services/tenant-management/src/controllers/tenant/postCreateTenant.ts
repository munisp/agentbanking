import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";
import { PostCreateTenantSchema, validateRequest } from "../../validations";
import { tenantRepository } from "../../repositories/tenantRepository";


export const postCreateTenant = asyncHandler(async (req, res) => {
  const payload = validateRequest(PostCreateTenantSchema, req.body);

  const tenantId = req.headers["x-tenant-id"] as string;

  const tenant = await tenantRepository.createTenant({ ...payload, tenantId });
  const billingProfile = await tenantRepository.createBillingProfile(tenantId, payload?.plan || "basic");

  return res.status(httpStatus.CREATED).json({
    status: "success",
    tenant,
    billingProfile,
  });
});
