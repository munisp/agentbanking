import { Column, Entity, Unique } from "typeorm";
import { BaseModel } from "./BaseModel";
import { PartyIdTypeEnum } from "../utils/enums";

@Entity("register_client_operation")
@Unique("uq_identifier_type_identifier_fsp_id", ["identifier_type", "identifier", "fsp_id"])
export class RegisterClientOperation extends BaseModel {
  @Column({ type: "enum", enum: PartyIdTypeEnum })
  identifier_type!: PartyIdTypeEnum;

  @Column()
  identifier!: string;

  @Column()
  fsp_id!: string;

  @Column()
  workflow_id!: string;
}
