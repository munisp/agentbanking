/**
 * Database Index Optimization — EXPLAIN ANALYZE guided indexes
 *
 * Run: npx tsx server/lib/dbIndexes.ts
 * to apply recommended indexes to PostgreSQL.
 */

export const RECOMMENDED_INDEXES = [
  // High-traffic query indexes
  {
    table: "transactions",
    columns: ["agent_id", "created_at"],
    name: "idx_tx_agent_created",
  },
  {
    table: "transactions",
    columns: ["status", "created_at"],
    name: "idx_tx_status_created",
  },
  {
    table: "transactions",
    columns: ["type", "agent_id"],
    name: "idx_tx_type_agent",
  },
  {
    table: "transactions",
    columns: ["recipient_id", "created_at"],
    name: "idx_tx_recipient_created",
  },

  // Agent lookups
  {
    table: "agents",
    columns: ["agent_code"],
    name: "idx_agents_code",
    unique: true,
  },
  { table: "agents", columns: ["phone"], name: "idx_agents_phone" },
  {
    table: "agents",
    columns: ["is_active", "created_at"],
    name: "idx_agents_active_created",
  },
  {
    table: "agents",
    columns: ["super_agent_id", "is_active"],
    name: "idx_agents_super_active",
  },

  // Audit log queries
  {
    table: "audit_logs",
    columns: ["agent_id", "created_at"],
    name: "idx_audit_agent_created",
  },
  {
    table: "audit_logs",
    columns: ["action", "created_at"],
    name: "idx_audit_action_created",
  },
  {
    table: "audit_logs",
    columns: ["resource", "resource_id"],
    name: "idx_audit_resource",
  },

  // KYC lookups
  {
    table: "kyc_documents",
    columns: ["agent_id", "status"],
    name: "idx_kyc_agent_status",
  },
  {
    table: "kyc_documents",
    columns: ["document_type", "status"],
    name: "idx_kyc_type_status",
  },

  // Settlement queries
  {
    table: "settlement_batches",
    columns: ["agent_id", "status"],
    name: "idx_settlement_agent_status",
  },
  {
    table: "settlement_batches",
    columns: ["status", "cutoff_time"],
    name: "idx_settlement_status_cutoff",
  },

  // Commission queries
  {
    table: "commissions",
    columns: ["agent_id", "created_at"],
    name: "idx_commission_agent_created",
  },
  {
    table: "commissions",
    columns: ["status", "payout_date"],
    name: "idx_commission_status_payout",
  },

  // POS terminal queries
  {
    table: "pos_terminals",
    columns: ["agent_id", "status"],
    name: "idx_pos_agent_status",
  },
  {
    table: "pos_terminals",
    columns: ["serial_number"],
    name: "idx_pos_serial",
    unique: true,
  },
];

export function generateCreateIndexSQL(): string[] {
  return RECOMMENDED_INDEXES.map(idx => {
    const unique = idx.unique ? "UNIQUE " : "";
    const cols = (idx.columns as string[]).join(", ");
    return `CREATE ${unique}INDEX IF NOT EXISTS ${idx.name} ON ${idx.table} (${cols});`;
  });
}

export function generateDropIndexSQL(): string[] {
  return RECOMMENDED_INDEXES.map(idx => `DROP INDEX IF EXISTS ${idx.name};`);
}
