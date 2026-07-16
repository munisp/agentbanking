import createLogger from "../../config/logger.config";
import { asyncHandler } from "../../middlewares/async";
import { extract_name_form_path } from "../../utils/helpers";
import { PutParticipantCallbackSchema, validateRequest } from "../../validations";

const logger = createLogger(extract_name_form_path(__filename));

export const put_participant_error = asyncHandler(async (req, res) => {
  logger.info("put_participant_error");
  logger.info(JSON.stringify(req.headers));
  logger.info(JSON.stringify({ ...req.params, ...req.query, ...req.body }));

  const source = req.headers["fspiop-destination"] as string;
  logger.info(`Headers ${JSON.stringify(req.headers)} ${source}`);

  const payload = {
    ...req.params,
    ...req.body,
    fspId: source,
  };

  validateRequest(PutParticipantCallbackSchema, payload);

  return res.json({});
});
