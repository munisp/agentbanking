import { Column, Entity, Index, ManyToOne, PrimaryGeneratedColumn, Unique } from "typeorm";
import { FeatureFlag } from "../utils/enums";
import { TenantBranchEntity } from "./TenantBranchEntity";

@Entity("tenant_branch_feature_flag")
export class TenantBranchFeatureFlagEntity {
  @PrimaryGeneratedColumn("uuid")
  id!: string;

  @Column({ type: "enum", enum: FeatureFlag })
  name!: FeatureFlag;

  @Column({ type: "boolean", default: false })
  is_enabled!: boolean;

  @ManyToOne(() => TenantBranchEntity, (branch) => branch.feature_flags)
  branch!: TenantBranchEntity;

  @Column({ type: "jsonb", nullable: true })
  config?: object;
}
