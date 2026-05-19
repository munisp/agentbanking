import pg from "pg";
const { Pool } = pg;
const pool = new Pool({ connectionString: "postgresql://posadmin:pos54link123@localhost:5432/pos54link" });

async function seed() {
  const client = await pool.connect();
  try {
    await client.query("BEGIN");
    const txTypes = ["pos_purchase", "transfer", "bill_payment", "airtime", "withdrawal"];
    const regions = ["lagos", "abuja", "kano", "ph", "ibadan"];
    const carriers = ["mtn", "airtel", "glo", "9mobile"];
    const models = ["revenue_share", "subscription", "hybrid"];
    let count = 0;
    for (let i = 0; i < 50; i++) {
      const grossAmount = Math.floor(Math.random() * 50000) + 1000;
      const grossFee = Math.floor(grossAmount * 0.015);
      const agentCommission = Math.floor(grossFee * 0.15);
      const switchFee = Math.floor(grossFee * 0.05);
      const aggregatorFee = Math.floor(grossFee * 0.10);
      const platformNetFee = grossFee - agentCommission - switchFee - aggregatorFee;
      const revSharePct = 70;
      const clientRevenue = Math.floor(platformNetFee * (revSharePct / 100));
      const platformRevenue = platformNetFee - clientRevenue;
      // transaction_id, agent_id, pos_terminal_id are integers
      const txId = 100000 + i;
      const txRef = `REF${Math.random().toString(36).substring(2,10).toUpperCase()}`;
      const txType = txTypes[Math.floor(Math.random() * txTypes.length)];
      const region = regions[Math.floor(Math.random() * regions.length)];
      const carrier = carriers[Math.floor(Math.random() * carriers.length)];
      const model = models[Math.floor(Math.random() * models.length)];
      const agentId = Math.ceil(Math.random() * 20);
      const posId = Math.ceil(Math.random() * 100);
      await client.query(
        `INSERT INTO platform_billing_ledger (transaction_id, transaction_ref, transaction_type, agent_id, pos_terminal_id, gross_amount, gross_fee, agent_commission, switch_fee, aggregator_fee, platform_net_fee, billing_model, client_revenue, platform_revenue, revenue_share_pct, currency, region, carrier) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, 'NGN', $16, $17)`,
        [txId, txRef, txType, agentId, posId, grossAmount, grossFee, agentCommission, switchFee, aggregatorFee, platformNetFee, model, clientRevenue, platformRevenue, revSharePct, region, carrier]
      );
      count++;
    }
    await client.query("COMMIT");
    console.log(`✅ Seeded ${count} platform_billing_ledger entries`);
  } catch (err) {
    await client.query("ROLLBACK");
    console.error("Seed failed:", err.message);
  } finally {
    client.release();
    await pool.end();
  }
}
seed();
