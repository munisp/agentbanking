#!/usr/bin/env node
/**
 * 54Link POS Shell — Sprint 42 Production Seed (43 Missing Tables)
 * Usage: node scripts/seed-production-sprint42.mjs
 */
import pg from "pg";
import crypto from "crypto";
const { Pool } = pg;
const DATABASE_URL = process.env.POSTGRES_URL || process.env.DATABASE_URL;
if (!DATABASE_URL) { console.error("POSTGRES_URL not set"); process.exit(1); }
const pool = new Pool({ connectionString: DATABASE_URL, max: 5 });

const rand = (min, max) => Math.floor(Math.random() * (max - min + 1)) + min;
const pick = (arr) => arr[rand(0, arr.length - 1)];
const uuid = () => crypto.randomUUID();
const daysAgo = (d) => new Date(Date.now() - d * 86400000);

const NAMES = ["Chioma Eze","Emeka Obi","Fatima Bello","Adamu Yusuf","Grace Okonkwo","Ibrahim Musa","Joy Nwosu","Kemi Ade","Ladi Bako","Musa Dan"];
const CITIES = ["Lagos","Abuja","Kano","Port Harcourt","Enugu","Kaduna","Ibadan","Jos","Benin","Calabar"];
const STATUSES = ["active","inactive","pending","completed","failed","approved","rejected"];

async function seed() {
  const client = await pool.connect();
  try {
    await client.query("BEGIN");
    let total = 0;

    // ── agent_geofence_zones (10 rows) ──
    for (let i = 0; i < 10; i++) {
      await client.query(
        `INSERT INTO "agent_geofence_zones" ("agent_id", "zone_id", "assigned_at", "assigned_by") VALUES ($1, $2, $3, $4) ON CONFLICT DO NOTHING`,
        [rand(1, 10), rand(1, 100), daysAgo(rand(0, 90)), `seed-${uuid().slice(0,8)}`]
      );
    }
    total += 10;
    console.log("  ✅ agent_geofence_zones: 10 rows");

    // ── agent_push_subscriptions (10 rows) ──
    for (let i = 0; i < 10; i++) {
      await client.query(
        `INSERT INTO "agent_push_subscriptions" ("agent_code", "endpoint", "p256dh_key", "auth_key", "user_agent", "created_at", "updated_at", "last_alerted_at") VALUES ($1, $2, $3, $4, $5, $6, $7, $8) ON CONFLICT DO NOTHING`,
        [uuid(), `https://api.54link.ng/${uuid()}`, uuid(), uuid(), `seed-${uuid().slice(0,8)}`, daysAgo(rand(0, 90)), daysAgo(rand(0, 90)), daysAgo(rand(0, 90))]
      );
    }
    total += 10;
    console.log("  ✅ agent_push_subscriptions: 10 rows");

    // ── api_key_usage (10 rows) ──
    for (let i = 0; i < 10; i++) {
      await client.query(
        `INSERT INTO "api_key_usage" ("api_key_id", "endpoint", "method", "status_code", "response_ms", "ip_address", "created_at") VALUES ($1, $2, $3, $4, $5, $6, $7) ON CONFLICT DO NOTHING`,
        [rand(1, 100), `https://api.54link.ng/${uuid()}`, pick(["standard","premium","basic","custom"]), rand(1, 100), rand(1, 100), `192.168.${rand(1,255)}.${rand(1,255)}`, daysAgo(rand(0, 90))]
      );
    }
    total += 10;
    console.log("  ✅ api_key_usage: 10 rows");

    // ── chat_messages (20 rows) ──
    for (let i = 0; i < 20; i++) {
      await client.query(
        `INSERT INTO "chat_messages" ("session_id", "sender_name", "content", "is_read", "created_at") VALUES ($1, $2, $3, $4, $5) ON CONFLICT DO NOTHING`,
        [rand(1, 100), pick(NAMES), `Seed data - ${uuid().slice(0,8)}`, Math.random() > 0.5, daysAgo(rand(0, 90))]
      );
    }
    total += 20;
    console.log("  ✅ chat_messages: 20 rows");

    // ── credit_applications (10 rows) ──
    for (let i = 0; i < 10; i++) {
      await client.query(
        `INSERT INTO "credit_applications" ("agent_id", "requested_amount", "approved_amount", "interest_rate", "term_days", "score_at_application", "reviewed_by", "review_note", "reviewed_at", "disbursed_at", "due_at", "repaid_at", "created_at", "updated_at") VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14) ON CONFLICT DO NOTHING`,
        [rand(1, 10), (rand(100, 99999) / 100).toFixed(2), (rand(100, 99999) / 100).toFixed(2), (rand(100, 99999) / 100).toFixed(2), rand(1, 100), rand(1, 100), `seed-${uuid().slice(0,8)}`, `seed-${uuid().slice(0,8)}`, daysAgo(rand(0, 90)), daysAgo(rand(0, 90)), daysAgo(rand(0, 90)), daysAgo(rand(0, 90)), daysAgo(rand(0, 90)), daysAgo(rand(0, 90))]
      );
    }
    total += 10;
    console.log("  ✅ credit_applications: 10 rows");

    // ── credit_score_history (10 rows) ──
    for (let i = 0; i < 10; i++) {
      await client.query(
        `INSERT INTO "credit_score_history" ("agent_id", "score", "computed_at") VALUES ($1, $2, $3) ON CONFLICT DO NOTHING`,
        [rand(1, 10), rand(1, 100), daysAgo(rand(0, 90))]
      );
    }
    total += 10;
    console.log("  ✅ credit_score_history: 10 rows");

    // ── data_rights_requests (10 rows) ──
    for (let i = 0; i < 10; i++) {
      await client.query(
        `INSERT INTO "data_rights_requests" ("request_type", "requester_id", "requester_type", "requester_email", "status", "export_file_url", "processed_by", "processed_at", "notes", "tenant_id", "created_at", "updated_at") VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12) ON CONFLICT DO NOTHING`,
        [pick(["standard","premium","basic","custom"]), rand(1, 100), pick(["standard","premium","basic","custom"]), `agent${rand(1,10)}@54link.ng`, pick(STATUSES), `https://api.54link.ng/${uuid()}`, `seed-${uuid().slice(0,8)}`, daysAgo(rand(0, 90)), `Seed data - ${uuid().slice(0,8)}`, rand(1, 3), daysAgo(rand(0, 90)), daysAgo(rand(0, 90))]
      );
    }
    total += 10;
    console.log("  ✅ data_rights_requests: 10 rows");

    // ── device_commands (10 rows) ──
    for (let i = 0; i < 10; i++) {
      await client.query(
        `INSERT INTO "device_commands" ("device_id", "command", "status", "issued_by", "issued_at", "acknowledged_at", "completed_at", "error_message", "executed_at", "created_at") VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10) ON CONFLICT DO NOTHING`,
        [rand(1, 20), `seed-${uuid().slice(0,8)}`, pick(STATUSES), `seed-${uuid().slice(0,8)}`, daysAgo(rand(0, 90)), daysAgo(rand(0, 90)), daysAgo(rand(0, 90)), `Seed data - ${uuid().slice(0,8)}`, daysAgo(rand(0, 90)), daysAgo(rand(0, 90))]
      );
    }
    total += 10;
    console.log("  ✅ device_commands: 10 rows");

    // ── device_compliance_violations (10 rows) ──
    for (let i = 0; i < 10; i++) {
      await client.query(
        `INSERT INTO "device_compliance_violations" ("device_id", "policy_id", "serial_number", "agent_code", "violation_type", "severity", "status", "enforcement_action", "resolved_at", "resolved_by", "detected_at", "created_at") VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12) ON CONFLICT DO NOTHING`,
        [rand(1, 20), rand(1, 100), `seed-${uuid().slice(0,8)}`, uuid(), pick(["standard","premium","basic","custom"]), `seed-${uuid().slice(0,8)}`, pick(STATUSES), `seed-${uuid().slice(0,8)}`, daysAgo(rand(0, 90)), `seed-${uuid().slice(0,8)}`, daysAgo(rand(0, 90)), daysAgo(rand(0, 90))]
      );
    }
    total += 10;
    console.log("  ✅ device_compliance_violations: 10 rows");

    // ── device_locations (10 rows) ──
    for (let i = 0; i < 10; i++) {
      await client.query(
        `INSERT INTO "device_locations" ("device_id", "agent_id", "latitude", "longitude", "within_zone", "reported_at", "lat", "lng", "accuracy", "altitude", "speed", "heading", "source", "created_at") VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14) ON CONFLICT DO NOTHING`,
        [rand(1, 20), rand(1, 10), (rand(100, 99999) / 100).toFixed(2), (rand(100, 99999) / 100).toFixed(2), Math.random() > 0.5, daysAgo(rand(0, 90)), (rand(100, 99999) / 100).toFixed(2), (rand(100, 99999) / 100).toFixed(2), (rand(100, 99999) / 100).toFixed(2), (rand(100, 99999) / 100).toFixed(2), (rand(100, 99999) / 100).toFixed(2), (rand(100, 99999) / 100).toFixed(2), `seed-${uuid().slice(0,8)}`, daysAgo(rand(0, 90))]
      );
    }
    total += 10;
    console.log("  ✅ device_locations: 10 rows");

    // ── dispute_messages (20 rows) ──
    for (let i = 0; i < 20; i++) {
      await client.query(
        `INSERT INTO "dispute_messages" ("dispute_id", "author_id", "author_name", "author_role", "message", "sender_type", "sender_name", "content", "attachment_url", "created_at") VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10) ON CONFLICT DO NOTHING`,
        [rand(1, 100), rand(1, 100), pick(NAMES), `seed-${uuid().slice(0,8)}`, `Seed data - ${uuid().slice(0,8)}`, pick(["standard","premium","basic","custom"]), pick(NAMES), `Seed data - ${uuid().slice(0,8)}`, `https://api.54link.ng/${uuid()}`, daysAgo(rand(0, 90))]
      );
    }
    total += 20;
    console.log("  ✅ dispute_messages: 20 rows");

    // ── dlq_messages (20 rows) ──
    for (let i = 0; i < 20; i++) {
      await client.query(
        `INSERT INTO "dlq_messages" ("topic", "partition", "offset", "error_message", "retry_count", "payload", "status", "resolved_at", "created_at") VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) ON CONFLICT DO NOTHING`,
        [`seed-${uuid().slice(0,8)}`, rand(1, 100), `seed-${uuid().slice(0,8)}`, `Seed data - ${uuid().slice(0,8)}`, rand(0, 10), `seed-${uuid().slice(0,8)}`, pick(STATUSES), daysAgo(rand(0, 90)), daysAgo(rand(0, 90))]
      );
    }
    total += 20;
    console.log("  ✅ dlq_messages: 20 rows");

    // ── email_delivery_log (20 rows) ──
    for (let i = 0; i < 20; i++) {
      await client.query(
        `INSERT INTO "email_delivery_log" ("email_queue_id", "provider_message_id", "to_address", "subject", "status", "opened_at", "clicked_at", "bounced_at", "error_message", "created_at") VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10) ON CONFLICT DO NOTHING`,
        [rand(1, 100), `Seed data - ${uuid().slice(0,8)}`, `seed-${uuid().slice(0,8)}`, `seed-${uuid().slice(0,8)}`, pick(STATUSES), daysAgo(rand(0, 90)), daysAgo(rand(0, 90)), daysAgo(rand(0, 90)), `Seed data - ${uuid().slice(0,8)}`, daysAgo(rand(0, 90))]
      );
    }
    total += 20;
    console.log("  ✅ email_delivery_log: 20 rows");

    // ── email_queue (20 rows) ──
    for (let i = 0; i < 20; i++) {
      await client.query(
        `INSERT INTO "email_queue" ("to_address", "to_name", "subject", "template_name", "sent_at", "error_message", "retry_count", "tenant_id", "created_at") VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) ON CONFLICT DO NOTHING`,
        [`seed-${uuid().slice(0,8)}`, pick(NAMES), `seed-${uuid().slice(0,8)}`, pick(NAMES), daysAgo(rand(0, 90)), `Seed data - ${uuid().slice(0,8)}`, rand(0, 10), rand(1, 3), daysAgo(rand(0, 90))]
      );
    }
    total += 20;
    console.log("  ✅ email_queue: 20 rows");

    // ── erp_config (10 rows) ──
    for (let i = 0; i < 10; i++) {
      await client.query(
        `INSERT INTO "erp_config" ("name", "base_url", "api_key", "username", "database", "sync_enabled", "sync_interval_minutes", "sync_transactions", "sync_agents", "sync_inventory", "last_sync_at", "last_sync_status", "last_sync_error", "last_sync_count", "created_at", "updated_at") VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16) ON CONFLICT DO NOTHING`,
        [pick(NAMES), `https://api.54link.ng/${uuid()}`, uuid(), pick(NAMES), `seed-${uuid().slice(0,8)}`, Math.random() > 0.5, rand(1, 100), Math.random() > 0.5, Math.random() > 0.5, Math.random() > 0.5, daysAgo(rand(0, 90)), pick(STATUSES), `seed-${uuid().slice(0,8)}`, rand(0, 10), daysAgo(rand(0, 90)), daysAgo(rand(0, 90))]
      );
    }
    total += 10;
    console.log("  ✅ erp_config: 10 rows");

    // ── erp_sync_log (10 rows) ──
    for (let i = 0; i < 10; i++) {
      await client.query(
        `INSERT INTO "erp_sync_log" ("entity_type", "entity_id", "erp_doc_type", "erp_doc_name", "error_message", "synced_at", "retry_count", "max_retries", "next_retry_at", "created_at") VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10) ON CONFLICT DO NOTHING`,
        [pick(["standard","premium","basic","custom"]), `seed-${uuid().slice(0,8)}`, pick(["standard","premium","basic","custom"]), pick(NAMES), `Seed data - ${uuid().slice(0,8)}`, daysAgo(rand(0, 90)), rand(0, 10), rand(1, 100), daysAgo(rand(0, 90)), daysAgo(rand(0, 90))]
      );
    }
    total += 10;
    console.log("  ✅ erp_sync_log: 10 rows");

    // ── fido2_challenges (10 rows) ──
    for (let i = 0; i < 10; i++) {
      await client.query(
        `INSERT INTO "fido2_challenges" ("challenge", "user_id", "agent_id", "type", "expires_at", "used_at", "created_at") VALUES ($1, $2, $3, $4, $5, $6, $7) ON CONFLICT DO NOTHING`,
        [`seed-${uuid().slice(0,8)}`, rand(1, 10), rand(1, 10), pick(["standard","premium","basic","custom"]), daysAgo(rand(0, 90)), daysAgo(rand(0, 90)), daysAgo(rand(0, 90))]
      );
    }
    total += 10;
    console.log("  ✅ fido2_challenges: 10 rows");

    // ── fido2_credentials (10 rows) ──
    for (let i = 0; i < 10; i++) {
      await client.query(
        `INSERT INTO "fido2_credentials" ("user_id", "agent_id", "credential_id", "public_key", "counter", "device_type", "last_used_at", "created_at") VALUES ($1, $2, $3, $4, $5, $6, $7, $8) ON CONFLICT DO NOTHING`,
        [rand(1, 10), rand(1, 10), `seed-${uuid().slice(0,8)}`, uuid(), rand(0, 10), pick(["standard","premium","basic","custom"]), daysAgo(rand(0, 90)), daysAgo(rand(0, 90))]
      );
    }
    total += 10;
    console.log("  ✅ fido2_credentials: 10 rows");

    // ── float_topup_requests (10 rows) ──
    for (let i = 0; i < 10; i++) {
      await client.query(
        `INSERT INTO "float_topup_requests" ("agent_id", "requested_amount", "approved_by", "notes", "supervisor_approval_required", "supervisor_approved_by", "supervisor_approved_at", "tenant_id", "created_at", "updated_at") VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10) ON CONFLICT DO NOTHING`,
        [rand(1, 10), (rand(100, 99999) / 100).toFixed(2), `seed-${uuid().slice(0,8)}`, `Seed data - ${uuid().slice(0,8)}`, Math.random() > 0.5, `seed-${uuid().slice(0,8)}`, daysAgo(rand(0, 90)), rand(1, 3), daysAgo(rand(0, 90)), daysAgo(rand(0, 90))]
      );
    }
    total += 10;
    console.log("  ✅ float_topup_requests: 10 rows");

    // ── inventory_items (10 rows) ──
    for (let i = 0; i < 10; i++) {
      await client.query(
        `INSERT INTO "inventory_items" ("sku", "name", "category", "description", "quantity_on_hand", "quantity_reserved", "reorder_point", "unit_cost", "warehouse_location", "supplier_id", "last_restocked_at", "created_at", "updated_at") VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13) ON CONFLICT DO NOTHING`,
        [`seed-${uuid().slice(0,8)}`, pick(NAMES), pick(["standard","premium","basic","custom"]), `Seed data - ${uuid().slice(0,8)}`, rand(1, 100), rand(1, 100), rand(1, 100), (rand(100, 99999) / 100).toFixed(2), pick(CITIES), `seed-${uuid().slice(0,8)}`, daysAgo(rand(0, 90)), daysAgo(rand(0, 90)), daysAgo(rand(0, 90))]
      );
    }
    total += 10;
    console.log("  ✅ inventory_items: 10 rows");

    // ── invite_codes (10 rows) ──
    for (let i = 0; i < 10; i++) {
      await client.query(
        `INSERT INTO "invite_codes" ("code", "max_uses", "used_count", "created_by", "assigned_tenant_id", "partner_name", "partner_email", "notes", "expires_at", "created_at", "updated_at") VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11) ON CONFLICT DO NOTHING`,
        [uuid(), rand(1, 100), rand(0, 10), rand(1, 100), rand(1, 3), pick(NAMES), `agent${rand(1,10)}@54link.ng`, `Seed data - ${uuid().slice(0,8)}`, daysAgo(rand(0, 90)), daysAgo(rand(0, 90)), daysAgo(rand(0, 90))]
      );
    }
    total += 10;
    console.log("  ✅ invite_codes: 10 rows");

    // ── mdm_geofence_violations (10 rows) ──
    for (let i = 0; i < 10; i++) {
      await client.query(
        `INSERT INTO "mdm_geofence_violations" ("device_id", "serial_number", "agent_code", "zone_id", "zone_name", "violation_type", "lat_e6", "lon_e6", "distance_meters", "status", "notified_at", "resolved_at", "detected_at", "created_at") VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14) ON CONFLICT DO NOTHING`,
        [rand(1, 20), `seed-${uuid().slice(0,8)}`, uuid(), rand(1, 100), pick(NAMES), pick(["standard","premium","basic","custom"]), rand(1, 100), rand(1, 100), rand(1, 100), pick(STATUSES), daysAgo(rand(0, 90)), daysAgo(rand(0, 90)), daysAgo(rand(0, 90)), daysAgo(rand(0, 90))]
      );
    }
    total += 10;
    console.log("  ✅ mdm_geofence_violations: 10 rows");

    // ── merchant_settlements (10 rows) ──
    for (let i = 0; i < 10; i++) {
      await client.query(
        `INSERT INTO "merchant_settlements" ("merchant_id", "period", "gross_amount", "fee_amount", "net_amount", "currency", "status", "settled_at", "bank_ref", "created_at") VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10) ON CONFLICT DO NOTHING`,
        [rand(1, 5), `seed-${uuid().slice(0,8)}`, (rand(100, 99999) / 100).toFixed(2), (rand(100, 99999) / 100).toFixed(2), (rand(100, 99999) / 100).toFixed(2), "NGN", pick(STATUSES), daysAgo(rand(0, 90)), uuid(), daysAgo(rand(0, 90))]
      );
    }
    total += 10;
    console.log("  ✅ merchant_settlements: 10 rows");

    // ── mqtt_bridge_config (10 rows) ──
    for (let i = 0; i < 10; i++) {
      await client.query(
        `INSERT INTO "mqtt_bridge_config" ("name", "broker_url", "port", "use_tls", "username", "password", "client_id", "keep_alive_seconds", "reconnect_delay_ms", "enabled", "last_test_at", "last_test_status", "last_test_error", "created_at", "updated_at") VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15) ON CONFLICT DO NOTHING`,
        [pick(NAMES), `https://api.54link.ng/${uuid()}`, rand(1, 100), Math.random() > 0.5, pick(NAMES), `seed-${uuid().slice(0,8)}`, `seed-${uuid().slice(0,8)}`, rand(1, 100), rand(1, 100), Math.random() > 0.5, daysAgo(rand(0, 90)), pick(STATUSES), `seed-${uuid().slice(0,8)}`, daysAgo(rand(0, 90)), daysAgo(rand(0, 90))]
      );
    }
    total += 10;
    console.log("  ✅ mqtt_bridge_config: 10 rows");

    // ── multi_sim_profiles (10 rows) ──
    for (let i = 0; i < 10; i++) {
      await client.query(
        `INSERT INTO "multi_sim_profiles" ("terminal_id", "sim_slot", "carrier", "iccid", "phone_number", "signal_strength", "data_usage_mb", "failover_priority", "last_checked_at", "created_at", "updated_at") VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11) ON CONFLICT DO NOTHING`,
        [rand(1, 100), rand(1, 100), `seed-${uuid().slice(0,8)}`, `seed-${uuid().slice(0,8)}`, `0801234${rand(1000, 9999)}`, rand(1, 100), (rand(100, 99999) / 100).toFixed(2), rand(1, 100), daysAgo(rand(0, 90)), daysAgo(rand(0, 90)), daysAgo(rand(0, 90))]
      );
    }
    total += 10;
    console.log("  ✅ multi_sim_profiles: 10 rows");

    // ── ota_update_log (10 rows) ──
    for (let i = 0; i < 10; i++) {
      await client.query(
        `INSERT INTO "ota_update_log" ("device_id", "release_id", "from_version", "to_version", "status", "started_at", "completed_at", "error_message", "created_at") VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) ON CONFLICT DO NOTHING`,
        [rand(1, 20), rand(1, 100), `seed-${uuid().slice(0,8)}`, `seed-${uuid().slice(0,8)}`, pick(STATUSES), daysAgo(rand(0, 90)), daysAgo(rand(0, 90)), `Seed data - ${uuid().slice(0,8)}`, daysAgo(rand(0, 90))]
      );
    }
    total += 10;
    console.log("  ✅ ota_update_log: 10 rows");

    // ── otp_tokens (10 rows) ──
    for (let i = 0; i < 10; i++) {
      await client.query(
        `INSERT INTO "otp_tokens" ("agent_id", "hashed_otp", "purpose", "expires_at", "used", "used_at", "created_at") VALUES ($1, $2, $3, $4, $5, $6, $7) ON CONFLICT DO NOTHING`,
        [rand(1, 10), `seed-${uuid().slice(0,8)}`, `seed-${uuid().slice(0,8)}`, daysAgo(rand(0, 90)), Math.random() > 0.5, daysAgo(rand(0, 90)), daysAgo(rand(0, 90))]
      );
    }
    total += 10;
    console.log("  ✅ otp_tokens: 10 rows");

    // ── qr_codes (10 rows) ──
    for (let i = 0; i < 10; i++) {
      await client.query(
        `INSERT INTO "qr_codes" ("code", "agent_id", "amount", "currency", "description", "expires_at", "used_at", "used_by_customer_id", "created_at") VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) ON CONFLICT DO NOTHING`,
        [uuid(), rand(1, 10), (rand(100, 99999) / 100).toFixed(2), "NGN", `Seed data - ${uuid().slice(0,8)}`, daysAgo(rand(0, 90)), daysAgo(rand(0, 90)), rand(1, 100), daysAgo(rand(0, 90))]
      );
    }
    total += 10;
    console.log("  ✅ qr_codes: 10 rows");

    // ── rate_alerts (10 rows) ──
    for (let i = 0; i < 10; i++) {
      await client.query(
        `INSERT INTO "rate_alerts" ("agent_id", "base_currency", "target_currency", "target_rate", "current_rate", "triggered_at", "expires_at", "note", "created_at", "updated_at") VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10) ON CONFLICT DO NOTHING`,
        [rand(1, 10), "NGN", "NGN", (rand(100, 99999) / 100).toFixed(2), (rand(100, 99999) / 100).toFixed(2), daysAgo(rand(0, 90)), daysAgo(rand(0, 90)), `seed-${uuid().slice(0,8)}`, daysAgo(rand(0, 90)), daysAgo(rand(0, 90))]
      );
    }
    total += 10;
    console.log("  ✅ rate_alerts: 10 rows");

    // ── refunds (10 rows) ──
    for (let i = 0; i < 10; i++) {
      await client.query(
        `INSERT INTO "refunds" ("ref", "dispute_id", "transaction_id", "transaction_ref", "agent_id", "customer_id", "customer_name", "customer_phone", "original_amount", "refund_amount", "currency", "reason", "category", "status", "method", "approved_by", "approved_at", "processed_at", "rejected_by", "rejected_at", "rejection_reason", "notes", "metadata", "tenant_id", "deleted_at", "created_at", "updated_at") VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24, $25, $26, $27) ON CONFLICT DO NOTHING`,
        [uuid(), rand(1, 100), rand(1, 100), uuid(), rand(1, 10), rand(1, 100), pick(NAMES), `0801234${rand(1000, 9999)}`, rand(100, 50000), rand(100, 50000), "NGN", `Seed data - ${uuid().slice(0,8)}`, pick(["standard","premium","basic","custom"]), pick(STATUSES), pick(["standard","premium","basic","custom"]), `seed-${uuid().slice(0,8)}`, daysAgo(rand(0, 90)), daysAgo(rand(0, 90)), `seed-${uuid().slice(0,8)}`, daysAgo(rand(0, 90)), `Seed data - ${uuid().slice(0,8)}`, `Seed data - ${uuid().slice(0,8)}`, `seed-${uuid().slice(0,8)}`, rand(1, 3), daysAgo(rand(0, 90)), daysAgo(rand(0, 90)), daysAgo(rand(0, 90))]
      );
    }
    total += 10;
    console.log("  ✅ refunds: 10 rows");

    // ── service_records (10 rows) ──
    for (let i = 0; i < 10; i++) {
      await client.query(
        `INSERT INTO "service_records" ("terminal_id", "technician_name", "issue_description", "resolution", "service_date", "next_service_date", "created_at") VALUES ($1, $2, $3, $4, $5, $6, $7) ON CONFLICT DO NOTHING`,
        [rand(1, 100), pick(NAMES), `Seed data - ${uuid().slice(0,8)}`, `seed-${uuid().slice(0,8)}`, daysAgo(rand(0, 90)), daysAgo(rand(0, 90)), daysAgo(rand(0, 90))]
      );
    }
    total += 10;
    console.log("  ✅ service_records: 10 rows");

    // ── shareable_links (10 rows) ──
    for (let i = 0; i < 10; i++) {
      await client.query(
        `INSERT INTO "shareable_links" ("slug", "agent_id", "amount", "currency", "description", "click_count", "conversion_count", "expires_at", "created_at", "updated_at") VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10) ON CONFLICT DO NOTHING`,
        [`seed-${uuid().slice(0,8)}`, rand(1, 10), (rand(100, 99999) / 100).toFixed(2), "NGN", `Seed data - ${uuid().slice(0,8)}`, rand(0, 10), rand(0, 10), daysAgo(rand(0, 90)), daysAgo(rand(0, 90)), daysAgo(rand(0, 90))]
      );
    }
    total += 10;
    console.log("  ✅ shareable_links: 10 rows");

    // ── sim_failover_log (10 rows) ──
    for (let i = 0; i < 10; i++) {
      await client.query(
        `INSERT INTO "sim_failover_log" ("terminal_id", "agent_code", "from_slot", "to_slot", "reason", "latency_ms", "loss_x10", "tx_ref", "switched_at", "created_at") VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10) ON CONFLICT DO NOTHING`,
        [`seed-${uuid().slice(0,8)}`, uuid(), rand(1, 100), rand(1, 100), `Seed data - ${uuid().slice(0,8)}`, rand(1, 100), rand(1, 100), uuid(), daysAgo(rand(0, 90)), daysAgo(rand(0, 90))]
      );
    }
    total += 10;
    console.log("  ✅ sim_failover_log: 10 rows");

    // ── sim_orchestrator_config (10 rows) ──
    for (let i = 0; i < 10; i++) {
      await client.query(
        `INSERT INTO "sim_orchestrator_config" ("terminal_id", "probe_interval_ms", "relay_endpoint", "api_key", "enabled", "created_at", "updated_at") VALUES ($1, $2, $3, $4, $5, $6, $7) ON CONFLICT DO NOTHING`,
        [`seed-${uuid().slice(0,8)}`, rand(1, 100), `https://api.54link.ng/${uuid()}`, uuid(), Math.random() > 0.5, daysAgo(rand(0, 90)), daysAgo(rand(0, 90))]
      );
    }
    total += 10;
    console.log("  ✅ sim_orchestrator_config: 10 rows");

    // ── sim_probe_log (10 rows) ──
    for (let i = 0; i < 10; i++) {
      await client.query(
        `INSERT INTO "sim_probe_log" ("agent_code", "terminal_id", "slot", "carrier", "mcc_mnc", "rssi", "reg_status", "latency_ms", "packet_loss_x10", "score", "selected", "lat_e6", "lon_e6", "fw_version", "probed_at", "created_at") VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16) ON CONFLICT DO NOTHING`,
        [uuid(), `seed-${uuid().slice(0,8)}`, `seed-${uuid().slice(0,8)}`, `seed-${uuid().slice(0,8)}`, rand(1, 100), rand(1, 100), rand(1, 100), rand(1, 100), rand(1, 100), rand(1, 100), Math.random() > 0.5, rand(1, 100), rand(1, 100), `seed-${uuid().slice(0,8)}`, daysAgo(rand(0, 90)), daysAgo(rand(0, 90))]
      );
    }
    total += 10;
    console.log("  ✅ sim_probe_log: 10 rows");

    // ── software_updates (10 rows) ──
    for (let i = 0; i < 10; i++) {
      await client.query(
        `INSERT INTO "software_updates" ("version", "release_notes", "download_url", "checksum", "is_forced", "applied_count", "created_at") VALUES ($1, $2, $3, $4, $5, $6, $7) ON CONFLICT DO NOTHING`,
        [`seed-${uuid().slice(0,8)}`, `Seed data - ${uuid().slice(0,8)}`, `https://api.54link.ng/${uuid()}`, `seed-${uuid().slice(0,8)}`, Math.random() > 0.5, rand(0, 10), daysAgo(rand(0, 90))]
      );
    }
    total += 10;
    console.log("  ✅ software_updates: 10 rows");

    // ── storefront_ads (10 rows) ──
    for (let i = 0; i < 10; i++) {
      await client.query(
        `INSERT INTO "storefront_ads" ("title", "body", "image_url", "target_url", "agent_id", "impressions", "clicks", "budget", "spent", "starts_at", "ends_at", "created_at", "updated_at") VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13) ON CONFLICT DO NOTHING`,
        [`seed-${uuid().slice(0,8)}`, `seed-${uuid().slice(0,8)}`, `https://api.54link.ng/${uuid()}`, `https://api.54link.ng/${uuid()}`, rand(1, 10), rand(1, 100), rand(1, 100), (rand(100, 99999) / 100).toFixed(2), (rand(100, 99999) / 100).toFixed(2), daysAgo(rand(0, 90)), daysAgo(rand(0, 90)), daysAgo(rand(0, 90)), daysAgo(rand(0, 90))]
      );
    }
    total += 10;
    console.log("  ✅ storefront_ads: 10 rows");

    // ── system_config (10 rows) ──
    for (let i = 0; i < 10; i++) {
      await client.query(
        `INSERT INTO "system_config" ("key", "value", "description", "updated_by", "created_at", "updated_at") VALUES ($1, $2, $3, $4, $5, $6) ON CONFLICT DO NOTHING`,
        [uuid(), `seed-${uuid().slice(0,8)}`, `Seed data - ${uuid().slice(0,8)}`, `seed-${uuid().slice(0,8)}`, daysAgo(rand(0, 90)), daysAgo(rand(0, 90))]
      );
    }
    total += 10;
    console.log("  ✅ system_config: 10 rows");

    // ── tenant_branding (10 rows) ──
    for (let i = 0; i < 10; i++) {
      await client.query(
        `INSERT INTO "tenant_branding" ("tenant_id", "logo_url", "favicon_url", "primary_color", "secondary_color", "accent_color", "background_color", "text_color", "font_family", "brand_name", "tagline", "custom_domain", "support_email", "support_phone", "terms_url", "privacy_url", "custom_css", "is_live", "created_at", "updated_at") VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20) ON CONFLICT DO NOTHING`,
        [rand(1, 3), `https://api.54link.ng/${uuid()}`, `https://api.54link.ng/${uuid()}`, `seed-${uuid().slice(0,8)}`, `seed-${uuid().slice(0,8)}`, `seed-${uuid().slice(0,8)}`, `seed-${uuid().slice(0,8)}`, `seed-${uuid().slice(0,8)}`, `seed-${uuid().slice(0,8)}`, pick(NAMES), `seed-${uuid().slice(0,8)}`, `seed-${uuid().slice(0,8)}`, `agent${rand(1,10)}@54link.ng`, `0801234${rand(1000, 9999)}`, `https://api.54link.ng/${uuid()}`, `https://api.54link.ng/${uuid()}`, `seed-${uuid().slice(0,8)}`, Math.random() > 0.5, daysAgo(rand(0, 90)), daysAgo(rand(0, 90))]
      );
    }
    total += 10;
    console.log("  ✅ tenant_branding: 10 rows");

    // ── tenant_corridors (10 rows) ──
    for (let i = 0; i < 10; i++) {
      await client.query(
        `INSERT INTO "tenant_corridors" ("tenant_id", "source_country", "source_currency", "destination_country", "destination_currency", "min_amount", "max_amount", "daily_limit", "estimated_delivery_minutes", "created_at", "updated_at") VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11) ON CONFLICT DO NOTHING`,
        [rand(1, 3), `seed-${uuid().slice(0,8)}`, "NGN", `seed-${uuid().slice(0,8)}`, "NGN", (rand(100, 99999) / 100).toFixed(2), (rand(100, 99999) / 100).toFixed(2), (rand(100, 99999) / 100).toFixed(2), rand(1, 100), daysAgo(rand(0, 90)), daysAgo(rand(0, 90))]
      );
    }
    total += 10;
    console.log("  ✅ tenant_corridors: 10 rows");

    // ── tenant_fee_overrides (10 rows) ──
    for (let i = 0; i < 10; i++) {
      await client.query(
        `INSERT INTO "tenant_fee_overrides" ("tenant_id", "corridor_id", "tx_type", "fee_value", "min_fee", "max_fee", "description", "is_active", "created_at", "updated_at") VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10) ON CONFLICT DO NOTHING`,
        [rand(1, 3), rand(1, 100), pick(["standard","premium","basic","custom"]), (rand(100, 99999) / 100).toFixed(2), (rand(100, 99999) / 100).toFixed(2), (rand(100, 99999) / 100).toFixed(2), `Seed data - ${uuid().slice(0,8)}`, Math.random() > 0.5, daysAgo(rand(0, 90)), daysAgo(rand(0, 90))]
      );
    }
    total += 10;
    console.log("  ✅ tenant_fee_overrides: 10 rows");

    // ── tenant_users (10 rows) ──
    for (let i = 0; i < 10; i++) {
      await client.query(
        `INSERT INTO "tenant_users" ("tenant_id", "user_id", "email", "name", "is_active", "invited_by", "invited_at", "accepted_at", "last_active_at", "created_at", "updated_at") VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11) ON CONFLICT DO NOTHING`,
        [rand(1, 3), rand(1, 10), `agent${rand(1,10)}@54link.ng`, pick(NAMES), Math.random() > 0.5, rand(1, 100), daysAgo(rand(0, 90)), daysAgo(rand(0, 90)), daysAgo(rand(0, 90)), daysAgo(rand(0, 90)), daysAgo(rand(0, 90))]
      );
    }
    total += 10;
    console.log("  ✅ tenant_users: 10 rows");

    // ── webhook_secrets (10 rows) ──
    for (let i = 0; i < 10; i++) {
      await client.query(
        `INSERT INTO "webhook_secrets" ("integration_name", "secret", "algorithm", "is_active", "last_rotated_at", "created_at") VALUES ($1, $2, $3, $4, $5, $6) ON CONFLICT DO NOTHING`,
        [pick(NAMES), uuid(), `seed-${uuid().slice(0,8)}`, Math.random() > 0.5, daysAgo(rand(0, 90)), daysAgo(rand(0, 90))]
      );
    }
    total += 10;
    console.log("  ✅ webhook_secrets: 10 rows");

    await client.query("COMMIT");
    console.log(`\n✅ Total: ${total} seed records inserted across 43 tables`);
  } catch (err) {
    await client.query("ROLLBACK");
    console.error("❌ Seed failed:", err.message);
    throw err;
  } finally {
    client.release();
    await pool.end();
  }
}

seed().catch(console.error);
