import { userService } from "../../services/userService";

export async function markCustomerKycComplete(tenant_id: string, keycloak_id: string) {
  return userService.markKycComplete(tenant_id, keycloak_id);
}
