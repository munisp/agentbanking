import { MigrationInterface, QueryRunner } from "typeorm";

export class Migration1739973352074 implements MigrationInterface {
    name = 'Migration1739973352074'

    public async up(queryRunner: QueryRunner): Promise<void> {
        await queryRunner.query(`ALTER TABLE "administration"."transaction" DROP CONSTRAINT "UQ_a468ebb59d3768fbbc1ca070a97"`);
        await queryRunner.query(`ALTER TABLE "administration"."transaction" ADD CONSTRAINT "uq_transaction_direction" UNIQUE ("transaction_id", "transaction_direction")`);
    }

    public async down(queryRunner: QueryRunner): Promise<void> {
        await queryRunner.query(`ALTER TABLE "administration"."transaction" DROP CONSTRAINT "uq_transaction_direction"`);
        await queryRunner.query(`ALTER TABLE "administration"."transaction" ADD CONSTRAINT "UQ_a468ebb59d3768fbbc1ca070a97" UNIQUE ("quote_id")`);
    }

}
