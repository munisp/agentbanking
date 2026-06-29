import { AppDataSource } from "../database/dataSource";
import { BillingLedgerEntity } from "../entity/BillingLedgerEntity";
import { TenantBillingEntity } from "../entity/TenantBillingEntity";
import { BillingModel } from "../utils/enums";
import { postBillingTransfer } from "../services/tigerbeetleService";
import logger from "../config/logger.config";

export interface RecordSplitInput {
  tenant_id: string;
  transaction_ref: string;
  transaction_type?: string;
  agent_id: number;
  pos_terminal_id?: number;
  gross_amount: number;
  gross_fee: number;
  agent_commission: number;
  switch_fee: number;
  aggregator_fee?: number;
  billing_model: BillingModel;
  revenue_share_pct?: number;
  currency?: string;
  region?: string;
  carrier?: string;
}

export interface LedgerQueryInput {
  tenant_id: string;
  agent_id?: number;
  billing_model?: BillingModel;
  transaction_type?: string;
  region?: string;
  carrier?: string;
  date_from?: Date;
  date_to?: Date;
  page?: number;
  page_size?: number;
}

class BillingLedgerRepository {
  private manager = AppDataSource.manager;

  async recordSplit(input: RecordSplitInput): Promise<BillingLedgerEntity> {
    const aggregator_fee = input.aggregator_fee ?? 0;
    const revenue_share_pct = input.revenue_share_pct ?? 70;

    const platform_net_fee =
      input.gross_fee - input.agent_commission - input.switch_fee - aggregator_fee;
    const client_revenue = Math.floor(platform_net_fee * (revenue_share_pct / 100));
    const platform_revenue = platform_net_fee - client_revenue;

    const entry = this.manager.create(BillingLedgerEntity, {
      tenant_id: input.tenant_id,
      transaction_ref: input.transaction_ref,
      transaction_type: input.transaction_type,
      agent_id: input.agent_id,
      pos_terminal_id: input.pos_terminal_id,
      gross_amount: input.gross_amount,
      gross_fee: input.gross_fee,
      agent_commission: input.agent_commission,
      switch_fee: input.switch_fee,
      aggregator_fee,
      platform_net_fee,
      billing_model: input.billing_model,
      client_revenue,
      platform_revenue,
      revenue_share_pct,
      currency: input.currency ?? "NGN",
      region: input.region,
      carrier: input.carrier,
    });

    const saved = await this.manager.save(entry);

    // Post to TigerBeetle — non-fatal if TB is unavailable or tenant has no account yet
    try {
      const billing = await this.manager.findOne(TenantBillingEntity, {
        where: { tenant_id: input.tenant_id },
      });
      if (billing?.tigerbeetle_account_id) {
        const tbTransferId = await postBillingTransfer({
          ledger_entry_id: saved.id,
          tigerbeetle_account_id: billing.tigerbeetle_account_id,
          client_revenue: Number(saved.client_revenue),
          currency: saved.currency,
        });
        if (tbTransferId) {
          saved.tigerbeetle_transfer_id = tbTransferId;
          await this.manager.save(saved);
        }
      }
    } catch (err) {
      logger.warn("[TigerBeetle] Transfer post failed (non-fatal)", err);
    }

    return saved;
  }

  async query(input: LedgerQueryInput) {
    const page = input.page ?? 1;
    const pageSize = input.page_size ?? 50;
    const skip = (page - 1) * pageSize;

    const qb = this.manager
      .createQueryBuilder(BillingLedgerEntity, "ledger")
      .where("ledger.tenant_id = :tenant_id", { tenant_id: input.tenant_id });

    if (input.agent_id) qb.andWhere("ledger.agent_id = :agent_id", { agent_id: input.agent_id });
    if (input.billing_model)
      qb.andWhere("ledger.billing_model = :billing_model", { billing_model: input.billing_model });
    if (input.transaction_type)
      qb.andWhere("ledger.transaction_type = :transaction_type", {
        transaction_type: input.transaction_type,
      });
    if (input.region) qb.andWhere("ledger.region = :region", { region: input.region });
    if (input.carrier) qb.andWhere("ledger.carrier = :carrier", { carrier: input.carrier });
    if (input.date_from)
      qb.andWhere("ledger.created_at >= :date_from", { date_from: input.date_from });
    if (input.date_to) qb.andWhere("ledger.created_at <= :date_to", { date_to: input.date_to });

    qb.orderBy("ledger.created_at", "DESC").skip(skip).take(pageSize);

    const [entries, total] = await qb.getManyAndCount();

    return {
      entries,
      total,
      page,
      page_size: pageSize,
      total_pages: Math.ceil(total / pageSize),
    };
  }

  async aggregateRevenue(
    tenant_id: string,
    period: "hourly" | "daily" | "weekly" | "monthly",
    date_from?: Date,
    date_to?: Date
  ) {
    const truncMap = {
      hourly: "hour",
      daily: "day",
      weekly: "week",
      monthly: "month",
    };
    const trunc = truncMap[period];

    const qb = this.manager
      .createQueryBuilder(BillingLedgerEntity, "ledger")
      .select(`DATE_TRUNC('${trunc}', ledger.created_at)`, "period_start")
      .addSelect("COUNT(*)", "transaction_count")
      .addSelect("COALESCE(SUM(ledger.gross_fee), 0)", "gross_fees")
      .addSelect("COALESCE(SUM(ledger.gross_amount), 0)", "gross_amounts")
      .addSelect("COALESCE(SUM(ledger.platform_revenue), 0)", "platform_revenue")
      .addSelect("COALESCE(SUM(ledger.client_revenue), 0)", "client_revenue")
      .addSelect("COALESCE(SUM(ledger.agent_commission), 0)", "agent_commissions")
      .addSelect("COALESCE(SUM(ledger.switch_fee), 0)", "switch_fees")
      .addSelect("COALESCE(SUM(ledger.platform_net_fee), 0)", "platform_net_fees")
      .where("ledger.tenant_id = :tenant_id", { tenant_id })
      .groupBy(`DATE_TRUNC('${trunc}', ledger.created_at)`)
      .orderBy(`DATE_TRUNC('${trunc}', ledger.created_at)`, "ASC");

    if (date_from) qb.andWhere("ledger.created_at >= :date_from", { date_from });
    if (date_to) qb.andWhere("ledger.created_at <= :date_to", { date_to });

    const aggregations = await qb.getRawMany();

    const totals = {
      total_gross_fees: aggregations.reduce((s, a) => s + Number(a.gross_fees), 0),
      total_platform_revenue: aggregations.reduce((s, a) => s + Number(a.platform_revenue), 0),
      total_client_revenue: aggregations.reduce((s, a) => s + Number(a.client_revenue), 0),
      total_transactions: aggregations.reduce((s, a) => s + Number(a.transaction_count), 0),
    };

    return { period, aggregations, totals };
  }

  async getLiveSplitMetrics(tenant_id: string) {
    const now = new Date();
    const today_start = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const month_start = new Date(now.getFullYear(), now.getMonth(), 1);

    const buildQuery = (since: Date) =>
      this.manager
        .createQueryBuilder(BillingLedgerEntity, "ledger")
        .select("COALESCE(SUM(ledger.gross_fee), 0)", "gross_fees")
        .addSelect("COALESCE(SUM(ledger.gross_amount), 0)", "gross_amounts")
        .addSelect("COALESCE(SUM(ledger.platform_revenue), 0)", "platform_revenue")
        .addSelect("COALESCE(SUM(ledger.client_revenue), 0)", "client_revenue")
        .addSelect("COALESCE(SUM(ledger.agent_commission), 0)", "agent_commissions")
        .addSelect("COALESCE(SUM(ledger.switch_fee), 0)", "switch_fees")
        .addSelect("COALESCE(SUM(ledger.platform_net_fee), 0)", "platform_net_fees")
        .addSelect("COUNT(*)", "transaction_count")
        .where("ledger.tenant_id = :tenant_id", { tenant_id })
        .andWhere("ledger.created_at >= :since", { since })
        .getRawOne();

    const [today, this_month] = await Promise.all([
      buildQuery(today_start),
      buildQuery(month_start),
    ]);

    const todayTxCount = Number(today?.transaction_count || 0);
    const todayGrossFees = Number(today?.gross_fees || 0);
    const monthTxCount = Number(this_month?.transaction_count || 0);

    return {
      today: {
        gross_fees: todayGrossFees,
        gross_amounts: Number(today?.gross_amounts || 0),
        platform_revenue: Number(today?.platform_revenue || 0),
        client_revenue: Number(today?.client_revenue || 0),
        agent_commissions: Number(today?.agent_commissions || 0),
        switch_fees: Number(today?.switch_fees || 0),
        platform_net_fees: Number(today?.platform_net_fees || 0),
        transaction_count: todayTxCount,
        avg_fee_per_tx: todayTxCount > 0 ? Math.round(todayGrossFees / todayTxCount) : 0,
      },
      this_month: {
        gross_fees: Number(this_month?.gross_fees || 0),
        gross_amounts: Number(this_month?.gross_amounts || 0),
        platform_revenue: Number(this_month?.platform_revenue || 0),
        client_revenue: Number(this_month?.client_revenue || 0),
        agent_commissions: Number(this_month?.agent_commissions || 0),
        switch_fees: Number(this_month?.switch_fees || 0),
        platform_net_fees: Number(this_month?.platform_net_fees || 0),
        transaction_count: monthTxCount,
        avg_fee_per_tx:
          monthTxCount > 0
            ? Math.round(Number(this_month?.gross_fees || 0) / monthTxCount)
            : 0,
      },
      last_updated: Date.now(),
    };
  }

  async getClientBillingConfig(tenant_id: string) {
    const billing = await this.manager.findOne(TenantBillingEntity, {
      where: { tenant_id },
    });

    if (!billing) {
      return {
        tenant_id,
        billing_model: BillingModel.REVENUE_SHARE,
        revenue_share_config: null,
        subscription_config: null,
        hybrid_config: null,
        effective_date: null,
        contract_end_date: null,
        auto_renew: false,
        provisioned: false,
      };
    }

    return {
      tenant_id,
      billing_model: billing.billing_model,
      revenue_share_config: billing.revenue_share_config,
      subscription_config: billing.subscription_config,
      hybrid_config: billing.hybrid_config,
      effective_date: billing.effective_date,
      contract_end_date: billing.contract_end_date,
      auto_renew: billing.auto_renew,
      provisioned: true,
    };
  }
}

export const billingLedgerRepository = new BillingLedgerRepository();
