import logger from "../config/logger.config";
import { AppDataSource } from "../database/dataSource";
import { BallerineVerificationWorkflowEntity } from "../entity/BallerineVerificationWorkflowEntity";
import { BallerineWorkflow } from "../types/workflow";

/**
 * Upserts a business verification workflow.
 * @param ballerineBusinessId
 * @param payload
 * @returns void
 */
export async function saveVerificationWorkflow(ballerineBusinessId: string, payload: BallerineWorkflow) {
  logger.info(`Updating verification workflow for ${ballerineBusinessId}`);

  const verificationWorkflowRepository = AppDataSource.manager.getRepository(
    BallerineVerificationWorkflowEntity
  );

  await verificationWorkflowRepository.upsert(
    {
      ballerine_entity_id: payload.ballerineEntityId,
      ballerine_workflow_definition_id: payload.workflowDefinitionId,
      ballerine_workflow_runtime_id: payload.workflowRuntimeId,
      ballerine_business_id: ballerineBusinessId,
    },
    ["ballerine_business_id"]
  );

  logger.info("Verification workflow updated..");
}
