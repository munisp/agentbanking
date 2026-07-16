import { asyncHandler } from "../../middlewares/async";
import { extract_name_form_path, runWorkflow } from "../../utils/helpers";
import {
  RegisterParticipantWithSwitchSchema as RegisterParticipantSchema,
  validateRequest,
} from "../../validations";
import { register_fsp_client_workflow } from "../../workflows";
import { PartyIdTypeEnum } from "../../utils/enums";
import { regClientOpRepo } from "../../repos/regClientOpRepo";
import { IPutParticipantResponse, IRegisterUserToSwitchWorkflowInput } from "../../types/workflow";
import createLogger from "../../config/logger.config";
import { uuid4 } from "@temporalio/workflow";
import ApiError from "../../utils/ApiError";
import httpStatus from "http-status";

const logger = createLogger(extract_name_form_path(__filename));

export const register_participant = asyncHandler(async (req, res) => {
  const { currency, identifier, identifier_type, tenant_name } = validateRequest(
    RegisterParticipantSchema,
    req.body
  );

  const workflowId = uuid4();

  // store workflow Id in db
  await regClientOpRepo.createRecord(workflowId, {
    identifier,
    identifier_type,
    fspId: tenant_name,
  });

  // Run the workflow
  const result = await runWorkflow<IRegisterUserToSwitchWorkflowInput, IPutParticipantResponse>(
    register_fsp_client_workflow,
    {
      args: {
        currency,
        fsp_id: tenant_name,
        id_type: identifier_type as PartyIdTypeEnum,
        identifier,
      },
      workflowId,
    }
  );

  if (result) {
    logger.info(`register participant is successful ${JSON.stringify(result)}`);
    return res.json({ success: true });
  }

  throw new ApiError(httpStatus.INTERNAL_SERVER_ERROR, "Failed to register particapant");
});
