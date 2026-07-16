import { Column, Entity, OneToOne, PrimaryGeneratedColumn } from "typeorm";
import { TenantEntity } from "./TenantEntity";

@Entity("tenant_branding")
export class TenantBrandingEntity {
  @PrimaryGeneratedColumn("uuid")
  id!: string;

  @Column({ nullable: true })
  logo_url?: string;

  @Column({ nullable: true })
  favicon_url?: string;

  @Column({ nullable: true })
  primary_color?: string;

  @Column({ nullable: true })
  secondary_color?: string;

  @Column({ nullable: true })
  domain?: string;

  @OneToOne(() => TenantEntity, (tenant) => tenant.branding)
  tenant!: TenantEntity;
}
