import { agentService } from "../../services/agentService";

export async function markAgentKycComplete(
  tenant_id: string,
  keycloak_id: string,
) {
  await agentService.markKycComplete(tenant_id, keycloak_id);
}
