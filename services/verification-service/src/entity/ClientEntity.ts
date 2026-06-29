import { Column, Entity, OneToMany } from "typeorm";
import { BaseEntity } from "./BaseEntity";
import { KycVerificationWorkflowEntity } from "./KycVerificationWorkflowEntity";

@Entity("client")
export class ClientEntity extends BaseEntity {
  @Column()
  client_id!: string;

  @Column()
  client_name!: string;

  @Column()
  client_secret!: string;

  @Column({ nullable: true })
  callback_url?: string;

  @Column("text", { array: true })
  redirect_urls!: string[];

  @Column()
  contact_first_name!: string;

  @Column()
  contact_last_name!: string;

  @Column()
  contact_email!: string;

  @Column()
  ballerine_customer_api_key!: string;

  @Column()
  ballerine_customer_id!: string;

  @OneToMany(() => KycVerificationWorkflowEntity, (kyc_verifications) => kyc_verifications.client)
  kyc_verifications!: KycVerificationWorkflowEntity[];
}
