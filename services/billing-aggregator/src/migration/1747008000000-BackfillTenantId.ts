import { MigrationInterface, QueryRunner } from "typeorm";

export class BackfillTenantId1747008000000 implements MigrationInterface {
  name = "BackfillTenantId1747008000000";

  public async up(queryRunner: QueryRunner): Promise<void> {
    // Add column as nullable if it doesn't already exist
    const hasColumn = await queryRunner.hasColumn("tenant_billing", "tenant_id");
    if (!hasColumn) {
      await queryRunner.query(`ALTER TABLE "tenant_billing" ADD COLUMN "tenant_id" VARCHAR`);
    }

    // billingId FK was removed from the tenant table when billing moved to billing-aggregator.
    // Only attempt backfill if the column still exists (it won't on new deployments).
    const billingIdExists = await queryRunner.hasColumn("tenant", "billingId");
    if (billingIdExists) {
      await queryRunner.query(`
        UPDATE "tenant_billing" tb
        SET "tenant_id" = t."tenant_id"
        FROM "tenant" t
        WHERE t."billingId" = tb."id"
          AND (tb."tenant_id" IS NULL OR tb."tenant_id" = '')
      `);
    }

    // Only enforce NOT NULL when every row has been populated.
    const [{ nullCount }] = await queryRunner.query(`
      SELECT COUNT(*)::int AS "nullCount"
      FROM "tenant_billing"
      WHERE "tenant_id" IS NULL OR "tenant_id" = ''
    `);

    if (nullCount === 0) {
      await queryRunner.query(`
        ALTER TABLE "tenant_billing" ALTER COLUMN "tenant_id" SET NOT NULL
      `);
    }

    await queryRunner.query(`
      CREATE UNIQUE INDEX IF NOT EXISTS "idx_tenant_billing_tenant_id"
      ON "tenant_billing" ("tenant_id")
      WHERE "tenant_id" IS NOT NULL
    `);
  }

  public async down(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(`DROP INDEX IF EXISTS "idx_tenant_billing_tenant_id"`);
    await queryRunner.query(`ALTER TABLE "tenant_billing" ALTER COLUMN "tenant_id" DROP NOT NULL`);
  }
}
