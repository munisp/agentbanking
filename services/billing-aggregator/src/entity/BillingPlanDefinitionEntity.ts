import { Entity, Column } from "typeorm";
import { BaseEntity } from "./BaseEntity";

@Entity({ name: "billing_plan_definitions" })
export class BillingPlanDefinitionEntity extends BaseEntity {
  @Column({ type: "varchar", length: 64, unique: true })
  name!: string;

  @Column({ type: "varchar", length: 128 })
  label!: string;

  @Column({ type: "decimal", precision: 15, scale: 2, default: 0 })
  monthly_fee!: number;

  @Column({ type: "varchar", length: 3, default: "NGN" })
  currency!: string;

  @Column({ type: "text", nullable: true })
  description?: string;

  @Column({ type: "jsonb", default: [] })
  features!: string[];

  @Column({ type: "boolean", default: false })
  popular!: boolean;
}
