import { WorkflowClient } from "@temporalio/client";
import createLogger from "../config/logger.config";
import { PartyIdTypeEnum } from "../utils/enums";
import { extract_name_form_path } from "../utils/helpers";
import { regClientOpRepo } from "../repos/regClientOpRepo";
import { register_fsp_client_workflow_response } from "./register_fsp_client";

const logger = createLogger(extract_name_form_path(__filename));

export const closeRegOpWorkflow = async (
  identifier: string,
  identifier_type: PartyIdTypeEnum,
  fspId: string,
  client: WorkflowClient
) => {
  try {
    logger.info("closeRegOpWorkflow");

    const op = await regClientOpRepo.getByPutResponse({
      identifier,
      identifier_type,
      fspId,
    });

    logger.info(`Operation ${JSON.stringify(op)}`);

    if (!op) {
      throw new Error("Reg operation does not exist");
    }

    const workflowId = op.workflow_id;

    const handle = client.getHandle(workflowId);

    logger.info("send signal to reg workflow");
    await handle.signal(register_fsp_client_workflow_response, {
      fspId,
      identifier,
      identifier_type,
    });

    logger.info("delete operation");
    await regClientOpRepo.deleteIfExist({
      identifier,
      identifier_type,
      fsp_id: fspId,
    });
  } catch (err) {
    logger.error("Failed to exit reg op Workflow", err);
  }
};
