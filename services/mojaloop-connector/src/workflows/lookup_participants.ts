import * as wf from "@temporalio/workflow";
import {
  ILookupFromSwitchWorkflowInput,
  IPutParticipantsResponse,
} from "../types/workflow";
import * as activites from "../activities";

export const lookup_participants_workflow_response = wf.defineSignal<
  [IPutParticipantsResponse]
>("lookup_participants_workflow_response");

export async function lookup_participants_workflow({
  fsp_id,
  id_type,
  identifier,
}: ILookupFromSwitchWorkflowInput): Promise<IPutParticipantsResponse> {
  try {
    console.log(`Starting workflow for lookup_party_info ${identifier}`);

    let result: IPutParticipantsResponse;

    const { lookup_participants } = wf.proxyActivities<typeof activites>({
      retry: {
        initialInterval: "1 second", // amount of time that must elapse before the first retry occurs.
        maximumInterval: "1 minute", // maximum interval between retries.
        backoffCoefficient: 2, // how much the retry interval increases.
        maximumAttempts: 2,
      },
      startToCloseTimeout: "1 minute", // maximum time allowed for a single Activity Task Execution.
    });

    wf.setHandler(lookup_participants_workflow_response, (input) => {
      result = input;
    });

    await lookup_participants(fsp_id, id_type, identifier);

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
