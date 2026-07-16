import * as wf from "@temporalio/workflow";
import { IInitiateTransfer, IGetQuoteFromSwitchResponse } from "../types/workflow";
import * as activites from "../activities";
import { IMojaloopError } from "../types";

export const initiate_transfer_workflow_quote_response = wf.defineSignal<[IGetQuoteFromSwitchResponse]>(
  "initiate_transfer_workflow_quote_response"
);

export const initiate_transfer_workflow_error_signal = wf.defineSignal<[IMojaloopError]>(
  "initiate_transfer_workflow_error_signal"
);

export async function initiate_transfer_workflow({
  fsp_id,
  destination,
  payload,
  fees,
  hold_id,
}: IInitiateTransfer): Promise<void> {
  try {
    let quote_result: IGetQuoteFromSwitchResponse | null = null;

    const { initiate_quote, debit_payer, prepare_transfer } = wf.proxyActivities<typeof activites>({
      retry: {
        initialInterval: "1 second", // amount of time that must elapse before the first retry occurs.
        maximumInterval: "1 minute", // maximum interval between retries.
        backoffCoefficient: 2, // how much the retry interval increases.
        maximumAttempts: 2,
      },
      startToCloseTimeout: "1 minute", // maximum time allowed for a single Activity Task Execution.
    });

    wf.setHandler(initiate_transfer_workflow_quote_response, (input) => {
      quote_result = input;
    });

    wf.setHandler(initiate_transfer_workflow_error_signal, (input) => {
      throw wf.ApplicationFailure.nonRetryable(input.errorInformation.errorDescription);
    });

    await initiate_quote(fsp_id, destination, payload, fees, hold_id);

    const quoteArrived = await wf.condition(() => Boolean(quote_result), "30 seconds");

    if (!quoteArrived) {
      throw wf.ApplicationFailure.nonRetryable(
        "Quote response timeout: no callback received within 30 seconds"
      );
    }

    if (!quote_result) {
      throw new wf.ApplicationFailure("Quote is result is not defined");
    }

    quote_result = quote_result as IGetQuoteFromSwitchResponse;

    const post_transfer_data = {
      amount: payload.amount,
      condition: quote_result.condition,
      expiration: quote_result.expiration,
      ilpPacket: quote_result.ilpPacket,
      payeeFsp: destination,
      payerFsp: fsp_id,
      transferId: payload.transactionId,
      holdId: hold_id,
    };

    const debitResult = await debit_payer(payload.payer.partyIdInfo, post_transfer_data);

    if (!Boolean(debitResult)) {
      // failed to debit user: Exit - nothing to rollback
      throw new wf.ApplicationFailure("Debit failed");
    }

    // prepare transfer
    await prepare_transfer(post_transfer_data);
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
