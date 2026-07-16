import { asyncHandler } from "../../../middlewares/async";
import { tenantRepository } from "../../../repositories/tenantRepo";
import { IGetTenantResponse, IPaginatedResponse } from "../../../types/api.response";
import { getPagination } from "../../../utils/query";
import { v1_validations, validateRequest } from "../../../validations";

export const fetch_tenants = asyncHandler<IPaginatedResponse<IGetTenantResponse>>(async (req, res) => {
  const payload = validateRequest(v1_validations.FetchTenantsSchema, req.query);

  const { limit, skip } = getPagination(payload);

  const [tenants, total] = await tenantRepository.paginatedFind({
    take: limit,
    skip,
    select: ["dfsp_id", "name", "id"],
    order: {
      created_at: "DESC",
    },
  });

  return res.json({ data: tenants, total });
});
