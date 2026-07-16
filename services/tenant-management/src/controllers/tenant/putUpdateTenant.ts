import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";
import { PutUpdateTenantSchema, validateRequest } from "../../validations";
import { tenantRepository } from "../../repositories/tenantRepository";

export const putUpdateTenant = asyncHandler(async (req, res) => {
  const payload = validateRequest(PutUpdateTenantSchema, req.body);

  const tenantId = req.params.tenant_id;

  const tenant = await tenantRepository.updateTenant(tenantId, { ...payload, tenantId });


  return res.status(httpStatus.OK).json({
    status: "success",
    tenant,
  });
});
