import { Entity, Column, ManyToOne } from "typeorm";
import { BaseEntity } from "./BaseEntity";
import { BillingCycleStatus } from "../utils/enums";
import { TenantBillingEntity } from "./TenantBillingEntity";

@Entity({ name: "tenant_billing_cycle" })
export class TenantBillingCycleEntity extends BaseEntity {
  @Column({
    type: "decimal",
    precision: 12,
    scale: 2,
    default: 0,
  })
  amount!: number;

  @Column({ type: "enum", enum: BillingCycleStatus, default: BillingCycleStatus.RUNNING })
  status!: BillingCycleStatus;

  @ManyToOne(() => TenantBillingEntity, { onDelete: "CASCADE", nullable: true })
  billing?: TenantBillingEntity;
}
