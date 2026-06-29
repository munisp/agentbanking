import { Column, Entity } from "typeorm";
import { BaseModel } from "./BaseModel";

@Entity()
export class Tenant extends BaseModel {
  @Column({ unique: true })
  name!: string;

  @Column()
  dfsp_id!: string;
}
