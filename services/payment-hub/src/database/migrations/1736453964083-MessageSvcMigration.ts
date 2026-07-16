import { MigrationInterface, QueryRunner } from "typeorm";

export class MessageSvcMigration1736453964083 implements MigrationInterface {
    name = 'MessageSvcMigration1736453964083'

    public async up(queryRunner: QueryRunner): Promise<void> {
        await queryRunner.query(`CREATE TYPE "administration"."transaction_switch_name_enum" AS ENUM('mojaloop', 'vfd')`);
        await queryRunner.query(`ALTER TABLE "administration"."transaction" ADD "switch_name" "administration"."transaction_switch_name_enum"`);
    }

    public async down(queryRunner: QueryRunner): Promise<void> {
        await queryRunner.query(`ALTER TABLE "administration"."transaction" DROP COLUMN "switch_name"`);
        await queryRunner.query(`DROP TYPE "administration"."transaction_switch_name_enum"`);
    }

}
