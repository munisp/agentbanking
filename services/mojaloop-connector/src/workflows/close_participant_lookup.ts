import { WorkflowClient } from "@temporalio/client";
import { LookupResourceEnum, PartyIdTypeEnum } from "../utils/enums";
import { extract_name_form_path } from "../utils/helpers";
import { lookupOpRepo } from "../repos/lookupRepo";
import { lookup_participants_workflow_response } from "./lookup_participants";
import createLogger from "../config/logger.config";

const logger = createLogger(extract_name_form_path(__filename));

export const closeParticipantLookupWorkflow = async (
  identifier: string,
  identifier_type: PartyIdTypeEnum,
  fspId: string,
  client: WorkflowClient
) => {
  try {
    logger.info("closeParticipantLookupWorkflow");

    const op = await lookupOpRepo.getBySignature(
      identifier,
      identifier_type,
      LookupResourceEnum.participants
    );

    logger.info(`Operation ${JSON.stringify(op)}`);

    if (!op) {
      throw new Error("Lookup operation does not exist");
    }

    const workflowId = op.workflow_id;

    const handle = client.getHandle(workflowId);

    logger.info("send signal to lookup participant workflow");
    await handle.signal(lookup_participants_workflow_response, {
      fspId,
    });

    logger.info("delete operation");
    await lookupOpRepo.deleteIfExist({
      identifier,
      identifier_type,
      resource: LookupResourceEnum.participants,
    });
  } catch (err) {
    logger.error("Failed to exit lookup operation workflow", err);
  }
};
