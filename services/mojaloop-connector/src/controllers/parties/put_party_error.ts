import httpStatus from "http-status";
import createLogger from "../../config/logger.config";
import { readEnv } from "../../config/readEnv.config";
import { asyncHandler } from "../../middlewares/async";
import { lookupOpRepo } from "../../repos/lookupRepo";
import ApiError from "../../utils/ApiError";
import { extract_name_form_path } from "../../utils/helpers";
import { PutLookupErrorCallback, validateRequest } from "../../validations";
import { lookup_party_info_workflow_error_response } from "../../workflows/lookup_party_info";
import { setupTemporalClient } from "../../setup/setupTemporalClient";

const logger = createLogger(extract_name_form_path(__filename));
const tenant = readEnv("TENANT_NAME", "ucard") as string;

export const put_party_error = asyncHandler(async (req, res) => {
  logger.info("put_party_error");
  logger.info(JSON.stringify(req.headers));

  const payload = validateRequest(PutLookupErrorCallback, {
    ...req.params,
    ...req.body,
  });

  logger.info(`error info: ${JSON.stringify(payload.errorInformation)}`);

  const source = req.headers["fspiop-destination"] as string;
  if (tenant !== source) {
    throw new ApiError(httpStatus.BAD_REQUEST, "Header mismatch");
  }

  const lookupOp = await lookupOpRepo.getOneWhere({
    where: {
      identifier: payload.identifier,
      identifier_type: payload.identifier_type,
    },
  });

  if (lookupOp) {
    const client = await setupTemporalClient();

    const handle = client.getHandle(lookupOp.workflow_id);

    try {
      await handle.signal(lookup_party_info_workflow_error_response, payload);
    } catch (error) {
      logger.error("Error signaling transction", error);
    }
  }

  return res.status(httpStatus.OK).send();
});
