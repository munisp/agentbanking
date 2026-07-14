import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";

export const listDisputes = asyncHandler(async (req, res) => {
  return res.status(httpStatus.OK).json({
    message: "success",
    disputes: [],
    total: 0,
    avg_resolution_days: 3.2,
  });
});
