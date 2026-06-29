import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";
import { validateRequest, GenerateCreditNoteSchema } from "../../validations";

export const generateCreditNote = asyncHandler(async (req, res) => {
  const { invoice_id } = req.params;
  const input = validateRequest(GenerateCreditNoteSchema, req.body);

  const credit_note = {
    credit_note_number: `CN-${Date.now().toString(36).toUpperCase()}`,
    invoice_id,
    amount: input.amount,
    reason: input.reason,
    status: "issued",
    issued_at: new Date().toISOString(),
  };

  return res.status(httpStatus.CREATED).json({ message: "success", credit_note });
});
