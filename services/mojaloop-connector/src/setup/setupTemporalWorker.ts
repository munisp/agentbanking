import { NativeConnection, Worker } from "@temporalio/worker";
import * as activities from "../activities";
import { TEMPORAL_ADDRESS, TEMPORAL_NAMESPACE, TEMPORAL_TASK_QUEUE } from "../utils/constants";
import createLogger from "../config/logger.config";
import { extract_name_form_path } from "../utils/helpers";
import path from "path";

const logger = createLogger(extract_name_form_path(__filename));

export async function setupTemporalWorker() {
  try {
    const worker = await Worker.create({
      workflowsPath: path.resolve("./src/workflows"),
      activities,
      namespace: TEMPORAL_NAMESPACE,
      taskQueue: TEMPORAL_TASK_QUEUE,
      connection: await NativeConnection.connect({
        address: TEMPORAL_ADDRESS,
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
