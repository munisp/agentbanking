import { MigrationInterface, QueryRunner } from "typeorm";

export class AddMissingBillingColumns1747094400000 implements MigrationInterface {
  name = "AddMissingBillingColumns1747094400000";

  private async addColumnIfMissing(
    queryRunner: QueryRunner,
    table: string,
    column: string,
    definition: string,
  ) {
    const exists = await queryRunner.hasColumn(table, column);
    if (!exists) {
      await queryRunner.query(`ALTER TABLE "${table}" ADD COLUMN "${column}" ${definition}`);
    }
  }

  public async up(queryRunner: QueryRunner): Promise<void> {
    // Enum types — create if they don't exist
    await queryRunner.query(`
      DO $$ BEGIN
        CREATE TYPE billing_plan_enum AS ENUM ('standard', 'premium', 'enterprise');
      EXCEPTION WHEN duplicate_object THEN NULL; END $$
    `);
    await queryRunner.query(`
      DO $$ BEGIN
        CREATE TYPE billing_model_enum AS ENUM ('revenue_share', 'subscription', 'hybrid');
      EXCEPTION WHEN duplicate_object THEN NULL; END $$
    `);
    await queryRunner.query(`
      DO $$ BEGIN
        CREATE TYPE billing_status_enum AS ENUM ('ACTIVE', 'PAST_DUE', 'SUSPENDED');
      EXCEPTION WHEN duplicate_object THEN NULL; END $$
    `);

    await this.addColumnIfMissing(
      queryRunner, "tenant_billing", "plan",
      `billing_plan_enum NOT NULL DEFAULT 'standard'`,
    );
    await this.addColumnIfMissing(
      queryRunner, "tenant_billing", "billing_model",
      `billing_model_enum NOT NULL DEFAULT 'revenue_share'`,
    );
    await this.addColumnIfMissing(
      queryRunner, "tenant_billing", "status",
      `billing_status_enum NOT NULL DEFAULT 'ACTIVE'`,
    );
    await this.addColumnIfMissing(
      queryRunner, "tenant_billing", "revenue_share_config",
      `JSONB`,
    );
    await this.addColumnIfMissing(
      queryRunner, "tenant_billing", "subscription_config",
      `JSONB`,
    );
    await this.addColumnIfMissing(
      queryRunner, "tenant_billing", "hybrid_config",
      `JSONB`,
    );
    await this.addColumnIfMissing(
      queryRunner, "tenant_billing", "currency",
      `VARCHAR(3) NOT NULL DEFAULT 'NGN'`,
    );
    await this.addColumnIfMissing(
      queryRunner, "tenant_billing", "effective_date",
      `TIMESTAMP`,
    );
    await this.addColumnIfMissing(
      queryRunner, "tenant_billing", "contract_end_date",
      `TIMESTAMP`,
    );
    await this.addColumnIfMissing(
      queryRunner, "tenant_billing", "auto_renew",
      `BOOLEAN NOT NULL DEFAULT TRUE`,
    );
    await this.addColumnIfMissing(
      queryRunner, "tenant_billing", "tigerbeetle_account_id",
      `VARCHAR(64)`,
    );
    await this.addColumnIfMissing(
      queryRunner, "tenant_billing", "kafka_topic_prefix",
      `VARCHAR(64)`,
    );
    await this.addColumnIfMissing(
      queryRunner, "tenant_billing", "jurisdiction",
      `VARCHAR(32)`,
    );
    await this.addColumnIfMissing(
      queryRunner, "tenant_billing", "credits_balance",
      `DECIMAL(15, 2) NOT NULL DEFAULT 0`,
    );
    await this.addColumnIfMissing(
      queryRunner, "tenant_billing", "grace_period_end",
      `TIMESTAMP`,
    );
    await this.addColumnIfMissing(
      queryRunner, "tenant_billing", "grace_period_reason",
      `VARCHAR(256)`,
    );
    await this.addColumnIfMissing(
      queryRunner, "tenant_billing", "last_payment_date",
      `TIMESTAMP`,
    );
    await this.addColumnIfMissing(
      queryRunner, "tenant_billing", "last_payment_reference",
      `VARCHAR(64)`,
    );
    await this.addColumnIfMissing(
      queryRunner, "tenant_billing", "total_paid_ytd",
      `DECIMAL(15, 2) NOT NULL DEFAULT 0`,
    );
    await this.addColumnIfMissing(
      queryRunner, "tenant_billing", "total_outstanding",
      `DECIMAL(15, 2) NOT NULL DEFAULT 0`,
    );
  }

  public async down(queryRunner: QueryRunner): Promise<void> {
    const cols = [
      "plan", "billing_model", "status", "revenue_share_config", "subscription_config",
      "hybrid_config", "currency", "effective_date", "contract_end_date", "auto_renew",
      "tigerbeetle_account_id", "kafka_topic_prefix", "jurisdiction", "credits_balance",
      "grace_period_end", "grace_period_reason", "last_payment_date", "last_payment_reference",
      "total_paid_ytd", "total_outstanding",
    ];
    for (const col of cols) {
      const exists = await queryRunner.hasColumn("tenant_billing", col);
      if (exists) {
        await queryRunner.query(`ALTER TABLE "tenant_billing" DROP COLUMN "${col}"`);
      }
    }
  }
}
