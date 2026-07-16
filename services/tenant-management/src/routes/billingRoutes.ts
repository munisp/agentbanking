import { Router } from "express";
import httpStatus from "http-status";
import { asyncHandler } from "../middlewares/async";
import { billingService } from "../services/billingService";
import { tenantRepository } from "../repositories/tenantRepository";

const router = Router();

router.get(
  "/",
  asyncHandler(async (req, res) => {
    const tenantId = req.headers["x-tenant-id"] as string;
    const billing_info = await billingService.getBillingInfo(tenantId);
    return res.status(httpStatus.OK).json({ billing_info });
  })
);

router.put(
  "/",
  asyncHandler(async (req, res) => {
    const tenantId = req.headers["x-tenant-id"] as string;
    const { plan, billingPeriod } = req.body;
    const billing_profile = await billingService.createBillingProfile(tenantId, plan, billingPeriod);
    await tenantRepository.updateTenant(tenantId, { plan, billingPeriod });
    return res.status(httpStatus.OK).json({ billing_profile });
  })
);

export default router;
