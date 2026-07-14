import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";
import ApiError from "../../utils/ApiError";
import createLogger from "../../config/logger.config";
import { extract_name_form_path } from "../../utils/helpers";
import { PutParticipantCallbackSchema, validateRequest } from "../../validations";
import { closeRegOpWorkflow } from "../../workflows/close_reg_op";
import { closeParticipantLookupWorkflow } from "../../workflows/close_participant_lookup";
import { setupTemporalClient } from "../../setup/setupTemporalClient";

const logger = createLogger(extract_name_form_path(__filename));

export const put_participant = asyncHandler(async (req, res) => {
  const client = await setupTemporalClient();

  try {
    const source = req.headers["fspiop-destination"] as string;
    logger.info(`Headers ${JSON.stringify(req.headers)} ${source}`);

    if (!source) {
      throw new ApiError(httpStatus.BAD_REQUEST, "Source header not found");
    }

    const payload = {
      ...req.params,
      ...req.body,
    };

    logger.info(`Payload: ${JSON.stringify(payload)} Destination ${source}`);

    if (!payload.fspId) {
      payload.fspId = source;
    }

    const { identifier, identifier_type, fspId } = validateRequest(PutParticipantCallbackSchema, payload);

    if (!fspId) {
      throw new ApiError(httpStatus.BAD_REQUEST, "Invalid request");
    }

    await closeRegOpWorkflow(identifier, identifier_type, fspId, client);
    await closeParticipantLookupWorkflow(identifier, identifier_type, fspId, client);

    return res.json({});
  } catch (e: any) {
    logger.error(JSON.stringify(e));
    throw e;
  }
});
