import { MigrationInterface, QueryRunner } from "typeorm";

export class CreateBillingPlanDefinitions1750000000000 implements MigrationInterface {
  name = "CreateBillingPlanDefinitions1750000000000";

  public async up(queryRunner: QueryRunner): Promise<void> {
    const exists = await queryRunner.hasTable("billing_plan_definitions");
    if (exists) return;

    await queryRunner.query(`
      CREATE TABLE "billing_plan_definitions" (
        "id"          SERIAL PRIMARY KEY,
        "name"        VARCHAR(64)     NOT NULL UNIQUE,
        "label"       VARCHAR(128)    NOT NULL,
        "monthly_fee" DECIMAL(15, 2)  NOT NULL DEFAULT 0,
        "currency"    VARCHAR(3)      NOT NULL DEFAULT 'NGN',
        "description" TEXT,
        "features"    JSONB           NOT NULL DEFAULT '[]',
        "popular"     BOOLEAN         NOT NULL DEFAULT FALSE,
        "created_at"  TIMESTAMP       NOT NULL DEFAULT now(),
        "updated_at"  TIMESTAMP       NOT NULL DEFAULT now(),
        "deleted_at"  TIMESTAMP
      )
    `);

    await queryRunner.query(`
      INSERT INTO "billing_plan_definitions" ("name", "label", "monthly_fee", "currency", "description", "features", "popular")
      VALUES
        ('standard',   'Standard Plan',   50000,  'NGN', 'Essential features for growing agents', '["Up to 50 agents", "Basic reporting", "Email support"]', FALSE),
        ('premium',    'Premium Plan',    150000, 'NGN', 'Advanced tools for established networks', '["Up to 200 agents", "Advanced analytics", "Priority support", "API access"]', TRUE),
        ('enterprise', 'Enterprise Plan', 500000, 'NGN', 'Full platform access for large deployments', '["Unlimited agents", "Custom integrations", "Dedicated support", "SLA guarantee", "White-label option"]', FALSE)
      ON CONFLICT ("name") DO NOTHING
    `);
  }

  public async down(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(`DROP TABLE IF EXISTS "billing_plan_definitions"`);
  }
}
