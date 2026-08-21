import pg from "pg";
const { Pool } = pg;

// NF-SEC-6: the database connection must come from the environment; there is
// no hardcoded credential default. A passwordless localhost DSN is allowed
// only with an explicit ALLOW_INSECURE_LOCAL_DB=true opt-in, and never in
// production. (Matches scripts/seed.mjs round-1 pattern.)
const ALLOW_INSECURE_LOCAL_DB = process.env.ALLOW_INSECURE_LOCAL_DB === "true";
const IS_PRODUCTION = process.env.NODE_ENV === "production";

let POSTGRES_URL = process.env.POSTGRES_URL ?? process.env.DATABASE_URL;
if (!POSTGRES_URL) {
  if (IS_PRODUCTION) {
    console.error("FATAL: DATABASE_URL (or POSTGRES_URL) must be set when NODE_ENV=production; no default database credential exists.");
    process.exit(1);
  }
  if (!ALLOW_INSECURE_LOCAL_DB) {
    console.error("FATAL: DATABASE_URL (or POSTGRES_URL) is not set. Set it, or set ALLOW_INSECURE_LOCAL_DB=true to use a passwordless localhost DSN for local development only.");
    process.exit(1);
  }
  console.warn("WARNING: ALLOW_INSECURE_LOCAL_DB=true — using passwordless localhost database DSN (development only).");
  POSTGRES_URL = "postgresql://localhost:5432/pos54link";
}

const pool = new Pool({ connectionString: POSTGRES_URL, ssl: false });

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
