-- Commission Settlement Service - Seed Data
-- Run this script in psql shell
-- Usage: \i /path/to/seed_data.sql
-- or paste directly into psql

-- Set timezone
SET timezone = 'UTC';

-- Agent ID for ifegbesan Tanitoluwa
\set agent_id 'fe0fab2b-2052-4d84-a92d-81583f7acce6'

-- =====================================================
-- 1. SEED COMMISSION RULES
-- =====================================================

-- Agent tier - Basic transactions
INSERT INTO commission_rules (agent_tier, transaction_type, min_amount, max_amount, rate, flat_fee, is_active, effective_from, created_at, updated_at)
VALUES 
    ('agent', 'deposit', 0, 999999999, 0.001, 0, true, NOW() - INTERVAL '6 months', NOW(), NOW()),
    ('agent', 'withdrawal', 0, 999999999, 0.002, 0, true, NOW() - INTERVAL '6 months', NOW(), NOW()),
    ('agent', 'transfer', 0, 999999999, 0.0015, 0, true, NOW() - INTERVAL '6 months', NOW(), NOW());

-- Agent tier - Bill payments
INSERT INTO commission_rules (agent_tier, transaction_type, min_amount, max_amount, rate, flat_fee, is_active, effective_from, created_at, updated_at)
VALUES 
    ('agent', 'bill_payment', 0, 999999999, 0.005, 0, true, NOW() - INTERVAL '6 months', NOW(), NOW()),
    ('agent', 'electricity', 0, 999999999, 0.008, 50, true, NOW() - INTERVAL '6 months', NOW(), NOW()),
    ('agent', 'water', 0, 999999999, 0.007, 40, true, NOW() - INTERVAL '6 months', NOW(), NOW()),
    ('agent', 'cable', 0, 999999999, 0.01, 0, true, NOW() - INTERVAL '6 months', NOW(), NOW()),
    ('agent', 'internet', 0, 999999999, 0.009, 0, true, NOW() - INTERVAL '6 months', NOW(), NOW());

-- Agent tier - Donations
INSERT INTO commission_rules (agent_tier, transaction_type, min_amount, max_amount, rate, flat_fee, is_active, effective_from, created_at, updated_at)
VALUES 
    ('agent', 'donation', 0, 999999999, 0.003, 0, true, NOW() - INTERVAL '6 months', NOW(), NOW());

-- Agent tier - Airtime and Data
INSERT INTO commission_rules (agent_tier, transaction_type, min_amount, max_amount, rate, flat_fee, is_active, effective_from, created_at, updated_at)
VALUES 
    ('agent', 'airtime', 0, 999999999, 0.03, 0, true, NOW() - INTERVAL '6 months', NOW(), NOW()),
    ('agent', 'data', 0, 999999999, 0.03, 0, true, NOW() - INTERVAL '6 months', NOW(), NOW());

-- Senior Agent tier - Higher rates
INSERT INTO commission_rules (agent_tier, transaction_type, min_amount, max_amount, rate, flat_fee, is_active, effective_from, created_at, updated_at)
VALUES 
    ('senior_agent', 'deposit', 0, 999999999, 0.0015, 0, true, NOW() - INTERVAL '6 months', NOW(), NOW()),
    ('senior_agent', 'withdrawal', 0, 999999999, 0.0025, 0, true, NOW() - INTERVAL '6 months', NOW(), NOW()),
    ('senior_agent', 'bill_payment', 0, 999999999, 0.008, 0, true, NOW() - INTERVAL '6 months', NOW(), NOW()),
    ('senior_agent', 'airtime', 0, 999999999, 0.035, 0, true, NOW() - INTERVAL '6 months', NOW(), NOW()),
    ('senior_agent', 'data', 0, 999999999, 0.035, 0, true, NOW() - INTERVAL '6 months', NOW(), NOW());

-- Premium Agent tier - Highest rates
INSERT INTO commission_rules (agent_tier, transaction_type, min_amount, max_amount, rate, flat_fee, is_active, effective_from, created_at, updated_at)
VALUES 
    ('premium_agent', 'deposit', 0, 999999999, 0.002, 0, true, NOW() - INTERVAL '6 months', NOW(), NOW()),
    ('premium_agent', 'withdrawal', 0, 999999999, 0.003, 0, true, NOW() - INTERVAL '6 months', NOW(), NOW()),
    ('premium_agent', 'bill_payment', 0, 999999999, 0.01, 0, true, NOW() - INTERVAL '6 months', NOW(), NOW()),
    ('premium_agent', 'airtime', 0, 999999999, 0.04, 0, true, NOW() - INTERVAL '6 months', NOW(), NOW()),
    ('premium_agent', 'data', 0, 999999999, 0.04, 0, true, NOW() - INTERVAL '6 months', NOW(), NOW());

-- =====================================================
-- 2. SEED AGENT COMMISSIONS - PENDING (Recent 7 days)
-- =====================================================

INSERT INTO commissions (agent_id, transaction_id, transaction_ref, transaction_type, amount, rate, commission_amount, currency, status, earned_at, metadata, created_at, updated_at)
VALUES 
    -- Deposit
    ('fe0fab2b-2052-4d84-a92d-81583f7acce6', gen_random_uuid(), 'TXN-20260303-001', 'deposit', 50000, 0.001, 50, 'NGN', 'pending', NOW() - INTERVAL '1 day', 
     '{"customer_name": "John Doe", "channel": "mobile"}'::jsonb, NOW(), NOW()),
    
    -- Airtime MTN
    ('fe0fab2b-2052-4d84-a92d-81583f7acce6', gen_random_uuid(), 'TXN-20260303-002', 'airtime', 5000, 0.03, 150, 'NGN', 'pending', NOW() - INTERVAL '1 day',
     '{"provider": "MTN", "phone": "08012345678"}'::jsonb, NOW(), NOW()),
    
    -- Electricity
    ('fe0fab2b-2052-4d84-a92d-81583f7acce6', gen_random_uuid(), 'TXN-20260302-001', 'electricity', 15000, 0.008, 170, 'NGN', 'pending', NOW() - INTERVAL '2 days',
     '{"provider": "IKEDC", "meter_number": "12345678901"}'::jsonb, NOW(), NOW()),
    
    -- Donation
    ('fe0fab2b-2052-4d84-a92d-81583f7acce6', gen_random_uuid(), 'TXN-20260302-002', 'donation', 10000, 0.003, 30, 'NGN', 'pending', NOW() - INTERVAL '2 days',
     '{"organization": "Nigerian Red Cross Society", "category": "NGO"}'::jsonb, NOW(), NOW()),
    
    -- Withdrawal
    ('fe0fab2b-2052-4d84-a92d-81583f7acce6', gen_random_uuid(), 'TXN-20260301-001', 'withdrawal', 75000, 0.002, 150, 'NGN', 'pending', NOW() - INTERVAL '3 days',
     '{"customer_name": "Jane Smith", "channel": "pos"}'::jsonb, NOW(), NOW()),
    
    -- Data Airtel
    ('fe0fab2b-2052-4d84-a92d-81583f7acce6', gen_random_uuid(), 'TXN-20260301-002', 'data', 3000, 0.03, 90, 'NGN', 'pending', NOW() - INTERVAL '3 days',
     '{"provider": "Airtel", "phone": "08098765432", "plan": "5GB Monthly"}'::jsonb, NOW(), NOW()),
    
    -- Cable TV
    ('fe0fab2b-2052-4d84-a92d-81583f7acce6', gen_random_uuid(), 'TXN-20260228-001', 'cable', 8500, 0.01, 85, 'NGN', 'pending', NOW() - INTERVAL '4 days',
     '{"provider": "DSTV", "smartcard": "1234567890", "package": "Compact Plus"}'::jsonb, NOW(), NOW()),
    
    -- Transfer
    ('fe0fab2b-2052-4d84-a92d-81583f7acce6', gen_random_uuid(), 'TXN-20260228-002', 'transfer', 100000, 0.0015, 150, 'NGN', 'pending', NOW() - INTERVAL '4 days',
     '{"beneficiary": "Alice Johnson", "bank": "First Bank"}'::jsonb, NOW(), NOW());

-- =====================================================
-- 3. SEED AGENT COMMISSIONS - SETTLED (Older transactions)
-- =====================================================

INSERT INTO commissions (agent_id, transaction_id, transaction_ref, transaction_type, amount, rate, commission_amount, currency, status, earned_at, metadata, created_at, updated_at)
VALUES 
    -- Deposit
    ('fe0fab2b-2052-4d84-a92d-81583f7acce6', gen_random_uuid(), 'TXN-20260225-001', 'deposit', 200000, 0.001, 200, 'NGN', 'settled', NOW() - INTERVAL '7 days',
     '{"customer_name": "Michael Brown", "channel": "web"}'::jsonb, NOW() - INTERVAL '7 days', NOW()),
    
    -- Airtime Glo
    ('fe0fab2b-2052-4d84-a92d-81583f7acce6', gen_random_uuid(), 'TXN-20260224-001', 'airtime', 10000, 0.03, 300, 'NGN', 'settled', NOW() - INTERVAL '8 days',
     '{"provider": "Glo", "phone": "08055551234"}'::jsonb, NOW() - INTERVAL '8 days', NOW()),
    
    -- Electricity EKEDC
    ('fe0fab2b-2052-4d84-a92d-81583f7acce6', gen_random_uuid(), 'TXN-20260223-001', 'electricity', 25000, 0.008, 250, 'NGN', 'settled', NOW() - INTERVAL '9 days',
     '{"provider": "EKEDC", "meter_number": "98765432109"}'::jsonb, NOW() - INTERVAL '9 days', NOW()),
    
    -- Water
    ('fe0fab2b-2052-4d84-a92d-81583f7acce6', gen_random_uuid(), 'TXN-20260222-001', 'water', 5000, 0.007, 75, 'NGN', 'settled', NOW() - INTERVAL '10 days',
     '{"provider": "Lagos Water Corporation", "account_number": "WTR-12345"}'::jsonb, NOW() - INTERVAL '10 days', NOW()),
    
    -- Donation RCCG
    ('fe0fab2b-2052-4d84-a92d-81583f7acce6', gen_random_uuid(), 'TXN-20260220-001', 'donation', 50000, 0.003, 150, 'NGN', 'settled', NOW() - INTERVAL '12 days',
     '{"organization": "RCCG", "category": "Religious", "religion": "Christian"}'::jsonb, NOW() - INTERVAL '12 days', NOW()),
    
    -- Withdrawal
    ('fe0fab2b-2052-4d84-a92d-81583f7acce6', gen_random_uuid(), 'TXN-20260218-001', 'withdrawal', 150000, 0.002, 300, 'NGN', 'settled', NOW() - INTERVAL '14 days',
     '{"customer_name": "Sarah Williams", "channel": "mobile"}'::jsonb, NOW() - INTERVAL '14 days', NOW()),
    
    -- Data 9mobile
    ('fe0fab2b-2052-4d84-a92d-81583f7acce6', gen_random_uuid(), 'TXN-20260215-001', 'data', 5000, 0.03, 150, 'NGN', 'settled', NOW() - INTERVAL '17 days',
     '{"provider": "9mobile", "phone": "08177778888", "plan": "10GB Monthly"}'::jsonb, NOW() - INTERVAL '17 days', NOW()),
    
    -- Transfer GTBank
    ('fe0fab2b-2052-4d84-a92d-81583f7acce6', gen_random_uuid(), 'TXN-20260210-001', 'transfer', 250000, 0.0015, 375, 'NGN', 'settled', NOW() - INTERVAL '22 days',
     '{"beneficiary": "David Lee", "bank": "GTBank"}'::jsonb, NOW() - INTERVAL '22 days', NOW()),
    
    -- Cable GOtv
    ('fe0fab2b-2052-4d84-a92d-81583f7acce6', gen_random_uuid(), 'TXN-20260205-001', 'cable', 12000, 0.01, 120, 'NGN', 'settled', NOW() - INTERVAL '27 days',
     '{"provider": "GOtv", "smartcard": "9876543210", "package": "Max"}'::jsonb, NOW() - INTERVAL '27 days', NOW()),
    
    -- Internet
    ('fe0fab2b-2052-4d84-a92d-81583f7acce6', gen_random_uuid(), 'TXN-20260203-001', 'internet', 20000, 0.009, 180, 'NGN', 'settled', NOW() - INTERVAL '29 days',
     '{"provider": "Spectranet", "plan": "Unlimited"}'::jsonb, NOW() - INTERVAL '29 days', NOW()),
    
    -- More transactions for variety
    ('fe0fab2b-2052-4d84-a92d-81583f7acce6', gen_random_uuid(), 'TXN-20260201-001', 'deposit', 80000, 0.001, 80, 'NGN', 'settled', NOW() - INTERVAL '31 days',
     '{"customer_name": "Peter Parker", "channel": "mobile"}'::jsonb, NOW() - INTERVAL '31 days', NOW()),
    
    ('fe0fab2b-2052-4d84-a92d-81583f7acce6', gen_random_uuid(), 'TXN-20260130-001', 'airtime', 8000, 0.03, 240, 'NGN', 'settled', NOW() - INTERVAL '33 days',
     '{"provider": "MTN", "phone": "08123456789"}'::jsonb, NOW() - INTERVAL '33 days', NOW());

-- =====================================================
-- 4. CREATE SETTLEMENTS
-- =====================================================

-- First settlement (older commissions)
WITH settlement1 AS (
    INSERT INTO settlements (settlement_ref, agent_id, total_amount, commission_count, currency, status, payment_method, payment_details, processed_at, start_date, end_date, created_at, updated_at)
    VALUES (
        'STL-' || EXTRACT(EPOCH FROM (NOW() - INTERVAL '14 days'))::bigint || '-fe0fab2b',
        'fe0fab2b-2052-4d84-a92d-81583f7acce6',
        1495,  -- Sum of first 6 settled commissions
        6,
        'NGN',
        'completed',
        'bank_transfer',
        '{"bank_name": "First Bank", "account_number": "1234567890", "account_name": "ifegbesan Tanitoluwa"}'::jsonb,
        NOW() - INTERVAL '13 days',
        NOW() - INTERVAL '21 days',
        NOW() - INTERVAL '14 days',
        NOW() - INTERVAL '14 days',
        NOW() - INTERVAL '13 days'
    )
    RETURNING id
)
UPDATE commissions 
SET settlement_id = (SELECT id FROM settlement1)
WHERE transaction_ref IN ('TXN-20260210-001', 'TXN-20260205-001', 'TXN-20260203-001', 'TXN-20260201-001', 'TXN-20260130-001', 'TXN-20260215-001');

-- Second settlement (newer settled commissions)
WITH settlement2 AS (
    INSERT INTO settlements (settlement_ref, agent_id, total_amount, commission_count, currency, status, payment_method, payment_details, processed_at, start_date, end_date, created_at, updated_at)
    VALUES (
        'STL-' || EXTRACT(EPOCH FROM (NOW() - INTERVAL '7 days'))::bigint || '-fe0fab2b',
        'fe0fab2b-2052-4d84-a92d-81583f7acce6',
        1275,  -- Sum of next 6 settled commissions
        6,
        'NGN',
        'completed',
        'bank_transfer',
        '{"bank_name": "First Bank", "account_number": "1234567890", "account_name": "ifegbesan Tanitoluwa"}'::jsonb,
        NOW() - INTERVAL '6 days',
        NOW() - INTERVAL '14 days',
        NOW() - INTERVAL '7 days',
        NOW() - INTERVAL '7 days',
        NOW() - INTERVAL '6 days'
    )
    RETURNING id
)
UPDATE commissions 
SET settlement_id = (SELECT id FROM settlement2)
WHERE transaction_ref IN ('TXN-20260225-001', 'TXN-20260224-001', 'TXN-20260223-001', 'TXN-20260222-001', 'TXN-20260220-001', 'TXN-20260218-001');

-- =====================================================
-- 5. CREATE/UPDATE AGENT BALANCE
-- =====================================================

INSERT INTO agent_balances (agent_id, pending_balance, available_balance, settled_balance, total_earned, currency, last_settlement_at, created_at, updated_at)
VALUES (
    'fe0fab2b-2052-4d84-a92d-81583f7acce6',
    875,    -- Sum of pending commissions
    2770,   -- Sum of settled commissions
    0,      -- Will be updated when fully processed
    3645,   -- Total earned (pending + settled)
    'NGN',
    NOW() - INTERVAL '6 days',
    NOW(),
    NOW()
)
ON CONFLICT (agent_id) 
DO UPDATE SET
    pending_balance = EXCLUDED.pending_balance,
    available_balance = EXCLUDED.available_balance,
    total_earned = EXCLUDED.total_earned,
    last_settlement_at = EXCLUDED.last_settlement_at,
    updated_at = NOW();

-- =====================================================
-- VERIFICATION QUERIES
-- =====================================================

\echo ''
\echo '=========================================='
\echo 'SEEDING COMPLETED!'
\echo '=========================================='
\echo ''

\echo 'Commission Rules Count:'
SELECT COUNT(*) as total_rules FROM commission_rules;

\echo ''
\echo 'Agent Commissions Summary:'
SELECT 
    status,
    COUNT(*) as count,
    SUM(commission_amount) as total_amount,
    currency
FROM commissions
WHERE agent_id = 'fe0fab2b-2052-4d84-a92d-81583f7acce6'
GROUP BY status, currency
ORDER BY status;

\echo ''
\echo 'Commissions by Transaction Type:'
SELECT 
    transaction_type,
    COUNT(*) as count,
    SUM(commission_amount) as total_commission,
    AVG(rate) as avg_rate
FROM commissions
WHERE agent_id = 'fe0fab2b-2052-4d84-a92d-81583f7acce6'
GROUP BY transaction_type
ORDER BY total_commission DESC;

\echo ''
\echo 'Agent Balance:'
SELECT 
    pending_balance,
    available_balance,
    settled_balance,
    total_earned,
    currency,
    last_settlement_at
FROM agent_balances
WHERE agent_id = 'fe0fab2b-2052-4d84-a92d-81583f7acce6';

\echo ''
\echo 'Settlements:'
SELECT 
    settlement_ref,
    total_amount,
    commission_count,
    status,
    processed_at
FROM settlements
WHERE agent_id = 'fe0fab2b-2052-4d84-a92d-81583f7acce6'
ORDER BY processed_at DESC;

\echo ''
\echo '=========================================='
\echo 'Seed data loaded successfully!'
\echo '=========================================='
