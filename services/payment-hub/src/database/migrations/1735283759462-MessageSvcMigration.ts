import { MigrationInterface, QueryRunner } from "typeorm";

export class MessageSvcMigration1735283759462 implements MigrationInterface {
    name = 'MessageSvcMigration1735283759462'

    public async up(queryRunner: QueryRunner): Promise<void> {
        await queryRunner.query(`ALTER TYPE "administration"."transaction_status_enum" RENAME TO "transaction_status_enum_old"`);
        await queryRunner.query(`CREATE TYPE "administration"."transaction_status_enum" AS ENUM('success', 'failed', 'pending', 'reserved')`);
        await queryRunner.query(`ALTER TABLE "administration"."transaction" ALTER COLUMN "status" DROP DEFAULT`);
        await queryRunner.query(`ALTER TABLE "administration"."transaction" ALTER COLUMN "status" TYPE "administration"."transaction_status_enum" USING "status"::"text"::"administration"."transaction_status_enum"`);
        await queryRunner.query(`ALTER TABLE "administration"."transaction" ALTER COLUMN "status" SET DEFAULT 'pending'`);
        await queryRunner.query(`DROP TYPE "administration"."transaction_status_enum_old"`);
    }

    public async down(queryRunner: QueryRunner): Promise<void> {
        await queryRunner.query(`CREATE TYPE "administration"."transaction_status_enum_old" AS ENUM('success', 'failed', 'pending')`);
        await queryRunner.query(`ALTER TABLE "administration"."transaction" ALTER COLUMN "status" DROP DEFAULT`);
        await queryRunner.query(`ALTER TABLE "administration"."transaction" ALTER COLUMN "status" TYPE "administration"."transaction_status_enum_old" USING "status"::"text"::"administration"."transaction_status_enum_old"`);
        await queryRunner.query(`ALTER TABLE "administration"."transaction" ALTER COLUMN "status" SET DEFAULT 'pending'`);
        await queryRunner.query(`DROP TYPE "administration"."transaction_status_enum"`);
        await queryRunner.query(`ALTER TYPE "administration"."transaction_status_enum_old" RENAME TO "transaction_status_enum"`);
    }

}
