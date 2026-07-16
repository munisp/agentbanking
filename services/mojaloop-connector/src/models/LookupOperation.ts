import { Column, Entity, Unique } from "typeorm";
import { BaseModel } from "./BaseModel";
import { LookupResourceEnum, PartyIdTypeEnum } from "../utils/enums";

@Entity("lookup_operation")
@Unique("uq_identifier_identifier_type_lookup_op", ["identifier", "identifier_type", "resource"])
export class LookupOperation extends BaseModel {
  @Column()
  identifier!: string;

  @Column({ type: "enum", enum: PartyIdTypeEnum })
  identifier_type!: PartyIdTypeEnum;

  @Column()
  workflow_id!: string;

  @Column({ type: "enum", enum: LookupResourceEnum })
  resource!: LookupResourceEnum;
}
