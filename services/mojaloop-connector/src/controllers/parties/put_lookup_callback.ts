import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";
import ApiError from "../../utils/ApiError";
import createLogger from "../../config/logger.config";
import { extract_name_form_path } from "../../utils/helpers";
import { PutPartyCallbackSchema, validateRequest } from "../../validations";
import { lookupOpRepo } from "../../repos/lookupRepo";
import { lookup_party_info_workflow_response } from "../../workflows";
import { LookupResourceEnum } from "../../utils/enums";
import { setupTemporalClient } from "../../setup/setupTemporalClient";

const logger = createLogger(extract_name_form_path(__filename));

export const put_lookup_party = asyncHandler(async (req, res) => {
  const client = await setupTemporalClient();

  try {
    const destination = req.headers["fspiop-destination"] as string;

    if (!destination) {
      throw new ApiError(httpStatus.BAD_REQUEST, "Source header not found");
    }

    const { identifier, identifier_type } = validateRequest(PutPartyCallbackSchema, req.params);

    logger.info(`identifier: ${identifier} identifier_type: ${identifier_type}`);

    // pull the workflow ID from DB and complete or cancel it
    logger.info(`Fetch Operation`);
    const op = await lookupOpRepo.getBySignature(identifier, identifier_type, LookupResourceEnum.party);
    logger.info(`Operation ${JSON.stringify(op)}`);

    if (!op) {
      throw new ApiError(httpStatus.INTERNAL_SERVER_ERROR, "Operation does not exist");
    }

    const workflowId = op.workflow_id;

    const handle = client.getHandle(workflowId);

    logger.info(`send signal ${JSON.stringify(req.body)}`);

    await handle.signal(lookup_party_info_workflow_response, req.body);

    logger.info("Delete operation");
    lookupOpRepo.deleteIfExist({
      identifier,
      identifier_type,
      resource: LookupResourceEnum.party,
    });

    return res.json({});
  } catch (e: any) {
    logger.error(JSON.stringify(e));
    throw e;
  }
});
