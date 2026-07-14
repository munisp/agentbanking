import { proxyActivities } from "@temporalio/workflow";
import * as activities from "../activities";
import { z } from "zod";
import { PostInitializeVerificationValidationSchema } from "../validations/schemas";
import { ClientEntity } from "../entity/ClientEntity";
import { BusinessEntity } from "../entity/BusinessEntity";
import { BallerineWorkflow } from "../types/workflow";

export interface KybWorkflowArgs {
  payload: z.infer<typeof PostInitializeVerificationValidationSchema>;
  client: ClientEntity;
}

export interface KybWorkflowResult {
  business: BusinessEntity;
  workflow: BallerineWorkflow;
  url: string;
}
/**
 * Temporal workflow definition to create a ballerine kyb workflow.
 * Create or Retreives a business identity,
 * Initialize the ballerine kyb workflow and
 * keeps track of its state until its completion.
 * Finally, notifies client of kyb response using callback.
 * @param args
 * @returns
 */
export async function kybWorkflow(args: KybWorkflowArgs): Promise<KybWorkflowResult> {
  const {
    fetchBusiness,
    createBallerineWorkflow,
    saveVerificationWorkflow,
    checkVerificationStatus,
    getVerificationUrl,
  } = proxyActivities<typeof activities>({
    retry: {
      initialInterval: "1s",
      maximumAttempts: 3,
      nonRetryableErrorTypes: ["NonRetriableApplicationError"],
    },
    startToCloseTimeout: "1m",
  });

  // 01. Fetch business.
  const business = await fetchBusiness(args.payload, args.client);

  // 02. Check if business has in-complete workflow.
  await checkVerificationStatus(business.ballerine_business_id);

  // 03. Create workflow
  const workflow = await createBallerineWorkflow(args.payload, args.client, business.ballerine_business_id); // Need to add a subscription payload to this.

  // 04. Save workflow.
  await saveVerificationWorkflow(business.ballerine_business_id, workflow);

  // 04. Get verification url.
  const url = await getVerificationUrl(workflow.workflowRuntimeId, args.client.ballerine_customer_api_key);

  return { business, workflow, url };
}
