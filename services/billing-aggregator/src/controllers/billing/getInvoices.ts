import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";
import { billingInvoiceRepository, toInvoiceDto } from "../../repositories/billingInvoiceRepository";

export const getInvoices = asyncHandler(async (req, res) => {
  const tenant_id = req.headers["x-tenant-id"] as string;

  const invoices = await billingInvoiceRepository.findByTenant(tenant_id);

  return res.status(httpStatus.OK).json({ message: "success", invoices: invoices.map(toInvoiceDto) });
});
