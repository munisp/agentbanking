import { Column, Entity, OneToOne, PrimaryGeneratedColumn } from "typeorm";
import { TenantBranchEntity } from "./TenantBranchEntity";

@Entity("tenant_branch_contact")
export class TenantBranchContactEntity {
  @PrimaryGeneratedColumn("uuid")
  id!: string;

  @Column({ type: "varchar", length: 255 })
  name!: string;

  @Column({ type: "varchar", length: 255 })
  email!: string;

  @Column({ type: "varchar", length: 20, nullable: true })
  phone?: string;

  @OneToOne(() => TenantBranchEntity, (branch) => branch.contact)
  branch!: TenantBranchEntity;
}
