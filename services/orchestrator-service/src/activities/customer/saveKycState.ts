import { userService } from "../../services/userService";

export async function saveKycState(kyc_url: string, tenant_id: string, keycloak_id: string) {
  return userService.saveKycState(kyc_url, tenant_id, keycloak_id);
}
