import { MigrationInterface, QueryRunner } from "typeorm";

export class MessageSvcMigration1735283105072 implements MigrationInterface {
    name = 'MessageSvcMigration1735283105072'

    public async up(queryRunner: QueryRunner): Promise<void> {
        await queryRunner.query(`ALTER TABLE "administration"."transaction" ADD "fulfillment_secret" text`);
    }

    public async down(queryRunner: QueryRunner): Promise<void> {
        await queryRunner.query(`ALTER TABLE "administration"."transaction" DROP COLUMN "fulfillment_secret"`);
    }

}
