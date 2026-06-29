import { agentService } from "../../services/agentService";
import { IAgentProfilePayload } from "../../types/agent";

export async function createAgentProfile(payload: IAgentProfilePayload) {
  await agentService.createAgentProfile(payload);
}
