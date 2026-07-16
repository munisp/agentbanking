import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";

const TAX_JURISDICTIONS: Record<string, { vat: number; wht: number; stamp: number }> = {
  NG_FEDERAL: { vat: 0.075, wht: 0.10, stamp: 0.005 },
  NG_LAGOS: { vat: 0.075, wht: 0.10, stamp: 0.005 },
  GH_ACCRA: { vat: 0.125, wht: 0.08, stamp: 0.005 },
  KE_NAIROBI: { vat: 0.16, wht: 0.05, stamp: 0.002 },
};

export const calculateTax = asyncHandler(async (req, res) => {
  const { amount, jurisdiction = "NG_FEDERAL", transaction_type } = req.query;

  if (!amount) return res.status(400).json({ message: "amount is required" });

  const gross_amount = Number(amount);
  const tax = TAX_JURISDICTIONS[jurisdiction as string] ?? TAX_JURISDICTIONS.NG_FEDERAL;

  const vat_amount = gross_amount * tax.vat;
  const wht_amount = gross_amount * tax.wht;
  const stamp_duty = gross_amount >= 10000 ? tax.stamp * gross_amount : 0;
  const net_amount = gross_amount + vat_amount - wht_amount;

  return res.status(httpStatus.OK).json({
    message: "success",
    gross_amount,
    vat_amount,
    wht_amount,
    stamp_duty,
    net_amount,
    jurisdiction,
    transaction_type,
  });
});
