import { Entity, Column, Index } from "typeorm";
import { BaseEntity } from "./BaseEntity";
import { BillingModel, BillingPlan, BillingStatus } from "../utils/enums";

@Entity({ name: "tenant_billing" })
@Index("idx_tenant_billing_tenant_id", ["tenant_id"], { unique: true })
export class TenantBillingEntity extends BaseEntity {
  @Column({ type: "varchar" })
  tenant_id!: string;

  @Column({ type: "enum", enum: BillingPlan, default: BillingPlan.STANDARD })
  plan!: BillingPlan;

  @Column({ type: "enum", enum: BillingModel, default: BillingModel.REVENUE_SHARE })
  billing_model!: BillingModel;

  @Column({ type: "enum", enum: BillingStatus, default: BillingStatus.ACTIVE })
  status!: BillingStatus;

  @Column({ type: "jsonb", nullable: true })
  revenue_share_config?: {
    startSplitPct: number;
    scaleSplitPct: number;
    scaleThreshold: number;
    minimumMonthlyGuarantee: number;
    signOnFee: number;
    signOnFeePaid: boolean;
  };

  @Column({ type: "jsonb", nullable: true })
  subscription_config?: {
    perAgentFee: number;
    perPosFee: number;
    implementationFee: number;
    billingCycle: string;
  };

  @Column({ type: "jsonb", nullable: true })
  hybrid_config?: {
    reducedSharePct: number;
    reducedPerAgent: number;
    licenseFee: number;
  };

  @Column({ type: "varchar", length: 3, default: "NGN" })
  currency!: string;

  @Column({ type: "timestamp", nullable: true })
  effective_date?: Date;

  @Column({ type: "timestamp", nullable: true })
  contract_end_date?: Date;

  @Column({ type: "boolean", default: true })
  auto_renew!: boolean;

  @Column({ type: "varchar", length: 64, nullable: true })
  tigerbeetle_account_id?: string;

  @Column({ type: "varchar", length: 64, nullable: true })
  kafka_topic_prefix?: string;

  @Column({ type: "varchar", length: 32, nullable: true })
  jurisdiction?: string;

  @Column({ type: "decimal", precision: 15, scale: 2, default: 0 })
  credits_balance!: number;

  @Column({ type: "timestamp", nullable: true })
  grace_period_end?: Date;

  @Column({ type: "varchar", length: 256, nullable: true })
  grace_period_reason?: string;

  @Column({ type: "timestamp", nullable: true })
  last_payment_date?: Date;

  @Column({ type: "varchar", length: 64, nullable: true })
  last_payment_reference?: string;

  @Column({ type: "decimal", precision: 15, scale: 2, default: 0 })
  total_paid_ytd!: number;

  @Column({ type: "decimal", precision: 15, scale: 2, default: 0 })
  total_outstanding!: number;

}
