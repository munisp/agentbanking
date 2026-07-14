import { Connection, WorkflowClient } from "@temporalio/client";
import { readEnv } from "../config/readEnv.config";

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
        address: readEnv("TEMPORAL_ADDRESS"),
        connectTimeout: 30000,
      });

      this.instance.clientInstance = new WorkflowClient({
        connection,
        namespace: readEnv("TEMPORAL_NAMESPACE"),
      });
    }

    return this.instance.clientInstance;
  }
}

export async function setupTemporalClient() {
  return TemporalClient.getInstance();
}
