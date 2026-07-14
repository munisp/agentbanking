import { readEnv } from "../config/readEnv.config";
import createLogger from "../config/logger.config";
import { TEMPORAL_TASK_QUEUE } from "./constants";
import { UnwrapPromise } from "../types";
import ApiError from "./ApiError";
import httpStatus from "http-status";
import { setupTemporalClient } from "../setup/setupTemporalClient";
import { WorkflowOptions } from "../types/workflow";

export const extract_name_form_path = (input: string) => {
  return input.split("/").pop() || "UnknownFile";
};

const logger = createLogger(extract_name_form_path(__filename));

export function devEnvironment() {
  return readEnv("NODE_ENV", "development") === "development";
}

export function parseAndValidateAmount(input: string): string {
  // Trim any unnecessary spaces from the input
  const trimmedInput = input.trim();

  // Try parsing the input as a float
  const parsedFloat = parseFloat(trimmedInput);
  if (isNaN(parsedFloat) || parsedFloat < 0) {
    throw new Error("Invalid amount format. Input must be a positive number.");
  }

  // Convert the parsed number back to a string with up to 3 decimal places
  const formattedAmount = parsedFloat.toFixed(3).replace(/(\.0*|(\.\d*?[1-9])0+)$/, "$2");

  // Validate the formatted amount against the regex pattern
  const regex = /^([0]|([1-9][0-9]{0,17}))([.][0-9]{0,3}[1-9])?$/;
  if (!regex.test(formattedAmount)) {
    throw new Error(
      "Invalid amount format. Ensure it matches the pattern: integer without leading zeros, or up to 3 decimal places with no trailing zeros."
    );
  }

  return formattedAmount;
}

/**
 * Generic Workflow Runner
 * @param {Function} workflowFn - The workflow function to execute.
 * @param {WorkflowOptions<T>} options - Workflow options.
 */
export async function runWorkflow<T, K>(
  workflowFn: (args: T) => Promise<UnwrapPromise<K>>,
  { args, workflowId, awaitResult = true }: WorkflowOptions<T>
): Promise<UnwrapPromise<K> | void> {
  const client = await setupTemporalClient();

  try {
    const handle = await client.start(workflowFn, {
      args: [args],
      taskQueue: TEMPORAL_TASK_QUEUE,
      workflowId,
    });

    logger.info(`Started Workflow ${handle.workflowId} with RunID ${handle.firstExecutionRunId}`);

    if (!awaitResult) {
      return;
    }

    const result = await handle.result();
    logger.info(`Workflow Result: ${JSON.stringify(result)}`);

    return result;
  } catch (e: any) {
    const message = e?.cause ?? "Workflow execution failed";
    logger.error(`Workflow execution failed with error:`, message);
    throw new ApiError(httpStatus.INTERNAL_SERVER_ERROR, message);
  }
}
