import { adminService } from "../../services/adminService";

export async function markAdminKycComplete(tenant_id: string, keycloak_id: string) {
  return adminService.markKycComplete(tenant_id, keycloak_id);
}
