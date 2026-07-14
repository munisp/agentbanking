import { uuid4 } from "@temporalio/workflow";
import { asyncHandler } from "../../middlewares/async";
import { LookupSchema, validateRequest } from "../../validations";
import { lookupOpRepo } from "../../repos/lookupRepo";
import { extract_name_form_path, runWorkflow } from "../../utils/helpers";
import {
  ILookupFromSwitchWorkflowInput,
  IPutPartyResponse,
} from "../../types/workflow";
import { lookup_party_info_workflow } from "../../workflows/lookup_party_info";
import ApiError from "../../utils/ApiError";
import httpStatus from "http-status";
import createLogger from "../../config/logger.config";
import { LookupResourceEnum } from "../../utils/enums";

const logger = createLogger(extract_name_form_path(__filename));

export const lookup_party = asyncHandler(async (req, res) => {
  const { tenant_name, identifier, identifier_type } = validateRequest(
    LookupSchema,
    req.body
  );

  const workflowId = uuid4();

  // store workflow Id in db
  await lookupOpRepo.createRecord(
    workflowId,
    identifier,
    identifier_type,
    LookupResourceEnum.party
  );

  // Run the workflow
  const result = await runWorkflow<
    ILookupFromSwitchWorkflowInput,
    IPutPartyResponse
  >(lookup_party_info_workflow, {
    args: {
      fsp_id: tenant_name,
      id_type: identifier_type,
      identifier,
      destination: req.headers["fspiop-destination"] as string | undefined,
    },
    workflowId,
  });

  if (result) {
    logger.info(`lookup is successful ${JSON.stringify(result)}`);
    res.setHeader("Content-Type", "application/json");
    await lookupOpRepo.deleteIfExist({ workflow_id: workflowId });
    return res.json({ success: true, data: result });
  }

  throw new ApiError(
    httpStatus.INTERNAL_SERVER_ERROR,
    "Failed to lookup accout"
  );
});
