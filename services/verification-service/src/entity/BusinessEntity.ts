import { Column, Entity, OneToOne } from "typeorm";
import { BaseEntity } from "./BaseEntity";
import { LocationEntity } from "./LocationEntity";

@Entity("business")
export class BusinessEntity extends BaseEntity {
  @Column()
  ballerine_business_id!: string;

  @Column()
  company_name!: string;

  @Column()
  registration_number!: string;

  @Column()
  mcc_code!: string;

  @Column()
  business_type!: string;

  @Column()
  contact_name!: string;

  @Column()
  contact_email!: string;

  @OneToOne(() => LocationEntity)
  location!: LocationEntity;
}
