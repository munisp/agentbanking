import { Column, Entity, Index, JoinColumn, OneToMany, OneToOne, PrimaryGeneratedColumn } from "typeorm";
import { BaseEntity } from "./BaseEntity";
import { TenantStatus } from "../utils/enums";
import { TenantBranchFeatureFlagEntity } from "./TenantBranchFeatureFlagEntity";
import { TenantBranchContactEntity } from "./TenantBranchContactEntity";

@Entity("tenant_branch")
export class TenantBranchEntity extends BaseEntity {
  @Column({ type: "varchar", length: 255 })
  name!: string;

  @Column({ type: "varchar", length: 255 })
  code!: string;

  @Column({ type: "varchar", length: 255, nullable: true })
  webhook_url?: string;

  @Column({ type: "varchar", length: 255, nullable: true })
  callback_url?: string;

  @Column({ type: "varchar", length: 255 })
  location!: string;

  @Column({ type: "enum", enum: TenantStatus, default: TenantStatus.ACTIVE })
  status!: TenantStatus;

  @OneToOne(() => TenantBranchContactEntity, (contact) => contact.branch, { cascade: true, eager: true })
  @JoinColumn()
  contact!: TenantBranchContactEntity;

  @OneToMany(() => TenantBranchFeatureFlagEntity, (featureFlag) => featureFlag.branch, {
    cascade: true,
    eager: true,
  })
  feature_flags!: TenantBranchFeatureFlagEntity[];

  @Column({ type: "varchar" })
  tenant_id!: string;
}
