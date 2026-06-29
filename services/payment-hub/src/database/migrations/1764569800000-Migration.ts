import { MigrationInterface, QueryRunner } from "typeorm";

export class Migration1764569800000 implements MigrationInterface {
    name = 'Migration1764569800000'

    public async up(queryRunner: QueryRunner): Promise<void> {
        await queryRunner.query(`ALTER TYPE "administration"."transaction_currency_enum" ADD VALUE IF NOT EXISTS 'USD'`);
        await queryRunner.query(`ALTER TYPE "administration"."transaction_currency_enum" ADD VALUE IF NOT EXISTS 'EUR'`);
        await queryRunner.query(`ALTER TYPE "administration"."transaction_currency_enum" ADD VALUE IF NOT EXISTS 'GBP'`);
        await queryRunner.query(`ALTER TYPE "administration"."transaction_currency_enum" ADD VALUE IF NOT EXISTS 'JPY'`);
        await queryRunner.query(`ALTER TYPE "administration"."transaction_currency_enum" ADD VALUE IF NOT EXISTS 'AUD'`);
        await queryRunner.query(`ALTER TYPE "administration"."transaction_currency_enum" ADD VALUE IF NOT EXISTS 'GHS'`);
    }

    public async down(queryRunner: QueryRunner): Promise<void> {
    }
}
