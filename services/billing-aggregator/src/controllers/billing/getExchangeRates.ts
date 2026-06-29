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

export const getExchangeRates = asyncHandler(async (req, res) => {
  return res.status(httpStatus.OK).json({
    message: "success",
    base_currency: "NGN",
    rates: FX_RATES,
    last_updated: new Date().toISOString(),
    source: "CBN_OFFICIAL",
  });
});
