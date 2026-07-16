import { ApplicationFailure, proxyActivities } from "@temporalio/workflow";
import * as activities from "../activities";
import { ICompleteCustomerOnboardingWorkflow } from "../types/workflows";

export async function completeCustomerOnboardingWorkflow(
  args: ICompleteCustomerOnboardingWorkflow,
): Promise<null> {
  const {
    createAccountProfile,
    getUserProfile,
    markCustomerKycComplete,
    markAdminKycComplete,
  } = proxyActivities<typeof activities>({
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
    if (args.metadata.is_admin) {
      // 01. Mark Admin KYC status complete
      await markAdminKycComplete(
        args.metadata.tenant_id,
        args.metadata.keycloak_id,
      );
    } else {
      // 01. Get user details
      const user = await getUserProfile(
        args.metadata.tenant_id,
        args.metadata.keycloak_id,
      );

      // 02. Create user account
      await createAccountProfile({
        name: user.name || user.first_name + " " + user.last_name,
        keycloak_id: args.metadata.keycloak_id,
        tenant_id: user.tenant_id,
        ledger_id: "1",
      });

      // 03. Mark KYC status complete
      await markCustomerKycComplete(
        args.metadata.tenant_id,
        args.metadata.keycloak_id,
      );
    }

    return null;
  } catch (e: any) {
    throw new ApplicationFailure(e.message);
  }
}
