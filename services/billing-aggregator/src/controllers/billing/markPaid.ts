import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";
import { validateRequest, MarkPaidSchema } from "../../validations";

export const markPaid = asyncHandler(async (req, res) => {
  const { invoice_id } = req.params;
  const input = validateRequest(MarkPaidSchema, req.body);

  return res.status(httpStatus.OK).json({
    message: "success",
    invoice_id,
    status: "paid",
    payment_ref: input.payment_ref,
    paid_at: input.paid_at ?? new Date().toISOString(),
  });
});
