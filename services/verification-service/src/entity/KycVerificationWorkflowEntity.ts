import { Column, Entity, JoinColumn, ManyToOne, Unique } from "typeorm";
import { BaseEntity } from "./BaseEntity";
import { KycIdentityProviders, VerificationWorkflowStatus } from "../utils/enums";
import { ClientEntity } from "./ClientEntity";

@Entity("kyc_verification_workflow")
@Unique(["client_id", "client_app_user_id"])
export class KycVerificationWorkflowEntity extends BaseEntity {
  @Column({ type: "enum", enum: KycIdentityProviders })
  identity_provider!: KycIdentityProviders;

  @ManyToOne(() => ClientEntity, (client) => client.kyc_verifications)
  @JoinColumn({ name: "client_id" })
  client!: ClientEntity;

  @Column()
  client_id!: string;

  @Column()
  client_app_user_id!: string;

  @Column({ type: "enum", enum: VerificationWorkflowStatus, default: VerificationWorkflowStatus.RUNNING })
  status!: VerificationWorkflowStatus;

  @Column({ type: "float", default: 0.0 })
  score: number = 0.0;

  @Column({ default: false })
  has_sent_webhook!: boolean;
}
