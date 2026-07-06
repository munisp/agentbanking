import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";
import { validateRequest, MarkPaidSchema } from "../../validations";
import { billingInvoiceRepository } from "../../repositories/billingInvoiceRepository";
import { ApiError } from "../../middlewares/error";

export const markPaid = asyncHandler(async (req, res) => {
  const { invoice_id: invoice_number } = req.params;
  const input = validateRequest(MarkPaidSchema, req.body);

  const invoice = await billingInvoiceRepository.markPaid(
    invoice_number,
    input.payment_ref,
    input.paid_at ? new Date(input.paid_at) : undefined
  );

  if (!invoice) {
    throw new ApiError(httpStatus.NOT_FOUND, `Invoice ${invoice_number} not found`);
  }

  return res.status(httpStatus.OK).json({ message: "success", invoice });
});
