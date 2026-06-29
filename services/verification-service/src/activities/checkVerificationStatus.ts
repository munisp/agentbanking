import { prodEnvironment } from "../config/readEnv.config";
import { AppDataSource } from "../database/dataSource";
import { BallerineVerificationWorkflowEntity } from "../entity/BallerineVerificationWorkflowEntity";
import { NonRetriableApplicationError } from "../middlewares/error";
import { VerificationWorkflowStatus } from "../utils/enums";

/**
 * Ensure that the business doesn't already have a running verification workflow.
 * @param ballerineBusinessId
 */
export async function checkVerificationStatus(ballerineBusinessId: string) {
  const verificationWorkflow = await AppDataSource.manager.findOne(BallerineVerificationWorkflowEntity, {
    where: {
      ballerine_business_id: ballerineBusinessId,
    },
  });

  if (prodEnvironment()) {
    if (verificationWorkflow?.status == VerificationWorkflowStatus.RUNNING)
      throw new NonRetriableApplicationError("Verification workflow already running.");
  }
}
