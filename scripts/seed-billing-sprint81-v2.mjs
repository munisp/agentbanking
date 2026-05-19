import pg from "pg";
const { Pool } = pg;
const pool = new Pool({ connectionString: "postgresql://posadmin:pos54link123@localhost:5432/pos54link" });

async function seed() {
  const client = await pool.connect();
  try {
    await client.query("BEGIN");

    // billing_role_assignments: columns are billing_role, granted_by
    const roleAssignments = [
      [1, 1, "platform_admin", 1, true],
      [2, 1, "billing_admin", 1, true],
      [3, 1, "billing_analyst", 1, true],
      [4, 1, "billing_viewer", 1, true],
      [5, 2, "billing_admin", 1, true],
      [6, 2, "billing_viewer", 5, true],
      [7, 3, "billing_admin", 1, true],
    ];
    for (const [userId, tenantId, role, grantedBy, isActive] of roleAssignments) {
      await client.query(
        `INSERT INTO billing_role_assignments (user_id, tenant_id, billing_role, granted_by, is_active) VALUES ($1, $2, $3, $4, $5) ON CONFLICT DO NOTHING`,
        [userId, tenantId, role, grantedBy, isActive]
      );
    }
    console.log(`✓ Seeded ${roleAssignments.length} billing role assignments`);

    // billing_audit_log: columns are action(enum), resource_type, resource_id, metadata
    const auditActions = ["config_created", "config_updated", "split_recorded", "reconciliation_run", "permission_granted"];
    const auditEntries = [
      [1, 1, null, "config_created", "tenant_billing_config", "1", null, null, '{"billingModel":"revenue_share"}'],
      [1, 2, null, "split_recorded", "platform_billing_ledger", "txn_001", null, null, '{"grossFee":5000}'],
      [1, 2, null, "reconciliation_run", "reconciliation_batch", "RB-001", null, null, '{"matched":95}'],
      [2, 5, null, "config_updated", "tenant_billing_config", "2", null, null, '{"billingModel":"subscription"}'],
      [1, 1, null, "permission_granted", "billing_role_assignments", "3", null, null, '{"role":"billing_analyst"}'],
    ];
    for (const [tenantId, userId, userName, action, resourceType, resourceId, beforeState, afterState, metadata] of auditEntries) {
      await client.query(
        `INSERT INTO billing_audit_log (tenant_id, user_id, user_name, action, resource_type, resource_id, before_state, after_state, metadata) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) ON CONFLICT DO NOTHING`,
        [tenantId, userId, userName, action, resourceType, resourceId, beforeState, afterState, metadata]
      );
    }
    console.log(`✓ Seeded ${auditEntries.length} billing audit log entries`);

    // tenant_billing_config: columns are tenant_id, billing_model, revenue_share_config, subscription_config, hybrid_config, currency, effective_date, contract_end_date, auto_renew
    const configs = [
      [1, "revenue_share", '{"startSplitPct":70,"scaleSplitPct":80,"scaleThreshold":100000}', null, null, "NGN", true],
      [2, "subscription", null, '{"perAgentFee":15000,"perPosFee":5000}', null, "NGN", true],
      [3, "hybrid", null, null, '{"baseMonthlyFee":200000,"revenueSharePct":15}', "NGN", false],
    ];
    for (const [tenantId, billingModel, revConfig, subConfig, hybConfig, currency, autoRenew] of configs) {
      await client.query(
        `INSERT INTO tenant_billing_config (tenant_id, billing_model, revenue_share_config, subscription_config, hybrid_config, currency, auto_renew) VALUES ($1, $2, $3, $4, $5, $6, $7) ON CONFLICT DO NOTHING`,
        [tenantId, billingModel, revConfig, subConfig, hybConfig, currency, autoRenew]
      );
    }
    console.log(`✓ Seeded ${configs.length} tenant billing configs`);

    // billing_provisioning_history: columns are tenant_id, step, status, details, started_at
    const provSteps = [
      [1, "create_billing_config", "completed", '{"billingModel":"revenue_share"}'],
      [1, "provision_tigerbeetle_accounts", "completed", '{"accounts":["acc_platform_1","acc_client_1"]}'],
      [1, "create_kafka_topics", "completed", '{"topics":["billing.tenant.1.splits"]}'],
      [1, "configure_apisix_rate_limits", "completed", '{"rateLimit":1000}'],
      [1, "setup_permify_policies", "completed", '{"policies":["billing_admin","billing_viewer"]}'],
      [1, "register_mojaloop_settlement", "completed", '{"participantId":"54link_tenant_1"}'],
      [2, "create_billing_config", "completed", '{"billingModel":"subscription"}'],
      [2, "provision_tigerbeetle_accounts", "completed", '{"accounts":["acc_platform_2","acc_client_2"]}'],
      [2, "create_kafka_topics", "completed", '{"topics":["billing.tenant.2.splits"]}'],
      [2, "configure_apisix_rate_limits", "completed", '{"rateLimit":500}'],
    ];
    for (const [tenantId, step, status, details] of provSteps) {
      await client.query(
        `INSERT INTO billing_provisioning_history (tenant_id, step, status, details, completed_at) VALUES ($1, $2, $3, $4, NOW()) ON CONFLICT DO NOTHING`,
        [tenantId, step, status, details]
      );
    }
    console.log(`✓ Seeded ${provSteps.length} billing provisioning history entries`);

    // platform_billing_ledger: seed 50 sample transactions
    const txTypes = ["pos_purchase", "transfer", "bill_payment", "airtime", "withdrawal"];
    const channels = ["pos", "mobile", "ussd", "web", "agent"];
    let ledgerCount = 0;
    for (let i = 0; i < 50; i++) {
      const grossFee = Math.floor(Math.random() * 10000) + 500;
      const platformShare = Math.floor(grossFee * 0.3);
      const clientShare = Math.floor(grossFee * 0.5);
      const switchFee = Math.floor(grossFee * 0.05);
      const agentCommission = grossFee - platformShare - clientShare - switchFee;
      const tenantId = Math.ceil(Math.random() * 3);
      const clientId = `client_${Math.ceil(Math.random() * 5)}`;
      const txId = `txn_${Date.now()}_${i}`;
      const txType = txTypes[Math.floor(Math.random() * txTypes.length)];
      const channel = channels[Math.floor(Math.random() * channels.length)];
      await client.query(
        `INSERT INTO platform_billing_ledger (tenant_id, client_id, transaction_id, transaction_type, channel, gross_fee, platform_share, client_share, switch_fee, agent_commission, currency, status) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, 'NGN', 'settled') ON CONFLICT DO NOTHING`,
        [tenantId, clientId, txId, txType, channel, grossFee, platformShare, clientShare, switchFee, agentCommission]
      );
      ledgerCount++;
    }
    console.log(`✓ Seeded ${ledgerCount} billing ledger entries`);

    await client.query("COMMIT");
    console.log("\n✅ Sprint 81 billing seed data complete!");
  } catch (err) {
    await client.query("ROLLBACK");
    console.error("Seed failed:", err.message);
    console.error(err.stack);
  } finally {
    client.release();
    await pool.end();
  }
}
seed();
