import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";

export const getInvoices = asyncHandler(async (req, res) => {
  return res.status(httpStatus.OK).json({ message: "success", invoices: [] });
});
