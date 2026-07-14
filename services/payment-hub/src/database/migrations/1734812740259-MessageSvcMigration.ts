import { MigrationInterface, QueryRunner } from "typeorm";

export class MessageSvcMigration1734812740259 implements MigrationInterface {
    name = 'MessageSvcMigration1734812740259'

    public async up(queryRunner: QueryRunner): Promise<void> {
        await queryRunner.query(`CREATE TABLE "administration"."tenant" ("id" uuid NOT NULL DEFAULT uuid_generate_v4(), "created_at" TIMESTAMP NOT NULL DEFAULT now(), "updated_at" TIMESTAMP NOT NULL DEFAULT now(), "deleted_at" TIMESTAMP, "name" character varying NOT NULL, "dfsp_id" character varying NOT NULL, CONSTRAINT "UQ_56211336b5ff35fd944f2259173" UNIQUE ("name"), CONSTRAINT "PK_da8c6efd67bb301e810e56ac139" PRIMARY KEY ("id"))`);
    }

    public async down(queryRunner: QueryRunner): Promise<void> {
        await queryRunner.query(`DROP TABLE "administration"."tenant"`);
    }

}
