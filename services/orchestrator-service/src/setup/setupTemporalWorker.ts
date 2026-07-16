import { NativeConnection, Worker } from "@temporalio/worker";
import * as activities from "../activities";
import logger from "../config/logger.config";
import { readEnv } from "../config/readEnv.config";

export async function setupTemporalWorker() {
  try {
    const worker = await Worker.create({
      workflowsPath: require.resolve("../workflows"),
      activities,
      namespace: readEnv("TEMPORAL_NAMESPACE"),
      taskQueue: readEnv("TEMPORAL_TASK_QUEUE"),
      connection: await NativeConnection.connect({
        address: readEnv("TEMPORAL_ADDRESS"),
      }),
    });

    await worker.run();
    return worker;
  } catch (e: any) {
    logger.error("Failed to start Temporal worker", e);
  }
}

export function stopTemporalWorker(worker?: Worker) {
  worker && worker.shutdown();
}
