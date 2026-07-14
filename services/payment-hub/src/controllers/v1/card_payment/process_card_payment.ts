import httpStatus from "http-status";
import { asyncHandler } from "../../../middlewares/async";
import { validateRequest } from "../../../validations";
import { ProcessCardPaymentSchema } from "../../../validations/v1/card_payment";
import { AppSwitchEnum } from "../../../utils/enums";
import { LuxConnectorApiClient } from "../../../lib/LuxConnectorApiClient";
import { EMVStandardResponse } from "../../../types/card_payment";
import ApiError from "../../../utils/ApiError";
import logger from "../../../config/logger.config";

export const process_card_payment = asyncHandler(async (req, res) => {
  try {
    const payload = validateRequest(ProcessCardPaymentSchema, req.body);

    const processor = req.context.switch_name;

    let paymentResponse: EMVStandardResponse | null = null;

    switch (processor) {
      case AppSwitchEnum.lux:
        paymentResponse = await LuxConnectorApiClient.getInstance().process_card_payment(payload);
        break;
      default:
        throw new ApiError(httpStatus.NOT_IMPLEMENTED, "Invalid card processor selected.");
    }

    return res.status(httpStatus.OK).json(paymentResponse);
  } catch (e: any) {
    logger.error(`Failed to process card payment. ${JSON.stringify(e)}`);
    return res.status(httpStatus.INTERNAL_SERVER_ERROR).json({
      status: "Error",
      message: "Failed to process card payment.",
    });
  }
});
