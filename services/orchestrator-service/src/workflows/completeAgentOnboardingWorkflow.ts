import { ApplicationFailure, proxyActivities } from "@temporalio/workflow";
import * as activities from "../activities";
import { ICompleteAgentOnboardingWorkflow } from "../types/workflows";

export async function completeAgentOnboardingWorkflow(
  args: ICompleteAgentOnboardingWorkflow,
): Promise<null> {
  const { createAgentAccountProfile, markAgentKycComplete } = proxyActivities<
    typeof activities
  >({
    retry: {
      initialInterval: "1s",
      maximumInterval: "1m",
      backoffCoefficient: 2,
      maximumAttempts: 3,
      nonRetryableErrorTypes: ["NonRetriableApplicationError"],
    },
    startToCloseTimeout: "1m",
  });

  try {
    // 01. Get agent service to fetch profile
    // Note: Agent profile already exists, created during agent creation workflow

    // 02. Create agent account
    await createAgentAccountProfile({
      name: `${args.metadata.first_name || ""} ${args.metadata.last_name || ""}`.trim(),
      keycloak_id: args.metadata.keycloak_id,
      tenant_id: args.metadata.tenant_id,
      ledger_id: "1",
    });

    // 03. Mark KYC status complete in agent service
    await markAgentKycComplete(
      args.metadata.tenant_id,
      args.metadata.keycloak_id,
    );

    return null;
  } catch (e: any) {
    throw new ApplicationFailure(e.message);
  }
}
