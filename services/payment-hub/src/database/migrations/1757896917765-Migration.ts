import { MigrationInterface, QueryRunner } from "typeorm";

export class Migration1757896917765 implements MigrationInterface {
    name = 'Migration1757896917765'

    public async up(queryRunner: QueryRunner): Promise<void> {
        await queryRunner.query(`ALTER TABLE "administration"."transaction" ADD "hold_id" character varying`);
    }

    public async down(queryRunner: QueryRunner): Promise<void> {
        await queryRunner.query(`ALTER TABLE "administration"."transaction" DROP COLUMN "hold_id"`);
    }

}
