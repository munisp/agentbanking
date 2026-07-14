import { Connection, WorkflowClient } from "@temporalio/client";
import { TEMPORAL_ADDRESS, TEMPORAL_NAMESPACE } from "../utils/constants";

class TemporalClient {
  private static instance: TemporalClient;
  private clientInstance?: WorkflowClient;

  private constructor() {}

  public static async getInstance(): Promise<WorkflowClient> {
    if (!this.instance) {
      this.instance = new TemporalClient();
    }

    if (!this.instance.clientInstance) {
      const connection = await Connection.connect({
        address: TEMPORAL_ADDRESS,
        connectTimeout: 30000,
      });

      this.instance.clientInstance = new WorkflowClient({
        connection,
        namespace: TEMPORAL_NAMESPACE,
      });
    }

    return this.instance.clientInstance;
  }
}

export async function setupTemporalClient() {
  return TemporalClient.getInstance();
}
