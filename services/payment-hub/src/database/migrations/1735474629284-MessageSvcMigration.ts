import { MigrationInterface, QueryRunner } from "typeorm";

export class MessageSvcMigration1735474629284 implements MigrationInterface {
    name = 'MessageSvcMigration1735474629284'

    public async up(queryRunner: QueryRunner): Promise<void> {
        await queryRunner.query(`CREATE TYPE "administration"."transaction_transaction_direction_enum" AS ENUM('incoming', 'outgoing')`);
        await queryRunner.query(`ALTER TABLE "administration"."transaction" ADD "transaction_direction" "administration"."transaction_transaction_direction_enum" NOT NULL`);
        await queryRunner.query(`ALTER TABLE "administration"."transaction" ADD "tenant" character varying NOT NULL`);
    }

    public async down(queryRunner: QueryRunner): Promise<void> {
        await queryRunner.query(`ALTER TABLE "administration"."transaction" DROP COLUMN "tenant"`);
        await queryRunner.query(`ALTER TABLE "administration"."transaction" DROP COLUMN "transaction_direction"`);
        await queryRunner.query(`DROP TYPE "administration"."transaction_transaction_direction_enum"`);
    }

}
