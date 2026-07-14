import { Entity, Column, Index } from "typeorm";
import { BaseEntity } from "./BaseEntity";

@Entity({ name: "billing_revenue_period" })
@Index("idx_brp_tenant_period", ["tenant_id", "period_type"])
export class BillingRevenuePeriodEntity extends BaseEntity {
  @Column({ type: "varchar" })
  tenant_id!: string;

  @Column({ type: "varchar", length: 10 })
  period_type!: string;

  @Column({ type: "timestamp" })
  period_start!: Date;

  @Column({ type: "timestamp" })
  period_end!: Date;

  @Column({ type: "int", default: 0 })
  transaction_count!: number;

  @Column({ type: "decimal", precision: 18, scale: 2, default: 0 })
  gross_volume!: number;

  @Column({ type: "decimal", precision: 15, scale: 2, default: 0 })
  total_fees!: number;

  @Column({ type: "decimal", precision: 15, scale: 2, default: 0 })
  total_client_revenue!: number;

  @Column({ type: "decimal", precision: 15, scale: 2, default: 0 })
  total_platform_revenue!: number;

  @Column({ type: "decimal", precision: 15, scale: 2, default: 0 })
  total_agent_commissions!: number;

  @Column({ type: "decimal", precision: 15, scale: 2, default: 0 })
  total_switch_fees!: number;

  @Column({ type: "int", default: 0 })
  active_agents!: number;

  @Column({ type: "jsonb", nullable: true })
  breakdown_by_type?: Record<string, number>;

  @Column({ type: "jsonb", nullable: true })
  breakdown_by_region?: Record<string, number>;
}
