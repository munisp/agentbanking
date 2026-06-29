import { Column, Entity } from "typeorm";
import { BaseEntity } from "./BaseEntity";
import { VerificationWorkflowStatus } from "../utils/enums";

@Entity("ballerine_verification_workflow")
export class BallerineVerificationWorkflowEntity extends BaseEntity {
  @Column()
  ballerine_workflow_definition_id!: string;

  @Column({ unique: true })
  ballerine_workflow_runtime_id!: string;

  @Column()
  ballerine_entity_id!: string;

  @Column({ unique: true })
  ballerine_business_id!: string;

  @Column({ type: "enum", enum: VerificationWorkflowStatus, default: VerificationWorkflowStatus.RUNNING })
  status!: VerificationWorkflowStatus;
}
