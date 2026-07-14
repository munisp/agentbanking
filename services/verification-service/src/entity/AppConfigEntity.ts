import { Column, Entity, Index } from "typeorm";
import { BaseEntity } from "./BaseEntity";

@Entity("app_config")
export class AppConfigEntity extends BaseEntity {
  @Index()
  @Column({ unique: true })
  key!: string;

  @Column({ type: "jsonb" })
  value!: Record<string, any>;
}
