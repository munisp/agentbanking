// Sprint 81: Seed data for billing RBAC, audit, config, and provisioning tables
import pg from "pg";
const { Pool } = pg;

const pool = new Pool({ connectionString: process.env.POSTGRES_URL || "postgresql://posadmin:pos54link123@localhost:5432/pos54link" });

async function seed() {
  const client = await pool.connect();
  try {
    await client.query("BEGIN");

    // Seed billing_role_assignments
    const roleAssignments = [
      { userId: 1, tenantId: 1, role: "platform_admin", assignedBy: 1, isActive: true },
      { userId: 2, tenantId: 1, role: "billing_admin", assignedBy: 1, isActive: true },
      { userId: 3, tenantId: 1, role: "billing_analyst", assignedBy: 1, isActive: true },
      { userId: 4, tenantId: 1, role: "billing_viewer", assignedBy: 1, isActive: true },
      { userId: 5, tenantId: 2, role: "billing_admin", assignedBy: 1, isActive: true },
      { userId: 6, tenantId: 2, role: "billing_viewer", assignedBy: 5, isActive: true },
      { userId: 7, tenantId: 3, role: "billing_admin", assignedBy: 1, isActive: true },
    ];
    for (const ra of roleAssignments) {
      await client.query(
        `INSERT INTO billing_role_assignments (user_id, tenant_id, role, assigned_by, is_active, created_at) VALUES ($1, $2, $3, $4, $5, NOW()) ON CONFLICT DO NOTHING`,
        [ra.userId, ra.tenantId, ra.role, ra.assignedBy, ra.isActive]
      );
    }
    console.log(`✓ Seeded ${roleAssignments.length} billing role assignments`);

    // Seed billing_audit_log
    const auditEntries = [
      { tenantId: 1, userId: 1, action: "billing_config_created", resource: "tenant_billing_config", resourceId: "1", details: '{"billingModel":"revenue_share"}' },
      { tenantId: 1, userId: 2, action: "split_recorded", resource: "platform_billing_ledger", resourceId: "txn_001", details: '{"grossFee":5000,"platformShare":1500}' },
      { tenantId: 1, userId: 2, action: "reconciliation_run", resource: "reconciliation_batch", resourceId: "RB-001", details: '{"matched":95,"discrepancies":2}' },
      { tenantId: 2, userId: 5, action: "billing_config_updated", resource: "tenant_billing_config", resourceId: "2", details: '{"billingModel":"subscription","perAgentFee":15000}' },
      { tenantId: 1, userId: 1, action: "role_assigned", resource: "billing_role_assignments", resourceId: "3", details: '{"role":"billing_analyst","userId":3}' },
    ];
    for (const ae of auditEntries) {
      await client.query(
        `INSERT INTO billing_audit_log (tenant_id, user_id, action, resource, resource_id, details, created_at) VALUES ($1, $2, $3, $4, $5, $6, NOW()) ON CONFLICT DO NOTHING`,
        [ae.tenantId, ae.userId, ae.action, ae.resource, ae.resourceId, ae.details]
      );
    }
    console.log(`✓ Seeded ${auditEntries.length} billing audit log entries`);

    // Seed tenant_billing_config
    const billingConfigs = [
      { tenantId: 1, billingModel: "revenue_share", isActive: true, revenueShareConfig: '{"startSplitPct":70,"scaleSplitPct":80,"scaleThreshold":100000,"minimumMonthlyGuarantee":500000,"signOnFee":2000000}', subscriptionConfig: null, hybridConfig: null, contractStartDate: "2025-01-01", contractEndDate: "2027-01-01", autoRenew: true },
      { tenantId: 2, billingModel: "subscription", isActive: true, revenueShareConfig: null, subscriptionConfig: '{"perAgentFee":15000,"perPosFee":5000,"implementationFee":5000000,"billingCycle":"monthly"}', hybridConfig: null, contractStartDate: "2025-03-01", contractEndDate: "2026-03-01", autoRenew: true },
      { tenantId: 3, billingModel: "hybrid", isActive: true, revenueShareConfig: null, subscriptionConfig: null, hybridConfig: '{"baseMonthlyFee":200000,"revenueSharePct":15,"minimumMonthlyRevenue":350000}', contractStartDate: "2025-06-01", contractEndDate: "2027-06-01", autoRenew: false },
    ];
    for (const bc of billingConfigs) {
      await client.query(
        `INSERT INTO tenant_billing_config (tenant_id, billing_model, is_active, revenue_share_config, subscription_config, hybrid_config, contract_start_date, contract_end_date, auto_renew, created_at, updated_at) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW(), NOW()) ON CONFLICT DO NOTHING`,
        [bc.tenantId, bc.billingModel, bc.isActive, bc.revenueShareConfig, bc.subscriptionConfig, bc.hybridConfig, bc.contractStartDate, bc.contractEndDate, bc.autoRenew]
      );
    }
    console.log(`✓ Seeded ${billingConfigs.length} tenant billing configs`);

    // Seed billing_provisioning_history
    const provisioningHistory = [
      { tenantId: 1, step: "create_billing_config", status: "completed", details: '{"billingModel":"revenue_share"}' },
      { tenantId: 1, step: "provision_tigerbeetle_accounts", status: "completed", details: '{"accounts":["acc_platform_1","acc_client_1"]}' },
      { tenantId: 1, step: "create_kafka_topics", status: "completed", details: '{"topics":["billing.tenant.1.splits","billing.tenant.1.reconciliation"]}' },
      { tenantId: 1, step: "configure_apisix_rate_limits", status: "completed", details: '{"rateLimit":1000}' },
      { tenantId: 1, step: "setup_permify_policies", status: "completed", details: '{"policies":["billing_admin","billing_viewer"]}' },
      { tenantId: 1, step: "register_mojaloop_settlement", status: "completed", details: '{"participantId":"54link_tenant_1"}' },
      { tenantId: 2, step: "create_billing_config", status: "completed", details: '{"billingModel":"subscription"}' },
      { tenantId: 2, step: "provision_tigerbeetle_accounts", status: "completed", details: '{"accounts":["acc_platform_2","acc_client_2"]}' },
      { tenantId: 2, step: "create_kafka_topics", status: "completed", details: '{"topics":["billing.tenant.2.splits"]}' },
      { tenantId: 2, step: "configure_apisix_rate_limits", status: "completed", details: '{"rateLimit":500}' },
      { tenantId: 2, step: "setup_permify_policies", status: "completed", details: '{"policies":["billing_admin"]}' },
      { tenantId: 2, step: "register_mojaloop_settlement", status: "completed", details: '{"participantId":"54link_tenant_2"}' },
    ];
    for (const ph of provisioningHistory) {
      await client.query(
        `INSERT INTO billing_provisioning_history (tenant_id, step, status, details, created_at) VALUES ($1, $2, $3, $4, NOW()) ON CONFLICT DO NOTHING`,
        [ph.tenantId, ph.step, ph.status, ph.details]
      );
    }
    console.log(`✓ Seeded ${provisioningHistory.length} billing provisioning history entries`);

    // Seed platform_billing_ledger with sample transactions
    const ledgerEntries = [];
    const txTypes = ["pos_purchase", "transfer", "bill_payment", "airtime", "withdrawal"];
    const channels = ["pos", "mobile", "ussd", "web", "agent"];
    for (let i = 0; i < 50; i++) {
      const grossFee = Math.floor(Math.random() * 10000) + 500;
      const platformShare = Math.floor(grossFee * 0.3);
      const clientShare = Math.floor(grossFee * 0.5);
      const switchFee = Math.floor(grossFee * 0.05);
      const agentCommission = grossFee - platformShare - clientShare - switchFee;
      ledgerEntries.push({
        tenantId: Math.ceil(Math.random() * 3),
        clientId: `client_${Math.ceil(Math.random() * 5)}`,
        transactionId: `txn_${Date.now()}_${i}`,
        transactionType: txTypes[Math.floor(Math.random() * txTypes.length)],
        channel: channels[Math.floor(Math.random() * channels.length)],
        grossFee, platformShare, clientShare, switchFee, agentCommission,
        currency: "NGN",
        status: "settled",
      });
    }
    for (const le of ledgerEntries) {
      await client.query(
        `INSERT INTO platform_billing_ledger (tenant_id, client_id, transaction_id, transaction_type, channel, gross_fee, platform_share, client_share, switch_fee, agent_commission, currency, status, created_at) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, NOW()) ON CONFLICT DO NOTHING`,
        [le.tenantId, le.clientId, le.transactionId, le.transactionType, le.channel, le.grossFee, le.platformShare, le.clientShare, le.switchFee, le.agentCommission, le.currency, le.status]
      );
    }
    console.log(`✓ Seeded ${ledgerEntries.length} billing ledger entries`);

    await client.query("COMMIT");
    console.log("\n✅ Sprint 81 billing seed data complete!");
  } catch (err) {
    await client.query("ROLLBACK");
    console.error("Seed failed:", err.message);
  } finally {
    client.release();
    await pool.end();
  }
}

seed();
