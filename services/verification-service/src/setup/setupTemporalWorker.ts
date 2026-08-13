import { NativeConnection, Worker } from "@temporalio/worker";
import * as activities from "../activities";
import logger from "../config/logger.config";
import { prodEnvironment, readEnv } from "../config/readEnv.config";
import { isKycSimulationMode } from "../utils/kycSimulationMode";

// Simulated KYC verification activities with no real provider behind them.
// They are only registered on the worker when KYC simulation mode is enabled
// (non-production). Outside simulation mode any workflow attempting to
// schedule them fails closed.
const SIMULATION_ONLY_ACTIVITIES = [
  "defaultVerifyFace",
  "defaultVerifyData",
  "validateLivenessProof",
  "verifyDocument",
] as const;

export async function setupTemporalWorker() {
  try {
    if (prodEnvironment() && process.env.KYC_SIMULATION_MODE === "true") {
      throw new Error(
        "KYC_SIMULATION_MODE must never be enabled in production; refusing to start the KYC worker.",
      );
    }

    const registeredActivities: Record<string, unknown> = { ...activities };

    if (!isKycSimulationMode()) {
      for (const name of SIMULATION_ONLY_ACTIVITIES) {
        delete registeredActivities[name];
      }
      logger.warn(
        "KYC simulation mode disabled: simulated verification activities " +
          `( ${SIMULATION_ONLY_ACTIVITIES.join(", ")} ) are not registered on this worker.`,
      );
    }

    const worker = await Worker.create({
      workflowsPath: require.resolve("../workflows"),
      activities: registeredActivities as typeof activities,
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
