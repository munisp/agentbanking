import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";
import { GLOBAL_FEATURES } from "../../utils/features";

export const getGlobalFeatures = asyncHandler(async (req, res) => {
  return res.status(httpStatus.OK).json({
    message: "success",
    tenants: GLOBAL_FEATURES,
  });
});
