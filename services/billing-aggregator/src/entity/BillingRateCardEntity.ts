import { Column, Entity } from "typeorm";
import { BaseEntity } from "./BaseEntity";

@Entity({ name: "billing_rate_cards" })
export class BillingRateCardEntity extends BaseEntity {
  @Column({ type: "varchar", length: 255, nullable: true })
  billing_account_id?: string;

  @Column({ type: "varchar", length: 128 })
  name!: string;

  @Column({ type: "int", default: 1 })
  version!: number;

  @Column({ type: "varchar", length: 16, default: "draft" })
  status!: "draft" | "approved" | "active" | "retired";

  @Column({ type: "timestamptz" })
  effective_from!: Date;

  @Column({ type: "timestamptz", nullable: true })
  effective_to?: Date;

  @Column({ type: "varchar", length: 3, default: "NGN" })
  pricing_currency!: string;

  @Column({ type: "varchar", length: 255 })
  created_by!: string;

  @Column({ type: "varchar", length: 16, default: "pending" })
  approval_state!: "pending" | "approved" | "rejected";
}
