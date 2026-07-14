import { MigrationInterface, QueryRunner } from "typeorm";

export class Migration1749682674346 implements MigrationInterface {
    name = 'Migration1749682674346'

    public async up(queryRunner: QueryRunner): Promise<void> {
        await queryRunner.query(`ALTER TABLE "administration"."transaction" ADD "tag" character varying NOT NULL DEFAULT 'TRANSFER'`);
        await queryRunner.query(`ALTER TYPE "administration"."transaction_switch_name_enum" RENAME TO "transaction_switch_name_enum_old"`);
        await queryRunner.query(`CREATE TYPE "administration"."transaction_switch_name_enum" AS ENUM('mojaloop', 'vfd', 'lux')`);
        await queryRunner.query(`ALTER TABLE "administration"."transaction" ALTER COLUMN "switch_name" TYPE "administration"."transaction_switch_name_enum" USING "switch_name"::"text"::"administration"."transaction_switch_name_enum"`);
        await queryRunner.query(`DROP TYPE "administration"."transaction_switch_name_enum_old"`);
    }

    public async down(queryRunner: QueryRunner): Promise<void> {
        await queryRunner.query(`CREATE TYPE "administration"."transaction_switch_name_enum_old" AS ENUM('mojaloop', 'vfd')`);
        await queryRunner.query(`ALTER TABLE "administration"."transaction" ALTER COLUMN "switch_name" TYPE "administration"."transaction_switch_name_enum_old" USING "switch_name"::"text"::"administration"."transaction_switch_name_enum_old"`);
        await queryRunner.query(`DROP TYPE "administration"."transaction_switch_name_enum"`);
        await queryRunner.query(`ALTER TYPE "administration"."transaction_switch_name_enum_old" RENAME TO "transaction_switch_name_enum"`);
        await queryRunner.query(`ALTER TABLE "administration"."transaction" DROP COLUMN "tag"`);
    }

}
