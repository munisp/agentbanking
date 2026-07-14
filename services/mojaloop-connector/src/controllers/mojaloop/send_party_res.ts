import createLogger from "../../config/logger.config";
import { MojaloopApiClient } from "../../lib/MojaloopApiClient";
import { asyncHandler } from "../../middlewares/async";
import { extract_name_form_path } from "../../utils/helpers";
import { SendLookupResponseToMojaloopSchema, validateRequest } from "../../validations";

const logger = createLogger(extract_name_form_path(__filename));

export const send_party_res_to_mojaloop = asyncHandler(async (req, res) => {
  logger.info(`send_party_res_to_mojaloop ${JSON.stringify(req.body)}`);

  const { identifier, identifier_type, fspId, response, destination } = validateRequest(
    SendLookupResponseToMojaloopSchema,
    req.body
  );

  await MojaloopApiClient.getInstance().send_party_res(
    response,
    fspId,
    identifier,
    identifier_type,
    destination
  );

  return res.json({});
});
