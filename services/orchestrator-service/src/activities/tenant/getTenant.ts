import { tenantService } from "../../services/tenantService";

export async function getTenant(tenant_id: string) {
  return tenantService.getTenant(tenant_id);
}
