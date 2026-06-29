import { Column, CreateDateColumn, Entity, Index, Unique } from "typeorm";
import { BaseModel } from "./BaseModel";
import {
  AmountTypeEnum,
  AppSwitchEnum,
  CurrencyEnum,
  PartyIdTypeEnum,
  TransactionDirectionEnum,
  TransactionQuoteStatusEnum,
  TransactionStatusEnum,
  TransactionTypeEnum,
} from "../utils/enums";

export interface TransactionParty {
  idType: PartyIdTypeEnum;
  idValue: string;
}

@Entity()
@Unique("uq_quote_direction", ["quote_id", "transaction_direction"])
export class Transaction extends BaseModel {
  @Column({
    type: "enum",
    enum: TransactionStatusEnum,
    default: TransactionStatusEnum.pending,
  })
  status!: TransactionStatusEnum;

  @Column({ type: "timestamptz", nullable: true })
  completed_at: string | null = null;

  @Column({ type: "timestamptz", nullable: true })
  failed_at: string | null = null;

  @Column({ type: "text", nullable: true })
  reason: string | null = null;

  @Column({ type: "enum", enum: AmountTypeEnum })
  amount_type!: AmountTypeEnum;

  @Column()
  amount!: string;

  @Column({ default: "0.0" })
  fees!: string;

  @Column({ nullable: true, type: "enum", enum: AppSwitchEnum })
  switch_name: AppSwitchEnum | null = null;

  @Column({ type: "enum", enum: CurrencyEnum })
  currency!: CurrencyEnum;

  @Column()
  quote_id!: string;

  @Column({
    type: "enum",
    enum: TransactionQuoteStatusEnum,
    default: TransactionQuoteStatusEnum.in_progress,
  })
  quote_status!: TransactionQuoteStatusEnum;

  @Column()
  @Index()
  transaction_id!: string;

  @Column({ type: "text", nullable: true })
  ilp_packet: string | null = null;

  @Column({ type: "text", nullable: true })
  fulfillment: string | null = null;

  @Column({ type: "text", nullable: true })
  fulfillment_secret: string | null = null;

  @Column({ type: "enum", enum: TransactionTypeEnum })
  transaction_type!: TransactionTypeEnum;

  @Column({ type: "enum", enum: TransactionDirectionEnum })
  transaction_direction!: TransactionDirectionEnum;

  @Column()
  payerFsp!: string;

  @Column()
  payeeFsp!: string;

  @Column({ type: "json" })
  payer!: TransactionParty;

  @Column({ type: "json" })
  payee!: TransactionParty;

  @Column()
  tenant!: string;

  @Column({ type: "varchar", nullable: true })
  note: string | null = null;

  @Column({ type: "varchar", nullable: true })
  local_transaction_id: string | null = null;

  @CreateDateColumn()
  @Index()
  created_at!: Date;

  @Column({ default: TransactionTypeEnum.TRANSFER })
  tag!: string;

  @Column({ type: "varchar", nullable: true })
  reference: string | null = null;

  @Column({ type: "varchar", nullable: true })
  hold_id: string | null = null;

  @Column({ type: "varchar", nullable: true })
  balance_after_transaction: string | null = null;
}
