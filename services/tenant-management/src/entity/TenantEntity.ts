import { Column, Entity, Index, JoinColumn, OneToMany, OneToOne } from "typeorm";
import { BaseEntity } from "./BaseEntity";
import { TenantStatus, TenantType } from "../utils/enums";
import { TenantFeatureFlagEntity } from "./TenantFeatureFlagEntity";
import { TenantBrandingEntity } from "./TenantBrandingEntity";
import { TenantContactEntity } from "./TenantContactEntity";

@Entity("tenant")
@Index("idx_tenant_id", ["tenant_id"])
export class TenantEntity extends BaseEntity {
  @Column({ type: "varchar", length: 255, unique: true })
  name!: string;

  @Column({ type: "enum", enum: TenantType, nullable: true })
  type?: TenantType;

  @Column({ type: "varchar", nullable: true })
  cac_certificate_url?: string;

  @Column({ type: "varchar", nullable: true })
  cbn_license_url?: string;

  @Column({ type: "enum", enum: TenantStatus, default: TenantStatus.ACTIVE })
  status!: TenantStatus;

  @OneToOne(() => TenantContactEntity, (contact) => contact.tenant, { cascade: true, eager: true })
  @JoinColumn()
  contact!: TenantContactEntity;

  @OneToOne(() => TenantBrandingEntity, (branding) => branding.tenant, {
    cascade: true,
    eager: true,
    nullable: true,
  })
  @JoinColumn()
  branding?: TenantBrandingEntity;

  @OneToMany(() => TenantFeatureFlagEntity, (featureFlag) => featureFlag.tenant, {
    cascade: true,
    eager: true,
  })
  feature_flags!: TenantFeatureFlagEntity[];

  @Column({ type: "varchar" })
  tenant_id!: string;

  @Column({ type: "varchar" })
  tenant_secret?: string;

  @Column({ type: "varchar", nullable: true })
  status_message!: string;

  @Column({ type: "jsonb", nullable: true })
  api_configuration?: {
    webhookUrl?: string;
    callbackUrl?: string;
  };
}
