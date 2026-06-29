import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";

const FX_RATES: Record<string, number> = {
  NGN_USD: 0.000625,
  NGN_GBP: 0.000500,
  NGN_EUR: 0.000575,
  NGN_GHS: 0.0078,
  NGN_KES: 0.084,
  NGN_ZAR: 0.012,
  USD_NGN: 1600,
  GBP_NGN: 2000,
  EUR_NGN: 1740,
};

export const convertCurrency = asyncHandler(async (req, res) => {
  const { amount, from = "NGN", to } = req.query;

  if (!amount || !to) {
    return res.status(400).json({ message: "amount and to parameters are required" });
  }

  const rate_key = `${from}_${to}`;
  const rate = FX_RATES[rate_key] ?? 1;
  const original_amount = Number(amount);
  const converted_amount = Math.round(original_amount * rate * 100) / 100;

  return res.status(httpStatus.OK).json({
    message: "success",
    original_amount,
    converted_amount,
    rate,
    from,
    to,
    timestamp: new Date().toISOString(),
  });
});
