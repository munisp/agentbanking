import httpStatus from "http-status";
import { tenantRepository } from "../../repositories/tenantRepository";
import { asyncHandler } from "../../middlewares/async";

export const getKeycloakPublicKey = asyncHandler(async (req, res) => {
  const tenant = await tenantRepository.findOne(req.params.tenant_id);

  return res.status(httpStatus.OK).json({
    message: "success",
    public_rsa_key: (tenant?.feature_flags.find((flag) => flag.name == "auth")?.config as any)
      ?.public_rsa_key,
  });
});
