import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";
import { AppDataSource } from "../../database/dataSource";
import { TenantBillingEntity } from "../../entity/TenantBillingEntity";
import { BillingPlan, BillingModel, BillingStatus } from "../../utils/enums";

/**
 * POST /billing/profiles — provision a tenant billing profile.
 * Backs the 54link_admin BankOnboarding call
 * POST /billing-orchestrator/v1/billing/profiles (via APISIX alias, wave-8).
 * Idempotent per tenant: an existing profile is updated, not duplicated.
 */
export const createBillingProfile = asyncHandler(async (req, res) => {
  const { tenant_id, pricing_model, monthly_fee, status } = req.body ?? {};
  if (!tenant_id || typeof tenant_id !== "string") {
    return res.status(httpStatus.BAD_REQUEST).json({ message: "tenant_id is required" });
  }

  const manager = AppDataSource.manager;
  let billing = await manager.findOne(TenantBillingEntity, { where: { tenant_id } });
  if (!billing) {
    billing = new TenantBillingEntity();
    billing.tenant_id = tenant_id;
  }

  billing.billing_model =
    pricing_model === "hybrid" ? BillingModel.HYBRID : BillingModel.SUBSCRIPTION;
  if (typeof monthly_fee === "number" && monthly_fee >= 0) {
    billing.subscription_config = {
      ...(billing.subscription_config ?? {}),
      perAgentFee: 0,
      perPosFee: 0,
      implementationFee: monthly_fee,
      billingCycle: "monthly",
    };
  }
  if (typeof status === "string" && status.toUpperCase() in BillingStatus) {
    billing.status = status.toUpperCase() as BillingStatus;
  }

  const saved = await manager.save(billing);

  return res.status(httpStatus.CREATED).json({
    profile: {
      id: saved.id,
      tenant_id: saved.tenant_id,
      billing_model: saved.billing_model,
      plan: saved.plan,
      status: saved.status,
      subscription_config: saved.subscription_config,
    },
  });
});
