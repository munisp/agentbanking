import { MigrationInterface, QueryRunner } from "typeorm";

export class Migration1740020303237 implements MigrationInterface {
    name = 'Migration1740020303237'

    public async up(queryRunner: QueryRunner): Promise<void> {
        await queryRunner.query(`CREATE INDEX "IDX_bd4c360c8e5745e921df060744" ON "administration"."transaction" ("created_at") `);
    }

    public async down(queryRunner: QueryRunner): Promise<void> {
        await queryRunner.query(`DROP INDEX "administration"."IDX_bd4c360c8e5745e921df060744"`);
    }

}
