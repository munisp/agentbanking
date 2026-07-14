import { MigrationInterface, QueryRunner } from "typeorm";

export class Migration1750879348866 implements MigrationInterface {
    name = 'Migration1750879348866'

    public async up(queryRunner: QueryRunner): Promise<void> {
        await queryRunner.query(`ALTER TABLE "administration"."transaction" ADD "reference" character varying`);
    }

    public async down(queryRunner: QueryRunner): Promise<void> {
        await queryRunner.query(`ALTER TABLE "administration"."transaction" DROP COLUMN "reference"`);
    }

}
