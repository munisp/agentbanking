import { Entity, Column, Index } from "typeorm";
import { BaseEntity } from "./BaseEntity";
import { ReconciliationStatus } from "../utils/enums";

@Entity({ name: "billing_reconciliation_report" })
@Index("idx_brr_tenant", ["tenant_id"])
export class BillingReconciliationReportEntity extends BaseEntity {
  @Column({ type: "varchar" })
  tenant_id!: string;

  @Column({ type: "varchar", length: 20 })
  report_period!: string;

  @Column({ type: "timestamp" })
  period_start!: Date;

  @Column({ type: "timestamp" })
  period_end!: Date;

  @Column({ type: "enum", enum: ReconciliationStatus, default: ReconciliationStatus.PENDING })
  status!: ReconciliationStatus;

  @Column({ type: "int", default: 0 })
  projected_transactions!: number;

  @Column({ type: "decimal", precision: 18, scale: 2, default: 0 })
  projected_gross_volume!: number;

  @Column({ type: "decimal", precision: 15, scale: 2, default: 0 })
  projected_platform_revenue!: number;

  @Column({ type: "decimal", precision: 15, scale: 2, default: 0 })
  projected_client_revenue!: number;

  @Column({ type: "int", default: 0 })
  actual_transactions!: number;

  @Column({ type: "decimal", precision: 18, scale: 2, default: 0 })
  actual_gross_volume!: number;

  @Column({ type: "decimal", precision: 15, scale: 2, default: 0 })
  actual_platform_revenue!: number;

  @Column({ type: "decimal", precision: 15, scale: 2, default: 0 })
  actual_client_revenue!: number;

  @Column({ type: "decimal", precision: 8, scale: 2, default: 0 })
  revenue_variance_pct!: number;

  @Column({ type: "decimal", precision: 8, scale: 2, default: 0 })
  volume_variance_pct!: number;

  @Column({ type: "jsonb", nullable: true })
  discrepancies?: unknown[];

  @Column({ type: "varchar", length: 64, default: "billing-reconciliation-engine" })
  generated_by!: string;

  @Column({ type: "timestamp", nullable: true })
  completed_at?: Date;
}
