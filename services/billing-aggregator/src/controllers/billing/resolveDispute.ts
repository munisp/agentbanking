import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";
import { validateRequest, ResolveDisputeSchema } from "../../validations";

export const resolveDispute = asyncHandler(async (req, res) => {
  const { dispute_id } = req.params;

  const input = validateRequest(ResolveDisputeSchema, req.body);

  return res.status(httpStatus.OK).json({
    message: "success",
    dispute_id,
    resolution: input.resolution,
    adjustment_amount: input.adjustment_amount,
    resolved_at: new Date().toISOString(),
  });
});
