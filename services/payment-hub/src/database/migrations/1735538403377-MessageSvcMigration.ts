import { MigrationInterface, QueryRunner } from "typeorm";

export class MessageSvcMigration1735538403377 implements MigrationInterface {
    name = 'MessageSvcMigration1735538403377'

    public async up(queryRunner: QueryRunner): Promise<void> {
        await queryRunner.query(`ALTER TABLE "administration"."transaction" ADD "note" character varying`);
    }

    public async down(queryRunner: QueryRunner): Promise<void> {
        await queryRunner.query(`ALTER TABLE "administration"."transaction" DROP COLUMN "note"`);
    }

}
