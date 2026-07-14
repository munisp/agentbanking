import { adminService } from "../../services/adminService";

export async function saveAdminKycState(
  kyc_url: string,
  tenant_id: string,
  keycloak_id: string,
) {
  return adminService.saveAdminKycState(kyc_url, tenant_id, keycloak_id);
}
