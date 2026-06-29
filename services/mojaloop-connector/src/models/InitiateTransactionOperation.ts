import { Column, Entity, Unique } from "typeorm";
import { BaseModel } from "./BaseModel";

@Entity("initiate_transaction_operation")
@Unique("uq_sender_receiver_amount", ["sender", "receiver", "amount"])
export class InitiateTransactionOperation extends BaseModel {
  @Column()
  sender!: string;

  @Column()
  receiver!: string;

  @Column({ type: "decimal" })
  amount!: number;

  @Column()
  workflow_id!: string;
}
