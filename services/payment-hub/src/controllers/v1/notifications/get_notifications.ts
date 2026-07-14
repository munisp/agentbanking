import httpStatus from "http-status";
import { VfdConnectorApiClient } from "../../../lib/VfdConnectorApiClient";
import { asyncHandler } from "../../../middlewares/async";
import ApiError from "../../../utils/ApiError";
import { AppSwitchEnum } from "../../../utils/enums";
import { LuxConnectorApiClient } from "../../../lib/LuxConnectorApiClient";

export const get_notifications = asyncHandler(async (req, res) => {
  const switch_name = req.context.switch_name;

  if (switch_name === AppSwitchEnum.vfd) {
    const result = await VfdConnectorApiClient.instance().get_notifications(
      req.query,
      req.context.tenant_name
    );

    res.json(result);
    return;
  } else if (switch_name === AppSwitchEnum.lux) {
    const result = await LuxConnectorApiClient.getInstance().get_notifications(
      req.query,
      req.context.tenant_name
    );

    res.json(result);
    return;
  }

  throw new ApiError(httpStatus.BAD_REQUEST, "Unsupported Ams");
});
