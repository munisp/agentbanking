import httpStatus from "http-status";
import { getWorkflowErrorMessage } from ".";
import logger from "../config/logger.config";
import { readEnv } from "../config/readEnv.config";
import { ApiError } from "../middlewares/error";
import { setupTemporalClient } from "../setup/setupTemporalClient";
import { UnwrapPromise, WorkflowOptions } from "../types/workflow";

/**
 * Generic Workflow Runner
 * @param {Function} workflowFn - The workflow function to execute.
 * @param {WorkflowOptions<T>} options - Workflow options.
 */
export async function workflowRunner<T, K>(
  workflowFn: (args: T) => Promise<UnwrapPromise<K>>,
  { args, workflowId, defaultErrorMessage, isDaemon }: WorkflowOptions<T>,
): Promise<UnwrapPromise<K> | void> {
  const client = await setupTemporalClient();

  try {
    // Try to get existing workflow handle first
    let handle;
    let workflowExists = false;
    
    try {
      handle = client.getHandle(workflowId);
      // Check if workflow is already running - this can throw if workflow doesn't exist
      const description = await handle.describe();
      workflowExists = true;
      
      if (description.status.name === 'RUNNING') {
        logger.info(
          `Workflow ${workflowId} is already running with RunID ${description.runId}, reusing existing workflow`,
        );
        
        // Return existing handle instead of trying to create a new one
        if (isDaemon) {
          handle.result(); // trigger in background, don't await
          return;
        }
        
        const result = await handle.result();
        return result;
      } else {
        logger.warn(
          `Workflow ${workflowId} exists but is not RUNNING (status: ${description.status.name}). Will attempt to start new workflow.`,
        );
      }
    } catch (error: any) {
      // Workflow doesn't exist in Temporal, proceed to create it
      // This can happen when describe() is called on a non-existent workflow
      logger.info(`Workflow ${workflowId} not found in Temporal (${error.message}), creating new workflow`);
    }

    // Start new workflow
    try {
      handle = await client.start(workflowFn, {
        args: [args],
        taskQueue: readEnv("TEMPORAL_TASK_QUEUE"),
        workflowId,
      });

      logger.info(
        `Started workflow ${handle.workflowId} with RunID ${handle.firstExecutionRunId}`,
      );
    } catch (startError: any) {
      logger.error(`Failed to start workflow ${workflowId}:`, {
        error: startError.message,
        code: startError.code,
        details: startError.details,
      });
      throw startError;
    }

    if (isDaemon) {
      handle.result(); // trigger in background, don't await
      return;
    }

    const result = await handle.result();

    return result;
  } catch (e: any) {
    const message = getWorkflowErrorMessage(
      e,
      defaultErrorMessage || "Workflow execution failed.",
    );
    logger.error(`Workflow execution failed for ${workflowId}:`, message);
    logger.error(`Error type: ${e?.name}, Message: ${e?.message}`);
    logger.error(`Full error object:`, JSON.stringify(e, Object.getOwnPropertyNames(e), 2));
    throw new ApiError(
      httpStatus.INTERNAL_SERVER_ERROR,
      message,
      "VER-500-00",
      "verification-service",
    );
  }
}
