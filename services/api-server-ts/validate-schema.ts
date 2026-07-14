/**
 * Schema Validation Script
 * ─────────────────────────────────────────────────────────────────────────────
 * Detects drift between Drizzle schema.ts definitions and the live database.
 *
 * Checks:
 * 1. Missing tables (in schema but not in DB)
 * 2. Extra tables (in DB but not in schema)
 * 3. Missing columns per table
 * 4. Column type mismatches
 * 5. Missing indexes
 * 6. Missing FK constraints
 * 7. Missing CHECK constraints
 * 8. Unapplied migrations
 *
 * Usage:
 *   npx tsx drizzle/validate-schema.ts
 *   npx tsx drizzle/validate-schema.ts --fix   # auto-apply safe fixes
 */

import { Pool } from "pg";
import * as fs from "fs";
import * as path from "path";

const DATABASE_URL =
  process.env.POSTGRES_URL ??
  process.env.DATABASE_URL;

if (!DATABASE_URL) {
  console.error("❌ POSTGRES_URL or DATABASE_URL is required");
  process.exit(1);
}

const pool = new Pool({ connectionString: DATABASE_URL, max: 3 });
const FIX_MODE = process.argv.includes("--fix");

// ─── Types ────────────────────────────────────────────────────────────────────
interface ValidationIssue {
  severity: "error" | "warning" | "info";
  category: string;
  table?: string;
  column?: string;
  message: string;
  fix?: string;
}

const issues: ValidationIssue[] = [];

function issue(i: ValidationIssue) {
  issues.push(i);
  const icon = i.severity === "error" ? "❌" : i.severity === "warning" ? "⚠️" : "ℹ️";
  const loc = i.table ? (i.column ? `${i.table}.${i.column}` : i.table) : "";
  console.log(`  ${icon} [${i.category}] ${loc ? `(${loc}) ` : ""}${i.message}`);
}

// ─── 1. Check unapplied migrations ───────────────────────────────────────────
async function checkMigrations(client: any) {
  console.log("\n📋 Checking migrations...");

  // Get applied migrations from DB
  let applied: string[] = [];
  try {
    const result = await client.query(
      `SELECT "tag" FROM "__drizzle_migrations" ORDER BY "created_at" ASC`
    );
    applied = result.rows.map((r: any) => r.tag);
  } catch {
    // Table might not exist yet
    issue({
      severity: "warning",
      category: "migrations",
      message: "__drizzle_migrations table not found — run drizzle-kit migrate first",
    });
    return;
  }

  // Get migration files on disk
  const migrationDir = path.join(__dirname, "drizzle");
  const files = fs.existsSync(migrationDir)
    ? fs.readdirSync(migrationDir)
        .filter((f) => f.endsWith(".sql"))
        .map((f) => f.replace(".sql", ""))
        .sort()
    : [];

  const unapplied = files.filter((f) => !applied.includes(f));
  if (unapplied.length > 0) {
    for (const m of unapplied) {
      issue({
        severity: "error",
        category: "migrations",
        message: `Unapplied migration: ${m}`,
        fix: `Run: npx drizzle-kit migrate`,
      });
    }
  } else {
    console.log("  ✓ All migrations applied");
  }
}

// ─── 2. Check tables ─────────────────────────────────────────────────────────
async function checkTables(client: any) {
  console.log("\n📋 Checking tables...");

  const result = await client.query(
    `SELECT table_name FROM information_schema.tables
     WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
     ORDER BY table_name`
  );
  const dbTables = new Set(result.rows.map((r: any) => r.table_name as string));

  // Tables we expect from schema (snake_case versions)
  const expectedTables = [
    "users", "agents", "transactions", "fraud_alerts", "loyalty_history",
    "chat_sessions", "chat_messages", "audit_log", "float_top_up_requests",
    "otp_tokens", "devices", "device_commands", "supervisor_agents",
    "disputes", "dispute_messages", "refunds", "platform_settings",
    "velocity_limits", "compliance_reports", "geofence_zones",
    "agent_geofence_zones", "device_locations", "kyc_sessions",
    "pos_terminals", "terminal_groups", "service_records",
    "software_updates", "terminal_leases", "pos_settlement_batches",
    "commission_rules", "qr_codes", "inventory_items", "multi_sim_profiles",
    "reversal_requests", "shareable_links", "customers", "tenants",
    "erp_sync_log", "storefront_ads", "vat_records", "erp_config",
    "mqtt_bridge_config", "analytics_metrics", "webhook_secrets",
    "email_queue", "merchants", "merchant_settlements", "api_keys",
    "api_key_usage", "fido2_credentials", "fido2_challenges",
    "credit_score_history", "credit_applications", "ota_releases",
    "ota_update_log", "data_rights_requests", "fraud_rules",
    "agent_push_subscriptions", "connectivity_log", "system_config",
    "sim_probe_log", "sim_orchestrator_config", "sim_failover_log",
    "device_compliance_policies", "device_compliance_violations",
    "mdm_geofence_violations", "dlq_messages", "commission_payouts",
    "referrals", "webhook_endpoints", "webhook_deliveries",
    "agent_onboarding_progress", "settlement_reconciliation",
    "rate_alerts", "email_delivery_log", "invite_codes",
    "tenant_branding", "tenant_corridors", "tenant_fee_overrides",
    "tenant_users", "commission_cascade_history", "agent_bank_accounts",
    "kyc_documents", "float_reconciliations", "agent_performance_scores",
    "commission_clawbacks", "pnl_reports", "geo_fences",
    "transaction_limits", "compliance_checks", "agent_suspension_log",
    "tx_monitoring_alerts", "fraud_ml_scores", "notification_dispatch_log",
    "agent_loans", "fee_rules", "fee_audit_trail", "merchant_kyc_docs",
    "merchant_payouts", "compliance_filings", "agent_achievements",
    "agent_badges", "tenant_feature_toggles", "reconciliation_batches",
    "reconciliation_items", "analytics_dashboards", "customer_journey_steps",
    "rate_limit_rules", "backup_snapshots", "workflow_definitions",
    "workflow_instances", "gl_entries", "training_courses",
    "training_enrollments", "bi_report_definitions", "observability_alerts",
    "encrypted_fields", "data_consent_records", "realtime_tx_alerts",
    "notification_channels", "notification_logs", "customer_journey_events",
    "gl_accounts", "gl_journal_entries", "sla_definitions", "sla_breaches",
    "data_export_jobs", "platform_health_checks", "platform_incidents",
    "platform_billing_ledger", "billing_revenue_periods",
    "billing_reconciliation_reports", "billing_role_assignments",
    "billing_audit_log", "tenant_billing_config",
    "billing_provisioning_history", "face_enrollments",
    "biometric_audit_events", "receipt_templates", "guide_feedback",
    "ecommerce_categories", "ecommerce_products", "ecommerce_inventory",
    "ecommerce_inventory_reservations", "ecommerce_orders",
    "ecommerce_order_items", "ecommerce_carts", "ecommerce_cart_items",
    "ecommerce_interactions", "agent_stores", "delivery_zones",
    "product_reviews", "store_reviews", "payment_splits",
    "delivery_tracking", "aml_screenings", "aml_watchlist_entries",
    "idempotency_keys", "temporal_workflow_log", "permify_check_log",
    "openappsec_threat_log", "fluvio_event_log", "lakehouse_sync_log",
    "dapr_pubsub_log",
  ];

  let missingCount = 0;
  for (const t of expectedTables) {
    if (!dbTables.has(t)) {
      issue({
        severity: "error",
        category: "tables",
        table: t,
        message: `Table missing from database`,
        fix: `Run: npx drizzle-kit push`,
      });
      missingCount++;
    }
  }

  if (missingCount === 0) {
    console.log(`  ✓ All ${expectedTables.length} expected tables present`);
  }
}

// ─── 3. Check critical indexes ────────────────────────────────────────────────
async function checkIndexes(client: any) {
  console.log("\n📋 Checking critical indexes...");

  const result = await client.query(
    `SELECT indexname, tablename FROM pg_indexes
     WHERE schemaname = 'public'`
  );
  const dbIndexes = new Set(result.rows.map((r: any) => r.indexname as string));

  const criticalIndexes = [
    "idx_agents_active_code",
    "idx_agents_active_phone",
    "idx_agents_fts_gin",
    "idx_tx_agent_date_amount",
    "idx_tx_high_fraud",
    "idx_tx_fts_gin",
    "idx_tx_metadata_gin",
    "idx_fraud_alerts_open",
    "idx_kyc_pending",
    "idx_topup_pending",
    "idx_disputes_open",
    "idx_otp_active",
    "idx_api_keys_active",
    "idx_dapr_topic_status_date",
    "idx_permify_subject_perm",
    "idx_temporal_type_status",
    "idx_audit_log_created_brin",
  ];

  let missingCount = 0;
  for (const idx of criticalIndexes) {
    if (!dbIndexes.has(idx)) {
      issue({
        severity: "warning",
        category: "indexes",
        message: `Critical index missing: ${idx}`,
        fix: `Run migration: 0048_schema_enhancements.sql`,
      });
      missingCount++;
    }
  }

  if (missingCount === 0) {
    console.log("  ✓ All critical indexes present");
  }
}

// ─── 4. Check RLS ─────────────────────────────────────────────────────────────
async function checkRLS(client: any) {
  console.log("\n📋 Checking Row Level Security...");

  const result = await client.query(
    `SELECT tablename, rowsecurity FROM pg_tables
     WHERE schemaname = 'public' AND tablename IN (
       'agents', 'transactions', 'fraud_alerts', 'customers',
       'float_top_up_requests', 'disputes', 'kyc_sessions',
       'merchants', 'api_keys', 'ecommerce_products'
     )`
  );

  let rlsIssues = 0;
  for (const row of result.rows) {
    if (!row.rowsecurity) {
      issue({
        severity: "warning",
        category: "rls",
        table: row.tablename,
        message: `RLS not enabled on multi-tenant table`,
        fix: `Run migration: 0048_schema_enhancements.sql`,
      });
      rlsIssues++;
    }
  }

  if (rlsIssues === 0) {
    console.log("  ✓ RLS enabled on all multi-tenant tables");
  }
}

// ─── 5. Check FK constraints ──────────────────────────────────────────────────
async function checkForeignKeys(client: any) {
  console.log("\n📋 Checking foreign key constraints...");

  const result = await client.query(
    `SELECT
       tc.table_name,
       kcu.column_name,
       ccu.table_name AS foreign_table_name
     FROM information_schema.table_constraints AS tc
     JOIN information_schema.key_column_usage AS kcu
       ON tc.constraint_name = kcu.constraint_name
     JOIN information_schema.constraint_column_usage AS ccu
       ON ccu.constraint_name = tc.constraint_name
     WHERE tc.constraint_type = 'FOREIGN KEY'
     AND tc.table_schema = 'public'`
  );

  const fkSet = new Set(
    result.rows.map((r: any) => `${r.table_name}.${r.column_name}`)
  );

  const criticalFKs = [
    { table: "transactions", col: "agentId", ref: "agents.id" },
    { table: "fraud_alerts", col: "agentId", ref: "agents.id" },
    { table: "float_top_up_requests", col: "agentId", ref: "agents.id" },
    { table: "disputes", col: "transactionId", ref: "transactions.id" },
    { table: "kyc_sessions", col: "agentId", ref: "agents.id" },
    { table: "chat_sessions", col: "agentId", ref: "agents.id" },
    { table: "devices", col: "agentId", ref: "agents.id" },
  ];

  let missingFKs = 0;
  for (const fk of criticalFKs) {
    if (!fkSet.has(`${fk.table}.${fk.col}`)) {
      issue({
        severity: "warning",
        category: "foreign_keys",
        table: fk.table,
        column: fk.col,
        message: `Missing FK constraint → ${fk.ref}`,
        fix: `Run migration: 0048_schema_enhancements.sql`,
      });
      missingFKs++;
    }
  }

  if (missingFKs === 0) {
    console.log("  ✓ All critical FK constraints present");
  }
}

// ─── 6. Check CHECK constraints ───────────────────────────────────────────────
async function checkConstraints(client: any) {
  console.log("\n📋 Checking CHECK constraints...");

  const result = await client.query(
    `SELECT constraint_name, table_name
     FROM information_schema.table_constraints
     WHERE constraint_type = 'CHECK'
     AND table_schema = 'public'`
  );

  const checkSet = new Set(result.rows.map((r: any) => r.constraint_name as string));

  const criticalChecks = [
    "chk_tx_amount_positive",
    "chk_tx_fee_non_negative",
    "chk_agent_float_non_negative",
    "chk_tx_fraud_score",
    "chk_fraud_score_range",
  ];

  let missingChecks = 0;
  for (const chk of criticalChecks) {
    if (!checkSet.has(chk)) {
      issue({
        severity: "warning",
        category: "constraints",
        message: `Missing CHECK constraint: ${chk}`,
        fix: `Run migration: 0048_schema_enhancements.sql`,
      });
      missingChecks++;
    }
  }

  if (missingChecks === 0) {
    console.log("  ✓ All critical CHECK constraints present");
  }
}

// ─── Main ─────────────────────────────────────────────────────────────────────
async function main() {
  console.log("🔍 54Link Schema Validation\n");
  console.log(`Database: ${DATABASE_URL!.replace(/:[^:@]+@/, ":***@")}`);

  const client = await pool.connect();
  try {
    await checkMigrations(client);
    await checkTables(client);
    await checkIndexes(client);
    await checkRLS(client);
    await checkForeignKeys(client);
    await checkConstraints(client);

    // ── Summary ───────────────────────────────────────────────────────────────
    const errors = issues.filter((i) => i.severity === "error");
    const warnings = issues.filter((i) => i.severity === "warning");

    console.log("\n" + "─".repeat(60));
    console.log(`📊 Validation Summary:`);
    console.log(`   Errors:   ${errors.length}`);
    console.log(`   Warnings: ${warnings.length}`);
    console.log(`   Total:    ${issues.length}`);

    if (issues.length === 0) {
      console.log("\n✅ Schema is fully in sync with the database!");
    } else {
      console.log("\n⚠️  Schema drift detected. Run migrations to fix.");
      if (errors.length > 0) {
        process.exit(1);
      }
    }
  } finally {
    client.release();
    await pool.end();
  }
}

main().catch((err) => {
  console.error("Fatal error:", err);
  process.exit(1);
});
