import { MigrationInterface, QueryRunner } from "typeorm";

export class CreateBillingInvoice1751600000000 implements MigrationInterface {
  name = "CreateBillingInvoice1751600000000";

  public async up(queryRunner: QueryRunner): Promise<void> {
    const exists = await queryRunner.hasTable("billing_invoice");
    if (exists) return;

    await queryRunner.query(`
      DO $$ BEGIN
        CREATE TYPE billing_invoice_status_enum AS ENUM ('draft', 'issued', 'paid', 'overdue', 'void');
      EXCEPTION WHEN duplicate_object THEN NULL; END $$
    `);

    await queryRunner.query(`
      CREATE TABLE "billing_invoice" (
        "id"             SERIAL PRIMARY KEY,
        "tenant_id"       VARCHAR         NOT NULL,
        "invoice_number" VARCHAR(64)     NOT NULL UNIQUE,
        "plan"           VARCHAR(32),
        "period_start"   TIMESTAMP       NOT NULL,
        "period_end"     TIMESTAMP       NOT NULL,
        "subtotal"       DECIMAL(15, 2)  NOT NULL DEFAULT 0,
        "tax_rate"       DECIMAL(6, 3)   NOT NULL DEFAULT 0,
        "tax_amount"     DECIMAL(15, 2)  NOT NULL DEFAULT 0,
        "total"          DECIMAL(15, 2)  NOT NULL DEFAULT 0,
        "currency"       VARCHAR(3)      NOT NULL DEFAULT 'NGN',
        "status"         billing_invoice_status_enum NOT NULL DEFAULT 'issued',
        "due_date"       TIMESTAMP       NOT NULL,
        "paid_at"        TIMESTAMP,
        "payment_ref"    VARCHAR(64),
        "line_items"     JSONB           NOT NULL DEFAULT '[]',
        "created_at"     TIMESTAMP       NOT NULL DEFAULT now(),
        "updated_at"     TIMESTAMP       NOT NULL DEFAULT now(),
        "deleted_at"     TIMESTAMP
      )
    `);

    await queryRunner.query(`
      CREATE INDEX "idx_billing_invoice_tenant_id" ON "billing_invoice" ("tenant_id")
    `);
  }

  public async down(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(`DROP TABLE IF EXISTS "billing_invoice"`);
    await queryRunner.query(`DROP TYPE IF EXISTS "billing_invoice_status_enum"`);
  }
}
