import { Entity, Column, Index } from "typeorm";
import { BaseEntity } from "./BaseEntity";
import { InvoiceStatus } from "../utils/enums";

@Entity({ name: "billing_invoice" })
@Index("idx_billing_invoice_tenant_id", ["tenant_id"])
export class BillingInvoiceEntity extends BaseEntity {
  @Column({ type: "varchar" })
  tenant_id!: string;

  @Column({ type: "varchar", length: 64, unique: true })
  invoice_number!: string;

  @Column({ type: "varchar", length: 32, nullable: true })
  plan?: string;

  @Column({ type: "timestamp" })
  period_start!: Date;

  @Column({ type: "timestamp" })
  period_end!: Date;

  @Column({ type: "decimal", precision: 15, scale: 2, default: 0 })
  subtotal!: number;

  @Column({ type: "decimal", precision: 6, scale: 3, default: 0 })
  tax_rate!: number;

  @Column({ type: "decimal", precision: 15, scale: 2, default: 0 })
  tax_amount!: number;

  @Column({ type: "decimal", precision: 15, scale: 2, default: 0 })
  total!: number;

  @Column({ type: "varchar", length: 3, default: "NGN" })
  currency!: string;

  @Column({ type: "enum", enum: InvoiceStatus, default: InvoiceStatus.ISSUED })
  status!: InvoiceStatus;

  @Column({ type: "timestamp" })
  due_date!: Date;

  @Column({ type: "timestamp", nullable: true })
  paid_at?: Date;

  @Column({ type: "varchar", length: 64, nullable: true })
  payment_ref?: string;

  @Column({ type: "jsonb", default: [] })
  line_items!: unknown[];
}
