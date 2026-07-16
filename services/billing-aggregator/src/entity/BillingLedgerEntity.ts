import { Entity, Column, Index } from "typeorm";
import { BaseEntity } from "./BaseEntity";
import { BillingModel } from "../utils/enums";

@Entity({ name: "billing_ledger" })
@Index("idx_billing_ledger_tenant", ["tenant_id"])
@Index("idx_billing_ledger_tx_ref", ["transaction_ref"])
@Index("idx_billing_ledger_agent", ["agent_id"])
export class BillingLedgerEntity extends BaseEntity {
  @Column({ type: "varchar" })
  tenant_id!: string;

  @Column({ type: "varchar", length: 64 })
  transaction_ref!: string;

  @Column({ type: "varchar", length: 32, nullable: true })
  transaction_type?: string;

  @Column({ type: "int" })
  agent_id!: number;

  @Column({ type: "int", nullable: true })
  pos_terminal_id?: number;

  @Column({ type: "decimal", precision: 15, scale: 2, default: 0 })
  gross_amount!: number;

  @Column({ type: "decimal", precision: 12, scale: 2, default: 0 })
  gross_fee!: number;

  @Column({ type: "decimal", precision: 12, scale: 2, default: 0 })
  agent_commission!: number;

  @Column({ type: "decimal", precision: 12, scale: 2, default: 0 })
  switch_fee!: number;

  @Column({ type: "decimal", precision: 12, scale: 2, default: 0 })
  aggregator_fee!: number;

  @Column({ type: "decimal", precision: 12, scale: 2, default: 0 })
  platform_net_fee!: number;

  @Column({ type: "enum", enum: BillingModel, default: BillingModel.REVENUE_SHARE })
  billing_model!: BillingModel;

  @Column({ type: "decimal", precision: 12, scale: 2, default: 0 })
  client_revenue!: number;

  @Column({ type: "decimal", precision: 12, scale: 2, default: 0 })
  platform_revenue!: number;

  @Column({ type: "decimal", precision: 5, scale: 2, default: 70 })
  revenue_share_pct!: number;

  @Column({ type: "varchar", length: 3, default: "NGN" })
  currency!: string;

  @Column({ type: "varchar", length: 32, nullable: true })
  region?: string;

  @Column({ type: "varchar", length: 32, nullable: true })
  carrier?: string;

  @Column({ type: "varchar", length: 64, nullable: true })
  tigerbeetle_transfer_id?: string;

  @Column({ type: "varchar", length: 32, nullable: true })
  kafka_offset?: string;

  @Column({ type: "timestamp", nullable: true })
  processed_at?: Date;
}
