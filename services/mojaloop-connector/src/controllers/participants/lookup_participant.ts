import { uuid4 } from "@temporalio/workflow";
import { asyncHandler } from "../../middlewares/async";
import { LookupSchema, validateRequest } from "../../validations";
import { lookupOpRepo } from "../../repos/lookupRepo";
import { extract_name_form_path, runWorkflow } from "../../utils/helpers";
import { ILookupFromSwitchWorkflowInput, IPutParticipantsResponse } from "../../types/workflow";
import ApiError from "../../utils/ApiError";
import httpStatus from "http-status";
import createLogger from "../../config/logger.config";
import { LookupResourceEnum } from "../../utils/enums";
import { lookup_participants_workflow } from "../../workflows";

const logger = createLogger(extract_name_form_path(__filename));

export const lookup_participants = asyncHandler(async (req, res) => {
  const { tenant_name, identifier, identifier_type } = validateRequest(LookupSchema, req.body);

  const workflowId = uuid4();

  // store workflow Id in db
  await lookupOpRepo.createRecord(workflowId, identifier, identifier_type, LookupResourceEnum.participants);

  // Run the workflow
  const result = await runWorkflow<ILookupFromSwitchWorkflowInput, IPutParticipantsResponse>(
    lookup_participants_workflow,
    {
      args: {
        fsp_id: tenant_name,
        id_type: identifier_type,
        identifier,
      },
      workflowId,
    }
  );

  if (result) {
    logger.info(`lookup is successful ${JSON.stringify(result)}`);
    return res.json({ success: true, data: result });
  }

  throw new ApiError(httpStatus.INTERNAL_SERVER_ERROR, "Failed to lookup account");
});
