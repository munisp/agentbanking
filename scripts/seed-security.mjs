import { readFileSync, writeFileSync } from 'fs';
import pg from 'pg';
const { Client } = pg;

// Update drizzle journal
const journal = JSON.parse(readFileSync('drizzle/meta/_journal.json', 'utf8'));
const already = journal.entries.find(e => e.tag === '0006_blushing_ikaris');
if (!already) {
  journal.entries.push({ idx: 6, version: '7', when: Date.now(), tag: '0006_blushing_ikaris', breakpoints: true });
  writeFileSync('drizzle/meta/_journal.json', JSON.stringify(journal, null, 2));
  console.log('Journal updated');
} else {
  console.log('Already in journal');
}

const client = new Client({ connectionString: process.env.POSTGRES_URL });
await client.connect();

// Seed velocity limits
await client.query(`
  INSERT INTO velocity_limits (tier, "maxTxPerHour", "maxSingleTxAmount", "maxDailyVolume")
  VALUES
    ('Bronze',  20,  50000.00,   500000.00),
    ('Silver',  40, 100000.00,  1000000.00),
    ('Gold',    80, 200000.00,  2000000.00),
    ('Platinum',200, 500000.00, 5000000.00)
  ON CONFLICT (tier) DO NOTHING
`);

// Seed platform settings
await client.query(`
  INSERT INTO platform_settings (key, value, description)
  VALUES
    ('reversal_approval_threshold', '10000', 'Reversals above this amount (NGN) require admin approval'),
    ('float_topup_approval_threshold', '50000', 'Float top-ups above this amount (NGN) require supervisor approval'),
    ('customer_sms_enabled', 'true', 'Send SMS confirmation to customer on Cash Out and Transfer'),
    ('enrollment_token_required', 'false', 'Require device enrollment token on every transaction'),
    ('settlement_float_lock', 'true', 'Lock agent float during settlement window'),
    ('velocity_limits_enabled', 'true', 'Enforce per-tier velocity limits on transactions'),
    ('geofencing_enabled', 'false', 'Block transactions when agent device is outside assigned geofence zone')
  ON CONFLICT (key) DO NOTHING
`);

console.log('Seeded velocity_limits and platform_settings');
await client.end();
