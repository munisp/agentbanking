/**
 * Sprint 50 Seed Data Script — Aligned with actual DB schema
 * Run: unset DATABASE_URL && node scripts/seed-sprint50.mjs
 */
import pg from "pg";
const { Pool } = pg;

const pool = new Pool({
  connectionString: process.env.POSTGRES_URL || "postgresql://posadmin:posadmin123@localhost:5432/posshell",
  ssl: false,
});

async function seed() {
  const client = await pool.connect();
  try {
    console.log("🌱 Seeding Sprint 50 tables...");

    // Truncate all Sprint 50 tables first
    await client.query(`
      TRUNCATE realtime_tx_alerts, fraud_ml_scores, notification_templates,
        webhook_subscriptions, webhook_delivery_logs, sla_definitions, sla_breaches,
        data_export_jobs, platform_health_checks, platform_incidents CASCADE
    `);

    // F01: Real-Time Transaction Monitor Alerts
    await client.query(`
      INSERT INTO realtime_tx_alerts (alert_type, severity, tx_reference, amount, merchant_id, agent_id, description, status, created_at)
      SELECT
        (ARRAY['velocity_breach','amount_threshold','geo_anomaly','device_mismatch','time_anomaly'])[floor(random()*5+1)],
        (ARRAY['low','medium','high','critical'])[floor(random()*4+1)],
        'TXN-' || lpad(floor(random()*999999)::text, 6, '0'),
        (random() * 500000 + 1000)::numeric(15,2),
        floor(random()*50+1)::int,
        floor(random()*100+1)::int,
        'Auto-detected anomaly in transaction pattern',
        (ARRAY['open','investigating','resolved','dismissed'])[floor(random()*4+1)],
        now() - (random() * interval '30 days')
      FROM generate_series(1, 50)
    `);
    console.log("  ✅ realtime_tx_alerts: 50 rows");

    // F02: Fraud ML Scoring
    await client.query(`
      INSERT INTO fraud_ml_scores (transaction_id, agent_id, risk_score, model_version, features, prediction, confidence, created_at)
      SELECT
        floor(random()*10000+1)::int,
        floor(random()*100+1)::int,
        (random() * 100)::numeric(5,2),
        'v2.3.1',
        '{"velocity":' || floor(random()*10) || ',"amount_zscore":' || round((random()*4)::numeric,2) || ',"geo_distance":' || floor(random()*500) || '}',
        (ARRAY['legitimate','suspicious','fraudulent'])[floor(random()*3+1)],
        (random())::numeric(5,4),
        now() - (random() * interval '30 days')
      FROM generate_series(1, 100)
    `);
    console.log("  ✅ fraud_ml_scores: 100 rows");

    // F03: Notification Templates
    await client.query(`
      INSERT INTO notification_templates (name, channel, subject, body, variables, active, created_at)
      VALUES
        ('Transaction Success', 'sms', NULL, 'Dear {{name}}, your transaction of N{{amount}} was successful. Ref: {{reference}}', '["name","amount","reference"]', true, now()),
        ('Transaction Failed', 'sms', NULL, 'Dear {{name}}, your transaction of N{{amount}} failed. Please retry.', '["name","amount","reference"]', true, now()),
        ('KYC Approved', 'email', 'KYC Verification Approved', 'Dear {{name}}, your KYC verification has been approved.', '["name"]', true, now()),
        ('Commission Paid', 'push', 'Commission Payment', 'You earned N{{amount}} commission on {{date}}.', '["amount","date","balance"]', true, now()),
        ('Fraud Alert', 'email', 'Suspicious Activity Detected', 'A suspicious transaction was detected. Reference: {{reference}}.', '["reference","amount"]', true, now()),
        ('Float Low', 'sms', NULL, 'Your float balance is low (N{{balance}}). Please top up.', '["balance"]', true, now()),
        ('Payout Completed', 'email', 'Payout Processed', 'Your payout of N{{amount}} has been processed.', '["amount","account"]', true, now()),
        ('System Maintenance', 'push', 'Scheduled Maintenance', 'System maintenance scheduled for {{date}}.', '["date","start_time","end_time"]', true, now())
    `);
    console.log("  ✅ notification_templates: 8 rows");

    // F04: Agent Loans (actual columns: agent_id, loan_type, principal_amount, interest_rate, tenor_days, total_repayable, amount_repaid, status, credit_score)
    await client.query(`
      INSERT INTO agent_loans (agent_id, loan_type, principal_amount, interest_rate, tenor_days, total_repayable, amount_repaid, status, credit_score, created_at)
      SELECT
        floor(random()*100+1)::int,
        (ARRAY['working_capital','float_advance','equipment','emergency'])[floor(random()*4+1)],
        (random() * 2000000 + 50000)::numeric(15,2),
        (random() * 15 + 5)::numeric(5,2),
        (ARRAY[30,60,90,180,365])[floor(random()*5+1)],
        (random() * 2500000 + 60000)::numeric(15,2),
        (random() * 1000000)::numeric(15,2),
        ((ARRAY['pending','approved','disbursed','repaying','completed','defaulted'])[floor(random()*6+1)])::loan_status,
        floor(random()*400+300)::int,
        now() - (random() * interval '180 days')
      FROM generate_series(1, 30)
    `);
    console.log("  ✅ agent_loans: 30 rows");

    // F05: Fee Rules (actual columns: name, tx_type, agent_tier, min_amount, max_amount, fee_type, fee_value, min_fee, max_fee, is_active, priority)
    await client.query(`
      INSERT INTO fee_rules (name, tx_type, agent_tier, fee_type, fee_value, min_fee, max_fee, is_active, priority, created_at)
      VALUES
        ('Cash Withdrawal Fee', 'withdrawal', 'all', 'percentage', '1.50', '100', '2000', true, 1, now()),
        ('Transfer Fee', 'transfer', 'all', 'flat', '50', NULL, NULL, true, 2, now()),
        ('Bill Payment Fee', 'bill_payment', 'all', 'percentage', '0.75', '50', '500', true, 3, now()),
        ('Airtime Purchase Fee', 'airtime', 'all', 'flat', '20', NULL, NULL, true, 4, now()),
        ('Cash Deposit Fee', 'deposit', 'all', 'tiered', '0', NULL, NULL, true, 5, now()),
        ('Inter-bank Transfer', 'nip_transfer', 'all', 'percentage', '0.50', '10', '50', true, 6, now()),
        ('USSD Withdrawal', 'withdrawal', 'basic', 'flat', '30', NULL, NULL, true, 7, now()),
        ('QR Payment Fee', 'qr_payment', 'all', 'percentage', '0.25', '5', '100', true, 8, now())
    `);
    console.log("  ✅ fee_rules: 8 rows");

    // F06: Merchant KYC Docs (actual columns: merchant_id, doc_type, doc_url, status)
    await client.query(`
      INSERT INTO merchant_kyc_docs (merchant_id, doc_type, doc_url, status, created_at)
      SELECT
        floor(random()*30+1)::int,
        (ARRAY['cac_certificate','tin_certificate','utility_bill','bank_statement','id_card','passport','bvn_verification','memart'])[floor(random()*8+1)],
        'https://storage.example.com/kyc/doc-' || floor(random()*9999) || '.pdf',
        (ARRAY['pending','approved','rejected'])[floor(random()*3+1)],
        now() - (random() * interval '60 days')
      FROM generate_series(1, 40)
    `);
    console.log("  ✅ merchant_kyc_docs: 40 rows");

    // F07: Merchant Payouts (actual columns: merchant_id, amount, currency, bank_code, account_number, account_name, reference, status, period_start, period_end, tx_count)
    await client.query(`
      INSERT INTO merchant_payouts (merchant_id, amount, currency, bank_code, account_number, account_name, reference, status, period_start, period_end, tx_count, created_at)
      SELECT
        floor(random()*30+1)::int,
        (random() * 5000000 + 10000)::numeric(15,2),
        'NGN',
        (ARRAY['044','058','011','033','057','215','050'])[floor(random()*7+1)],
        lpad(floor(random()*9999999999)::text, 10, '0'),
        'Merchant ' || floor(random()*30+1) || ' Ltd',
        'PAY-' || lpad(floor(random()*999999)::text, 6, '0'),
        (ARRAY['pending','approved','processing','completed','failed'])[floor(random()*5+1)],
        now() - interval '7 days',
        now(),
        floor(random()*500+10)::int,
        now() - (random() * interval '30 days')
      FROM generate_series(1, 40)
    `);
    console.log("  ✅ merchant_payouts: 40 rows");

    // F08: Compliance Filings (actual columns: filing_type, reference_number, status, reporting_period, submitted_to, total_transactions, total_amount, flagged_count, filing_data)
    await client.query(`
      INSERT INTO compliance_filings (filing_type, reference_number, status, reporting_period, submitted_to, total_transactions, total_amount, flagged_count, filing_data, created_at)
      SELECT
        (ARRAY['SAR','CTR','STR','CBN_RETURNS','NDIC_REPORT','FIRS_TAX','AML_REPORT'])[floor(random()*7+1)],
        'CF-' || lpad(floor(random()*999999)::text, 6, '0'),
        (ARRAY['draft','submitted','acknowledged'])[floor(random()*3+1)],
        to_char(now() - (i * interval '30 days'), 'YYYY-MM'),
        (ARRAY['CBN','NDIC','FIRS','EFCC','NFIU'])[floor(random()*5+1)],
        floor(random()*100000)::int,
        (random()*500000000)::numeric(15,2),
        floor(random()*50)::int,
        '{"summary":"Auto-generated filing"}',
        now() - (i * interval '30 days')
      FROM generate_series(1, 20) as s(i)
    `);
    console.log("  ✅ compliance_filings: 20 rows");

    // F09: Agent Achievements (actual columns: agent_id, achievement_type, title, description, badge_icon, points, level, unlocked_at)
    await client.query(`
      INSERT INTO agent_achievements (agent_id, achievement_type, title, description, points, level, unlocked_at)
      SELECT
        floor(random()*100+1)::int,
        (ARRAY['first_tx','tx_milestone','volume_milestone','streak','referral','badge_earned'])[floor(random()*6+1)],
        (ARRAY['First Transaction','Century Club','Volume Champion','Streak Master','Referral King'])[floor(random()*5+1)],
        'Achievement unlocked for outstanding performance',
        floor(random()*500+10)::int,
        floor(random()*5+1)::int,
        now() - (random() * interval '90 days')
      FROM generate_series(1, 200)
    `);
    // Agent Badges (actual columns: name, description, icon, category, requirement, points_value, is_active)
    await client.query(`
      INSERT INTO agent_badges (name, description, icon, category, requirement, points_value, is_active, created_at)
      VALUES
        ('First Transaction', 'Complete your first transaction', 'trophy', 'milestone', 'Complete 1 transaction', 10, true, now()),
        ('Century Club', 'Complete 100 transactions', 'star', 'milestone', 'Complete 100 transactions', 50, true, now()),
        ('Transaction Master', 'Complete 1000 transactions', 'crown', 'milestone', 'Complete 1000 transactions', 200, true, now()),
        ('Millionaire Agent', 'Process N1M in volume', 'diamond', 'volume', 'Process N1,000,000 volume', 100, true, now()),
        ('Volume Champion', 'Process N10M in volume', 'medal', 'volume', 'Process N10,000,000 volume', 500, true, now()),
        ('Streak Master', '30-day active streak', 'fire', 'streak', '30 consecutive active days', 150, true, now()),
        ('Referral King', 'Refer 10 agents', 'users', 'referral', 'Refer 10 active agents', 300, true, now()),
        ('Zero Fraud', 'No fraud incidents in 90 days', 'shield', 'compliance', 'Zero fraud for 90 days', 250, true, now())
    `);
    console.log("  ✅ agent_achievements: 200 rows, agent_badges: 8 rows");

    // F10: Tenant Feature Toggles (actual columns: tenant_id, feature_key, enabled, config)
    await client.query(`
      INSERT INTO tenant_feature_toggles (tenant_id, feature_key, enabled, config, created_at)
      VALUES
        (1, 'ussd_channel', true, '{"rollout":100}', now()),
        (1, 'qr_payments', true, '{"rollout":80}', now()),
        (1, 'biometric_auth', false, '{"rollout":0}', now()),
        (1, 'ai_fraud_detection', true, '{"rollout":50}', now()),
        (1, 'multi_currency', false, '{"rollout":0}', now()),
        (2, 'ussd_channel', true, '{"rollout":100}', now()),
        (2, 'qr_payments', false, '{"rollout":0}', now()),
        (2, 'biometric_auth', true, '{"rollout":100}', now()),
        (2, 'ai_fraud_detection', true, '{"rollout":100}', now()),
        (3, 'ussd_channel', true, '{"rollout":100}', now()),
        (3, 'mobile_money', true, '{"rollout":75}', now()),
        (3, 'agent_loans', true, '{"rollout":30}', now())
    `);
    console.log("  ✅ tenant_feature_toggles: 12 rows");

    // F11: Reconciliation Batches (actual columns: batch_reference, source_type, total_records, matched_count, unmatched_count, discrepancy_count, total_amount, status)
    await client.query(`
      INSERT INTO reconciliation_batches (batch_reference, source_type, total_records, matched_count, unmatched_count, discrepancy_count, total_amount, status, created_at)
      SELECT
        'RECON-' || to_char(now() - (i * interval '1 day'), 'YYYYMMDD'),
        (ARRAY['pos_terminal','bank_settlement','nibss','interswitch'])[floor(random()*4+1)],
        floor(random()*515+50)::int,
        floor(random()*500+50)::int,
        floor(random()*10)::int,
        floor(random()*15)::int,
        (random()*50000000+1000000)::numeric(15,2),
        (ARRAY['pending','completed','completed','completed'])[floor(random()*4+1)],
        now() - (i * interval '1 day')
      FROM generate_series(1, 30) as s(i)
    `);
    console.log("  ✅ reconciliation_batches: 30 rows");

    // F12: Customer Journey Steps (actual columns: customer_id, step_type, status, metadata)
    await client.query(`
      INSERT INTO customer_journey_steps (customer_id, step_type, status, metadata, created_at)
      SELECT
        floor(random()*200+1)::int,
        (ARRAY['awareness','registration','verification','first_use','activation','retention'])[floor(random()*6+1)],
        (ARRAY['pending','completed','skipped'])[floor(random()*3+1)],
        '{"channel":"' || (ARRAY['pos','ussd','mobile','web','whatsapp'])[floor(random()*5+1)] || '"}',
        now() - (random() * interval '90 days')
      FROM generate_series(1, 100)
    `);
    console.log("  ✅ customer_journey_steps: 100 rows");

    // F13: Rate Limit Rules (actual columns: endpoint, method, max_requests, window_seconds, burst_limit, scope, is_active)
    await client.query(`
      INSERT INTO rate_limit_rules (endpoint, method, max_requests, window_seconds, burst_limit, scope, is_active, created_at)
      VALUES
        ('/api/*', '*', 1000, 60, 50, 'global', true, now()),
        ('/api/auth/login', 'POST', 5, 300, 2, 'per_ip', true, now()),
        ('/api/trpc/transactions.create', 'POST', 30, 60, 5, 'per_agent', true, now()),
        ('/api/trpc/export.*', 'GET', 10, 3600, 0, 'per_user', true, now()),
        ('/api/webhooks/*', 'POST', 100, 60, 20, 'global', true, now()),
        ('/api/trpc/floatTopUp.create', 'POST', 20, 60, 3, 'per_agent', true, now()),
        ('/api/trpc/sms.*', 'POST', 50, 60, 10, 'global', true, now()),
        ('/api/trpc/bulkOps.*', 'POST', 5, 3600, 0, 'per_user', true, now())
    `);
    console.log("  ✅ rate_limit_rules: 8 rows");

    // F14: Backup Snapshots (actual columns: snapshot_type, status, size_bytes, storage_url, tables_included, rows_backed_up, duration_ms, rto_minutes, rpo_minutes)
    await client.query(`
      INSERT INTO backup_snapshots (snapshot_type, status, size_bytes, storage_url, tables_included, rows_backed_up, duration_ms, rto_minutes, rpo_minutes, triggered_by, completed_at, created_at)
      SELECT
        (CASE WHEN (i%7)=1 THEN 'full' ELSE 'incremental' END),
        'completed',
        (CASE WHEN (i%7)=1 THEN floor(random()*1000000000+500000000) ELSE floor(random()*500000000+100000000) END)::int,
        'https://s3.example.com/backups/backup-' || to_char(now() - (i * interval '1 day'), 'YYYYMMDD') || '.tar.gz',
        4,
        floor(random()*500000+10000)::int,
        floor(random()*300000+60000)::int,
        15,
        5,
        'system',
        now() - (i * interval '1 day'),
        now() - (i * interval '1 day')
      FROM generate_series(1, 30) as s(i)
    `);
    console.log("  ✅ backup_snapshots: 30 rows");

    // F15: Workflow Definitions (actual columns: name, description, category, steps, sla_hours, is_active, version)
    await client.query(`
      INSERT INTO workflow_definitions (name, description, category, steps, sla_hours, is_active, version, created_at)
      VALUES
        ('Agent Onboarding', 'Complete agent onboarding workflow', 'onboarding', '[{"name":"Document Collection","type":"form"},{"name":"KYC Verification","type":"approval"},{"name":"Training","type":"task"},{"name":"Activation","type":"approval"}]', 48, true, 1, now()),
        ('Loan Approval', 'Agent loan approval workflow', 'finance', '[{"name":"Application Review","type":"approval"},{"name":"Credit Check","type":"automated"},{"name":"Manager Approval","type":"approval"},{"name":"Disbursement","type":"task"}]', 72, true, 1, now()),
        ('Dispute Resolution', 'Transaction dispute resolution', 'support', '[{"name":"Intake","type":"form"},{"name":"Investigation","type":"task"},{"name":"Resolution","type":"approval"},{"name":"Communication","type":"task"}]', 24, true, 1, now()),
        ('Merchant KYC', 'Merchant KYC verification workflow', 'compliance', '[{"name":"Document Upload","type":"form"},{"name":"Verification","type":"approval"},{"name":"Background Check","type":"automated"},{"name":"Final Approval","type":"approval"}]', 96, true, 1, now()),
        ('Commission Payout', 'Commission calculation and payout', 'finance', '[{"name":"Calculate","type":"automated"},{"name":"Review","type":"approval"},{"name":"Approve","type":"approval"},{"name":"Disburse","type":"task"}]', 12, true, 1, now())
      ON CONFLICT DO NOTHING
    `);
    // Workflow Instances (actual columns: definition_id, entity_type, entity_id, current_step, status, started_at)
    await client.query(`
      INSERT INTO workflow_instances (definition_id, entity_type, entity_id, current_step, status, started_at, created_at)
      SELECT
        floor(random()*5+1)::int,
        (ARRAY['agent','merchant','loan','dispute','commission'])[floor(random()*5+1)],
        floor(random()*1000+1)::int,
        floor(random()*4)::int,
        (ARRAY['running','running','completed','failed','cancelled'])[floor(random()*5+1)],
        now() - (random() * interval '30 days'),
        now() - (random() * interval '30 days')
      FROM generate_series(1, 25)
    `);
    console.log("  ✅ workflow_definitions: 5 rows, workflow_instances: 25 rows");

    // F16: GL Entries (actual columns: account_code, account_name, entry_type, amount, currency, reference, description, period_date)
    await client.query(`
      INSERT INTO gl_entries (account_code, account_name, entry_type, amount, currency, reference, description, period_date, created_at)
      VALUES
        ('1000', 'Cash & Bank', 'debit', '5000000', 'NGN', 'JNL-001', 'Daily POS collections', now() - interval '1 day', now()),
        ('4000', 'Transaction Fee Revenue', 'credit', '5000000', 'NGN', 'JNL-001', 'Daily POS collections', now() - interval '1 day', now()),
        ('5100', 'Agent Commission Expense', 'debit', '750000', 'NGN', 'JNL-002', 'Monthly commission payout', now() - interval '2 days', now()),
        ('1000', 'Cash & Bank', 'credit', '750000', 'NGN', 'JNL-002', 'Monthly commission payout', now() - interval '2 days', now()),
        ('1100', 'Agent Float Receivable', 'debit', '10000000', 'NGN', 'JNL-003', 'Float advance to agents', now() - interval '3 days', now()),
        ('1000', 'Cash & Bank', 'credit', '10000000', 'NGN', 'JNL-003', 'Float advance to agents', now() - interval '3 days', now()),
        ('2200', 'Tax Payable (VAT)', 'debit', '375000', 'NGN', 'JNL-004', 'VAT remittance Q1', now() - interval '5 days', now()),
        ('1000', 'Cash & Bank', 'credit', '375000', 'NGN', 'JNL-004', 'VAT remittance Q1', now() - interval '5 days', now())
    `);
    console.log("  ✅ gl_entries: 8 rows (4 journal entries)");

    // F17: Webhook Subscriptions & Delivery Logs
    await client.query(`
      INSERT INTO webhook_subscriptions (url, events, secret, description, active, created_at)
      VALUES
        ('https://partner1.example.com/webhooks', '["transaction.completed","transaction.failed"]', '${randomHex()}', 'Partner 1 - Transaction Events', true, now()),
        ('https://partner2.example.com/hooks', '["agent.created","agent.activated"]', '${randomHex()}', 'Partner 2 - Agent Events', true, now()),
        ('https://compliance.example.com/api/events', '["fraud.alert","fraud.confirmed"]', '${randomHex()}', 'Compliance - Fraud Events', true, now()),
        ('https://accounting.example.com/webhooks', '["commission.calculated","commission.paid"]', '${randomHex()}', 'Accounting - Financial Events', true, now()),
        ('https://monitoring.example.com/ingest', '["transaction.completed","payout.initiated"]', '${randomHex()}', 'Monitoring - All Events', true, now())
    `);
    await client.query(`
      INSERT INTO webhook_delivery_logs (subscription_id, event_type, payload, status, response_code, response_time, delivered_at, created_at)
      SELECT
        floor(random()*5+1)::int,
        (ARRAY['transaction.completed','agent.created','fraud.alert','commission.paid','payout.completed'])[floor(random()*5+1)],
        '{"event":"test","timestamp":"' || now() || '"}',
        (ARRAY['delivered','delivered','delivered','failed','retrying'])[floor(random()*5+1)],
        (ARRAY[200,200,200,500,503])[floor(random()*5+1)],
        floor(random()*500+50)::int,
        now() - (random() * interval '7 days'),
        now() - (random() * interval '7 days')
      FROM generate_series(1, 50)
    `);
    console.log("  ✅ webhook_subscriptions: 5 rows, webhook_delivery_logs: 50 rows");

    // F18: SLA Definitions & Breaches
    await client.query(`
      INSERT INTO sla_definitions (name, service_name, metric, target_value, unit, measurement_window, breach_threshold, active, created_at)
      VALUES
        ('API Uptime', 'api-gateway', 'uptime', '99.95', 'percentage', 'monthly', '99.90', true, now()),
        ('Transaction Latency', 'transaction-engine', 'p95_latency', '500', 'milliseconds', 'hourly', '1000', true, now()),
        ('Settlement Time', 'settlement-service', 'settlement_time', '24', 'hours', 'daily', '48', true, now()),
        ('Fraud Detection Speed', 'fraud-detection', 'detection_time', '5', 'seconds', 'per_transaction', '10', true, now()),
        ('Notification Delivery', 'notification-service', 'delivery_rate', '99.00', 'percentage', 'daily', '95.00', true, now()),
        ('Database Response', 'database', 'query_time', '100', 'milliseconds', 'hourly', '500', true, now())
    `);
    await client.query(`
      INSERT INTO sla_breaches (sla_id, actual_value, severity, description, breached_at, created_at)
      SELECT
        floor(random()*6+1)::int,
        (random() * 100)::numeric(10,2)::text,
        (ARRAY['warning','minor','major','critical'])[floor(random()*4+1)],
        'SLA breach detected during monitoring window',
        now() - (random() * interval '30 days'),
        now() - (random() * interval '30 days')
      FROM generate_series(1, 15)
    `);
    console.log("  ✅ sla_definitions: 6 rows, sla_breaches: 15 rows");

    // F19: Data Export Jobs
    await client.query(`
      INSERT INTO data_export_jobs (job_name, export_type, format, delivery_channel, status, row_count, file_size_bytes, created_at)
      SELECT
        'Export-' || (ARRAY['Transactions','Agents','Commissions','Merchants','Fraud','Compliance'])[floor(random()*6+1)] || '-' || to_char(now() - (i * interval '1 day'), 'MMDD'),
        (ARRAY['transactions','agents','commissions','merchants','fraud','compliance'])[floor(random()*6+1)],
        (ARRAY['csv','pdf','xlsx','json'])[floor(random()*4+1)],
        (ARRAY['download','email','s3'])[floor(random()*3+1)],
        (ARRAY['pending','completed','completed','completed','failed'])[floor(random()*5+1)],
        floor(random()*50000+100)::int,
        floor(random()*10000000+10000)::text,
        now() - (i * interval '1 day')
      FROM generate_series(1, 20) as s(i)
    `);
    console.log("  ✅ data_export_jobs: 20 rows");

    // F20: Platform Health Checks & Incidents
    await client.query(`
      INSERT INTO platform_health_checks (service_name, status, latency_ms, checked_at, created_at)
      SELECT
        (ARRAY['api-gateway','transaction-engine','fraud-detection','settlement-service','notification-service','database','redis-cache','message-queue','commission-engine','webhook-delivery','s3-storage','auth-service'])[floor(random()*12+1)],
        (ARRAY['healthy','healthy','healthy','healthy','degraded'])[floor(random()*5+1)],
        floor(random()*200+5)::int,
        now() - (i * interval '5 minutes'),
        now() - (i * interval '5 minutes')
      FROM generate_series(1, 100) as s(i)
    `);
    await client.query(`
      INSERT INTO platform_incidents (title, description, severity, affected_services, status, reported_at, created_at)
      VALUES
        ('Notification Service Latency Spike', 'Notification delivery latency increased to 500ms+', 'medium', '["notification-service"]', 'monitoring', now() - interval '2 hours', now() - interval '2 hours'),
        ('Redis Cache Failover', 'Primary Redis node failed, automatic failover to replica', 'high', '["redis-cache"]', 'resolved', now() - interval '2 days', now() - interval '2 days'),
        ('Database Connection Pool Exhaustion', 'Connection pool reached 95% capacity', 'critical', '["database","api-gateway"]', 'resolved', now() - interval '5 days', now() - interval '5 days')
    `);
    console.log("  ✅ platform_health_checks: 100 rows, platform_incidents: 3 rows");

    console.log("\n🎉 Sprint 50 seeding complete! All tables populated.");
  } catch (err) {
    console.error("❌ Seed error:", err.message);
    throw err;
  } finally {
    client.release();
    await pool.end();
  }
}

function randomHex() {
  return Array.from({ length: 32 }, () => Math.floor(Math.random() * 16).toString(16)).join("");
}

seed().catch(console.error);
