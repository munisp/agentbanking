import { MigrationInterface, QueryRunner } from "typeorm";

export class AddTenantBillingColumns1751500000000 implements MigrationInterface {
  name = "AddTenantBillingColumns1751500000000";

  public async up(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(`
      DO $$ BEGIN
        CREATE TYPE tenant_plan_enum AS ENUM ('standard', 'premium', 'enterprise');
      EXCEPTION WHEN duplicate_object THEN NULL; END $$
    `);
    await queryRunner.query(`
      DO $$ BEGIN
        CREATE TYPE tenant_billingperiod_enum AS ENUM ('monthly', 'annual');
      EXCEPTION WHEN duplicate_object THEN NULL; END $$
    `);

    if (!(await queryRunner.hasColumn("tenant", "plan"))) {
      await queryRunner.query(
        `ALTER TABLE "tenant" ADD COLUMN "plan" tenant_plan_enum DEFAULT 'standard'`
      );
    }
    if (!(await queryRunner.hasColumn("tenant", "billingPeriod"))) {
      await queryRunner.query(
        `ALTER TABLE "tenant" ADD COLUMN "billingPeriod" tenant_billingperiod_enum DEFAULT 'monthly'`
      );
    }
  }

  public async down(queryRunner: QueryRunner): Promise<void> {
    if (await queryRunner.hasColumn("tenant", "plan")) {
      await queryRunner.query(`ALTER TABLE "tenant" DROP COLUMN "plan"`);
    }
    if (await queryRunner.hasColumn("tenant", "billingPeriod")) {
      await queryRunner.query(`ALTER TABLE "tenant" DROP COLUMN "billingPeriod"`);
    }
  }
}
