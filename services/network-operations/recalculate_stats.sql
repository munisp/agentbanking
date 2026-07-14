-- Recalculate channel statistics from existing transaction records
-- This will populate the channel_statistics table based on transaction_records data

-- First, clear existing statistics (optional)
-- TRUNCATE TABLE channel_statistics;

-- Insert/Update statistics for all channel combinations
INSERT INTO channel_statistics (id, type, channel, medium, total_transactions, success_count, failure_count, success_rate, last_updated)
SELECT 
    gen_random_uuid() as id,
    type,
    channel,
    medium,
    COUNT(*) as total_transactions,
    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_count,
    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failure_count,
    ROUND((SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END)::numeric / COUNT(*)::numeric * 100), 2) as success_rate,
    NOW() as last_updated
FROM transaction_records
GROUP BY type, channel, medium
ON CONFLICT (type, channel, medium) 
DO UPDATE SET 
    total_transactions = EXCLUDED.total_transactions,
    success_count = EXCLUDED.success_count,
    failure_count = EXCLUDED.failure_count,
    success_rate = EXCLUDED.success_rate,
    last_updated = EXCLUDED.last_updated;

-- Show the results
SELECT 
    type,
    channel,
    medium,
    total_transactions,
    success_rate,
    success_count,
    failure_count
FROM channel_statistics
ORDER BY type, channel, medium;
