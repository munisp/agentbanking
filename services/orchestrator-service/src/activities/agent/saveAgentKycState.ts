import { agentService } from "../../services/agentService";

export async function saveAgentKycState(
  kyc_url: string,
  tenant_id: string,
  keycloak_id: string,
) {
  await agentService.saveAgentKycState(kyc_url, tenant_id, keycloak_id);
}
