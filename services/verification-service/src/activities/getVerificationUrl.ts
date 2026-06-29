import { readEnv } from "../config/readEnv.config";
import { ballerineApiClient } from "../lib/BallerineApiClient";

export async function getVerificationUrl(workflowRuntimeId: string, apiKey: string): Promise<string> {
  const collectionFlowUrl = await ballerineApiClient.getCollectionFlowUrl(workflowRuntimeId, apiKey);

  return readEnv("KYB_COLLECTION_FLOW_BASE_URL") + "?" + collectionFlowUrl.split("?")[1];
}
