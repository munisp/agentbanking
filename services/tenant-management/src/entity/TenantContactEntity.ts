import { Column, Entity, OneToOne, PrimaryGeneratedColumn } from "typeorm";
import { TenantEntity } from "./TenantEntity";

@Entity("tenant_contact")
export class TenantContactEntity {
  @PrimaryGeneratedColumn("uuid")
  id!: string;

  @Column({ type: "varchar", length: 255 })
  name!: string;

  @Column({ type: "varchar", length: 255 })
  email!: string;

  @Column({ type: "varchar", length: 20, nullable: true })
  phone?: string;

  @OneToOne(() => TenantEntity, (tenant) => tenant.contact)
  tenant!: TenantEntity;
}
