import { AppDataSource } from "../database/dataSource";
import { TenantBillingEntity } from "../entity/TenantBillingEntity";
import { BillingPlan } from "../utils/enums";
import { ensureTenantAccount } from "../services/tigerbeetleService";

export class BillingRepository {
  private entity = TenantBillingEntity;
  private manager = AppDataSource.manager;

  async findOne(tenant_id: string) {
    return await this.manager.findOne(this.entity, {
      where: { tenant_id },
    });
  }

  async changeBillingPlan(tenant_id: string, plan: BillingPlan) {
    let billing = await this.findOne(tenant_id);

    if (!billing) {
      billing = new TenantBillingEntity();
      billing.tenant_id = tenant_id;
      billing.plan = plan || BillingPlan.STANDARD;
      const saved = await this.manager.save(billing);

      const tbAccountId = await ensureTenantAccount(saved.id, saved.currency ?? "NGN");
      if (tbAccountId) {
        saved.tigerbeetle_account_id = tbAccountId;
        await this.manager.save(saved);
      }
      return;
    }

    billing.plan = plan;
    await this.manager.save(billing);
  }

  async getBilling(tenant_id: string) {
    let billing = await this.findOne(tenant_id);
    if (!billing) {
      try {
        const created = new TenantBillingEntity();
        created.tenant_id = tenant_id;
        created.plan = BillingPlan.STANDARD;
        billing = await this.manager.save(created);
        try {
          const tbAccountId = await ensureTenantAccount(billing.id, billing.currency ?? "NGN");
          if (tbAccountId) {
            billing.tigerbeetle_account_id = tbAccountId;
            await this.manager.save(billing);
          }
        } catch (_) {
          // TigerBeetle unavailable — continue without account ID
        }
      } catch (err: any) {
        // Parallel requests race — another request already inserted; just re-fetch
        if (err?.driverError?.code === "23505" || err?.code === "23505") {
          billing = await this.findOne(tenant_id);
        } else {
          throw err;
        }
      }
    }
    return billing;
  }

  async updateCreditsBalance(tenant_id: string, amount: number, reference: string) {
    const billing = await this.getBilling(tenant_id);

    if (!billing) {
      throw new Error(`No billing record found for tenant ${tenant_id}`);
    }

    billing.credits_balance = Number(billing.credits_balance) + amount;
    billing.last_payment_date = new Date();
    billing.last_payment_reference = reference;
    billing.total_paid_ytd = Number(billing.total_paid_ytd) + amount;

    await this.manager.save(billing);
    return billing;
  }

  async applyGracePeriod(tenant_id: string, days: number, reason: string) {
    const billing = await this.getBilling(tenant_id);

    if (!billing) {
      throw new Error(`No billing record found for tenant ${tenant_id}`);
    }

    const grace_period_end = new Date();
    grace_period_end.setDate(grace_period_end.getDate() + days);

    billing.grace_period_end = grace_period_end;
    billing.grace_period_reason = reason;

    await this.manager.save(billing);
    return billing;
  }

  async getDunningStatus(tenant_id: string) {
    const billing = await this.getBilling(tenant_id);

    if (!billing) throw new Error(`No billing record found for tenant ${tenant_id}`);

    const now = new Date();
    const has_grace_period = billing.grace_period_end && billing.grace_period_end > now;
    const grace_days_remaining = has_grace_period
      ? Math.ceil((billing.grace_period_end!.getTime() - now.getTime()) / (1000 * 60 * 60 * 24))
      : 0;

    return {
      tenant_id,
      status: billing.status,
      credits_balance: billing.credits_balance,
      total_outstanding: billing.total_outstanding,
      last_payment_date: billing.last_payment_date,
      has_grace_period,
      grace_period_end: billing.grace_period_end,
      grace_period_reason: billing.grace_period_reason,
      grace_days_remaining,
      total_paid_ytd: billing.total_paid_ytd,
    };
  }

  async deductCredits(tenant_id: string, amount: number) {
    const billing = await this.getBilling(tenant_id);

    if (!billing) {
      throw new Error(`No billing record found for tenant ${tenant_id}`);
    }

    if (billing.credits_balance < amount) {
      throw new Error(`Insufficient credits. Balance: ${billing.credits_balance}, Required: ${amount}`);
    }

    billing.credits_balance = Number(billing.credits_balance) - amount;
    billing.total_outstanding = Number(billing.total_outstanding) + amount;

    await this.manager.save(billing);
    return billing;
  }

  async provision(tenant_id: string, plan: BillingPlan) {
    const existing = await this.findOne(tenant_id);
    if (existing) return existing;

    const billing = new TenantBillingEntity();
    billing.tenant_id = tenant_id;
    billing.plan = plan || BillingPlan.STANDARD;
    const saved = await this.manager.save(billing);

    const tbAccountId = await ensureTenantAccount(saved.id, saved.currency ?? "NGN");
    if (tbAccountId) {
      saved.tigerbeetle_account_id = tbAccountId;
      await this.manager.save(saved);
    }

    return saved;
  }
}

export const billingRepository = new BillingRepository();
