/**
 * Sprint 53 Seed Script — Commission Engine + Dispute Portal + Analytics
 * Seeds: commission_tiers, commission_splits, commission_payouts,
 *        commission_audit_trail, disputes, dispute_messages, dispute_evidence
 */
import pg from "pg";
const { Pool } = pg;

const pool = new Pool({
  connectionString: process.env.POSTGRES_URL || process.env.DATABASE_URL,
  ssl: false,
});

async function safeInsert(sql, params = []) {
  try {
    await pool.query(sql, params);
  } catch (e) {
    if (e.code === "23505") return; // duplicate key
    console.warn(`[WARN] ${e.message.slice(0, 100)}`);
  }
}

async function seed() {
  console.log("🌱 Sprint 53 Seed — Starting...");

  // ── Commission Tiers (9-tier structure) ─────────────────────────────────
  console.log("  → Seeding commission_tiers...");
  const tiers = [
    ["CT-001", "Cash-In Basic", "cash_in", 0, 100000, 0.5, 0, 0, "agent"],
    ["CT-002", "Cash-In Silver", "cash_in", 100001, 500000, 0.6, 0, 0.05, "agent"],
    ["CT-003", "Cash-In Gold", "cash_in", 500001, 2000000, 0.75, 0, 0.1, "agent"],
    ["CT-004", "Cash-In Platinum", "cash_in", 2000001, 999999999, 0.9, 0, 0.15, "agent"],
    ["CT-005", "Cash-Out Basic", "cash_out", 0, 100000, 0.8, 50, 0, "agent"],
    ["CT-006", "Cash-Out Premium", "cash_out", 100001, 999999999, 1.0, 50, 0.1, "agent"],
    ["CT-007", "Transfer Basic", "transfer", 0, 500000, 0.3, 25, 0, "agent"],
    ["CT-008", "Bill Payment", "bill_payment", 0, 999999999, 0.2, 50, 0.05, "agent"],
    ["CT-009", "Airtime", "airtime", 0, 999999999, 3.0, 0, 0, "agent"],
  ];
  for (const [tierId, name, txType, minV, maxV, rate, flat, bonus, role] of tiers) {
    await safeInsert(
      `INSERT INTO commission_tiers (tier_id, name, transaction_type, min_volume, max_volume, rate, flat_fee, bonus_rate, agent_role, is_active)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, true) ON CONFLICT (tier_id) DO NOTHING`,
      [tierId, name, txType, minV, maxV, rate, flat, bonus, role]
    );
  }

  // ── Commission Splits ───────────────────────────────────────────────────
  console.log("  → Seeding commission_splits...");
  const splits = [
    ["CS-001", "cash_in", 10, 15, 60, 10, 5],
    ["CS-002", "cash_out", 10, 15, 60, 10, 5],
    ["CS-003", "transfer", 8, 12, 65, 10, 5],
    ["CS-004", "bill_payment", 10, 15, 55, 15, 5],
    ["CS-005", "airtime", 5, 10, 70, 10, 5],
  ];
  for (const [splitId, txType, sa, ma, ag, sub, plat] of splits) {
    await safeInsert(
      `INSERT INTO commission_splits (split_id, transaction_type, super_agent_share, master_agent_share, agent_share, sub_agent_share, platform_share, is_active)
       VALUES ($1, $2, $3, $4, $5, $6, $7, true) ON CONFLICT (split_id) DO NOTHING`,
      [splitId, txType, sa, ma, ag, sub, plat]
    );
  }

  // ── Commission Payouts (30 sample payouts) ──────────────────────────────
  console.log("  → Seeding commission_payouts...");
  const agentNames = ["Adebayo Ogundimu", "Chinwe Okonkwo", "Ibrahim Musa", "Ngozi Okafor", "Aliyu Bello",
    "Funke Adeyemi", "Emeka Nwosu", "Aisha Abdullahi", "Olumide Bakare", "Halima Yusuf"];
  const statuses = ["pending", "approved", "completed", "completed"];
  for (let i = 1; i <= 30; i++) {
    const agentIdx = (i % 10) + 1;
    const agentId = agentIdx + 10; // agents start at ID 11
    const agentCode = `AGT${String(agentIdx).padStart(3, "0")}`;
    const amount = Math.floor(Math.random() * 50000) + 5000;
    const status = statuses[i % 4];
    await safeInsert(
      `INSERT INTO commission_payouts (agent_id, agent_code, amount, status, bank_code, account_number, account_name, requested_by, created_at)
       VALUES ($1, $2, $3, $4, $5, $6, $7, 1, NOW() - interval '${i} days')`,
      [agentId, agentCode, amount, status, "058", `20${String(agentId).padStart(8, "0")}`, agentNames[agentId - 1]]
    );
  }

  // ── Commission Audit Trail ──────────────────────────────────────────────
  console.log("  → Seeding commission_audit_trail...");
  const auditActions = [
    ["tier", "CT-001", "created", "System", null, '{"name":"Cash-In Basic","rate":0.5}'],
    ["tier", "CT-002", "updated", "Admin", '{"rate":0.55}', '{"rate":0.6}'],
    ["split", "CS-001", "created", "System", null, '{"agentShare":60}'],
    ["split", "CS-003", "updated", "Admin", '{"agentShare":60}', '{"agentShare":65}'],
    ["payout", "CP-0001", "approved", "Supervisor", '{"status":"pending"}', '{"status":"approved"}'],
    ["payout", "CP-0005", "approved", "Supervisor", '{"status":"pending"}', '{"status":"approved"}'],
    ["tier", "CT-005", "updated", "Admin", '{"rate":0.75}', '{"rate":0.8}'],
  ];
  for (const [entityType, entityId, action, performedBy, prev, next] of auditActions) {
    await safeInsert(
      `INSERT INTO commission_audit_trail (entity_type, entity_id, action, performed_by, previous_value, new_value, created_at)
       VALUES ($1, $2, $3, $4, $5::json, $6::json, NOW() - interval '${Math.floor(Math.random() * 30)} days')`,
      [entityType, entityId, action, performedBy, prev, next]
    );
  }

  // ── Disputes (20 sample disputes for CustomerDisputePortal) ─────────────
  console.log("  → Seeding disputes...");
  const customerNames = ["Adebayo Ogundimu", "Chioma Nwankwo", "Emeka Obi", "Fatima Bello", "Ibrahim Yusuf", "Kemi Adeyemi", "Ngozi Eze", "Olumide Bakare", "Sade Afolabi", "Tunde Okafor"];
  const disputeReasons = ["unauthorized", "duplicate_charge", "service_not_received", "wrong_amount", "fraud"];
  const disputeStatuses = ["open", "investigating", "resolved", "escalated", "closed"];
  const priorities = ["low", "medium", "high", "critical"];
  for (let i = 1; i <= 20; i++) {
    const amount = Math.floor(Math.random() * 100000) + 1000;
    const status = disputeStatuses[i % 5];
    const priority = priorities[i % 4];
    const reason = disputeReasons[i % 5];
    const ref = `DSP-${String(i).padStart(6, '0')}`;
    await safeInsert(
      `INSERT INTO disputes (ref, "transactionRef", "agentId", reason, description, status, priority, "assignedTo", amount, "createdBy", "slaDeadlineAt", "createdAt", "updatedAt")
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, NOW() + interval '48 hours', NOW() - interval '${i * 2} days', NOW() - interval '${i} days')`,
      [
        ref,
        `TXN-${String(Date.now() - i * 86400000).slice(-8)}`,
        (i % 10) + 1,
        reason,
        `Customer reported ${reason.replace(/_/g, " ")} for transaction of ₦${amount.toLocaleString()}`,
        status,
        priority,
        `AGT${String((i % 5) + 1).padStart(3, "0")}`,
        String(amount),
        customerNames[i % customerNames.length],
      ]
    );
  }

  // ── Dispute Messages (activity log) ─────────────────────────────────────
  console.log("  → Seeding dispute_messages...");
  for (let i = 1; i <= 20; i++) {
    const messages = [
      `Dispute filed by customer. Transaction reference verified.`,
      `Investigation started. Contacting merchant for transaction details.`,
      `Evidence reviewed. ${i % 2 === 0 ? "Refund approved." : "Escalated to supervisor."}`,
    ];
    for (let j = 0; j < messages.length; j++) {
      await safeInsert(
        `INSERT INTO dispute_messages ("disputeId", "senderType", "senderName", message, "createdAt")
         VALUES ($1, $2, $3, $4, NOW() - interval '${(20 - i) * 2 + j} days')`,
        [i, j === 0 ? "customer" : "agent", j === 0 ? agentNames[i % 10] : `Agent ${(i % 5) + 1}`, messages[j]]
      );
    }
  }

  // ── Dispute Evidence ────────────────────────────────────────────────────
  console.log("  → Seeding dispute_evidence...");
  for (let i = 1; i <= 10; i++) {
    await safeInsert(
      `INSERT INTO dispute_evidence (dispute_id, file_name, file_url, file_key, mime_type, file_size, uploaded_by, created_at)
       VALUES ($1, $2, $3, $4, $5, $6, $7, NOW() - interval '${i} days')`,
      [
        i,
        `receipt_${i}.pdf`,
        `https://storage.54link.com/disputes/${i}/receipt_${i}.pdf`,
        `disputes/${i}/receipt_${i}.pdf`,
        "application/pdf",
        Math.floor(Math.random() * 500000) + 10000,
        agentNames[i % 10],
      ]
    );
  }

  console.log("✅ Sprint 53 Seed — Complete!");
  await pool.end();
}

seed().catch((e) => {
  console.error("❌ Seed failed:", e.message);
  process.exit(1);
});
