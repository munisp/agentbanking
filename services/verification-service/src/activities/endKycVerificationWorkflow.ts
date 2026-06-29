import { AppDataSource } from "../database/dataSource";
import { KycVerificationWorkflowEntity } from "../entity/KycVerificationWorkflowEntity";
import { NonRetriableApplicationError } from "../middlewares/error";
import { VerificationWorkflowStatus } from "../utils/enums";

/**
 * End a runnning kyc workflow by updating its status to completed/failed
 * @param client_app_user_id Client app user identifier
 * @param status Status to update workflow to
 * @param score Final verification score
 */
export async function endKycVerificationWorkflow(
  client_app_user_id: string,
  status: VerificationWorkflowStatus.COMPLETED | VerificationWorkflowStatus.FAILED,
  score?: number,
  has_sent_webhook: boolean = false
) {
  const kycVerification = await AppDataSource.manager.findOne(KycVerificationWorkflowEntity, {
    where: {
      client_app_user_id,
      status: VerificationWorkflowStatus.RUNNING,
    },
  });

  if (!kycVerification) throw new NonRetriableApplicationError("Invalid verification session.");

  kycVerification.status = status;
  kycVerification.has_sent_webhook = has_sent_webhook;
  if (score) kycVerification.score = score;

  await AppDataSource.manager.save(kycVerification);
}
