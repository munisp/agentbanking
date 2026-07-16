import { MigrationInterface, QueryRunner } from "typeorm";

export class Migration1740020630107 implements MigrationInterface {
    name = 'Migration1740020630107'

    public async up(queryRunner: QueryRunner): Promise<void> {
        await queryRunner.query(`ALTER TABLE "administration"."transaction" DROP CONSTRAINT "uq_transaction_direction"`);
        await queryRunner.query(`ALTER TABLE "administration"."transaction" ADD CONSTRAINT "uq_quote_direction" UNIQUE ("quote_id", "transaction_direction")`);
    }

    public async down(queryRunner: QueryRunner): Promise<void> {
        await queryRunner.query(`ALTER TABLE "administration"."transaction" DROP CONSTRAINT "uq_quote_direction"`);
        await queryRunner.query(`ALTER TABLE "administration"."transaction" ADD CONSTRAINT "uq_transaction_direction" UNIQUE ("transaction_id", "transaction_direction")`);
    }

}
