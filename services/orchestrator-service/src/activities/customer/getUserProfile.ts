import { userService } from "../../services/userService";

export async function getUserProfile(tenant_id: string, keycloak_id: string) {
  return userService.getUser(tenant_id, keycloak_id);
}
