import { WorkflowExecutionAlreadyStartedError } from "@temporalio/client";
import logger from "../config/logger.config";
import { readEnv } from "../config/readEnv.config";
import { setupTemporalClient } from "../setup/setupTemporalClient";
import { UnwrapPromise } from "../types";
import { WorkflowOptions } from "../types/workflows";
import { timeoutWorkflow } from "./timeoutWorkflow";

/**
 * Generic Workflow Runner
 * @param {Function} workflowFn - The workflow function to execute.
 * @param {WorkflowOptions<T>} options - Workflow options.
 */
export async function workflowRunner<T, K>(
  workflowFn: (args: T) => Promise<UnwrapPromise<K>>,
  {
    args,
    workflowId,
    defaultErrorMessage,
    withTimeOut,
    timeOutFn,
  }: WorkflowOptions<T>,
): Promise<UnwrapPromise<K>> {
  const client = await setupTemporalClient();

  let handle;
  try {
    const handlePromise = client.start(workflowFn, {
      args: [args],
      taskQueue: readEnv("TEMPORAL_TASK_QUEUE"),
      workflowId,
    });

    handle =
      withTimeOut && timeOutFn
        ? await timeoutWorkflow(handlePromise, withTimeOut, timeOutFn)
        : await handlePromise;
  } catch (err) {
    // Deterministic workflowIds mean a retry targets an already-running
    // execution: resume it instead of failing or duplicating the workflow.
    if (err instanceof WorkflowExecutionAlreadyStartedError) {
      logger.info(
        `Workflow ${workflowId} already started — attaching to the existing execution (deterministic workflowId)`,
      );
      const existing = client.getHandle(workflowId);
      handle =
        withTimeOut && timeOutFn
          ? await timeoutWorkflow(
              Promise.resolve(existing),
              withTimeOut,
              timeOutFn,
            )
          : existing;
    } else {
      throw err;
    }
  }

  logger.info(
    `Started workflow ${handle.workflowId} with RunID ${handle.firstExecutionRunId}`,
  );

  const result = await handle.result();

  return result;
}
