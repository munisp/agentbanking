import * as wf from "@temporalio/workflow";
import {
  IPutParticipantResponse,
  IRegisterUserToSwitchWorkflowInput,
} from "../types/workflow";
import * as activites from "../activities";

export const register_fsp_client_workflow_response = wf.defineSignal<
  [IPutParticipantResponse]
>("register_fsp_client_workflow_response");

export async function register_fsp_client_workflow({
  fsp_id,
  id_type,
  identifier,
  currency,
}: IRegisterUserToSwitchWorkflowInput): Promise<IPutParticipantResponse> {
  try {
    console.log(`Starting workflow for register_fsp_client ${identifier}`);

    let result: IPutParticipantResponse;

    const { register_participant } = wf.proxyActivities<typeof activites>({
      retry: {
        initialInterval: "1 second", // amount of time that must elapse before the first retry occurs.
        maximumInterval: "1 minute", // maximum interval between retries.
        backoffCoefficient: 2, // how much the retry interval increases.
        maximumAttempts: 3,
      },
      startToCloseTimeout: "3 minute", // maximum time allowed for a single Activity Task Execution.
    });

    wf.setHandler(register_fsp_client_workflow_response, (input) => {
      result = input;
    });

    await register_participant(fsp_id, id_type, identifier, currency);

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
