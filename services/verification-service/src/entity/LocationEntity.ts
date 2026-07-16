import { Column, Entity } from "typeorm";
import { BaseEntity } from "./BaseEntity";

@Entity("location")
export class LocationEntity extends BaseEntity {
  @Column()
  country!: string;

  @Column()
  country_code!: string;

  @Column()
  city!: string;

  @Column()
  street!: string;

  @Column()
  post_code!: string;

  @Column()
  state!: string;
}
