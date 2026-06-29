import * as wf from "@temporalio/workflow";
import {
  ILookupFromSwitchWorkflowInput,
  IPutPartyResponse,
} from "../types/workflow";
import * as activites from "../activities";
import { IMojaloopError } from "../types";

export const lookup_party_info_workflow_response = wf.defineSignal<
  [IPutPartyResponse]
>("lookup_party_info_workflow_response");

export const lookup_party_info_workflow_error_response = wf.defineSignal<
  [IMojaloopError]
>("lookup_party_info_workflow_error_response");

export async function lookup_party_info_workflow({
  fsp_id,
  id_type,
  identifier,
  destination,
}: ILookupFromSwitchWorkflowInput): Promise<IPutPartyResponse> {
  try {
    console.log(`Starting workflow for lookup_party_info ${identifier}`);

    let result: IPutPartyResponse;

    const { lookup_party } = wf.proxyActivities<typeof activites>({
      retry: {
        initialInterval: "1 second", // amount of time that must elapse before the first retry occurs.
        maximumInterval: "1 minute", // maximum interval between retries.
        backoffCoefficient: 2, // how much the retry interval increases.
        maximumAttempts: 3,
      },
      startToCloseTimeout: "3 minute", // maximum time allowed for a single Activity Task Execution.
    });

    wf.setHandler(lookup_party_info_workflow_response, (input) => {
      result = input;
    });

    wf.setHandler(lookup_party_info_workflow_error_response, (input) => {
      throw wf.ApplicationFailure.nonRetryable(
        input.errorInformation.errorDescription
      );
    });

    await lookup_party(fsp_id, id_type, identifier, destination);

    await wf.condition(() => Boolean(result));

    return result!;
  } catch (err) {
    if (wf.isCancellation(err)) {
      console.log("Workflow cancelled");
      // Cleanup logic must be in a nonCancellable scope
      // If we'd run cleanup outside of a nonCancellable scope it would've been cancelled
      // before being started because the Workflow's root scope is cancelled.
      // await CancellationScope.nonCancellable(() => cleanup(url));
    }
    throw err; // <-- Fail the Workflow
  }
}
