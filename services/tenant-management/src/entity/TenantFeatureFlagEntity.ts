import { Column, Entity, ManyToOne, PrimaryGeneratedColumn } from "typeorm";
import { FeatureFlag } from "../utils/enums";
import { TenantEntity } from "./TenantEntity";

@Entity("tenant_feature_flag")
export class TenantFeatureFlagEntity {
  @PrimaryGeneratedColumn("uuid")
  id!: string;

  @Column({ type: "enum", enum: FeatureFlag })
  name!: FeatureFlag;

  @Column({ type: "boolean", default: false })
  is_enabled!: boolean;

  @ManyToOne(() => TenantEntity, (tenant) => tenant.feature_flags)
  tenant!: TenantEntity;

  @Column({ type: "jsonb", nullable: true })
  config?: object;
}
