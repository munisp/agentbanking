import { Entity, Column, Index } from "typeorm";
import { BaseEntity } from "./BaseEntity";
import { BillingAuditAction } from "../utils/enums";

@Entity({ name: "billing_audit_log" })
@Index("idx_bal_tenant", ["tenant_id"])
@Index("idx_bal_user", ["user_id"])
@Index("idx_bal_action", ["action"])
export class BillingAuditLogEntity extends BaseEntity {
  @Column({ type: "varchar" })
  tenant_id!: string;

  @Column({ type: "varchar" })
  user_id!: string;

  @Column({ type: "varchar", length: 128, nullable: true })
  user_name?: string;

  @Column({ type: "enum", enum: BillingAuditAction })
  action!: BillingAuditAction;

  @Column({ type: "varchar", length: 64, nullable: true })
  resource_type?: string;

  @Column({ type: "varchar", length: 128, nullable: true })
  resource_id?: string;

  @Column({ type: "jsonb", nullable: true })
  before_state?: Record<string, unknown>;

  @Column({ type: "jsonb", nullable: true })
  after_state?: Record<string, unknown>;

  @Column({ type: "jsonb", nullable: true })
  metadata?: Record<string, unknown>;

  @Column({ type: "varchar", length: 45, nullable: true })
  ip_address?: string;

  @Column({ type: "varchar", length: 512, nullable: true })
  user_agent?: string;

  @Column({ type: "varchar", length: 128, nullable: true })
  session_id?: string;

  @Column({ type: "boolean", default: false })
  notification_sent!: boolean;
}
