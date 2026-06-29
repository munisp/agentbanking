import { MigrationInterface, QueryRunner } from "typeorm";

export class Migration1764568515184 implements MigrationInterface {
    name = 'Migration1764568515184'

    public async up(queryRunner: QueryRunner): Promise<void> {
        await queryRunner.query(`ALTER TABLE "administration"."transaction" ADD "balance_after_transaction" character varying`);
    }

    public async down(queryRunner: QueryRunner): Promise<void> {
        await queryRunner.query(`ALTER TABLE "administration"."transaction" DROP COLUMN "balance_after_transaction"`);
    }

}
