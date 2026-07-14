import httpStatus from "http-status";
import { z } from "zod";
import { asyncHandler } from "../../middlewares/async";
import { getPaymentGateway } from "../../gateways";
import { validateRequest } from "../../validations";

const Schema = z.object({
  amount: z.number().min(100000),
  email: z.string().email(),
});

export const initializePayment = asyncHandler(async (req, res) => {
  const tenant_id = req.headers["x-tenant-id"] as string;
  const input = validateRequest(Schema, req.body);

  const reference = `54L-${tenant_id}-${Date.now()}`;
  const callback_url = `${process.env.APP_BASE_URL ?? "https://54agent.upi.dev"}/billing/credits?ref=${reference}`;

  const gateway = getPaymentGateway();
  const result = await gateway.initialize({
    amount: input.amount,
    email: input.email,
    reference,
    callback_url,
    metadata: { tenant_id, source: "credit_topup" },
  });

  return res.status(httpStatus.OK).json({ message: "success", ...result });
});
