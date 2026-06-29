import { ICreateTenantPayload } from "../../types/tenant";
import { tenantService } from "../../services/tenantService";

export async function createTenant(payload: ICreateTenantPayload) {
  return tenantService.createTenant(payload);
}
