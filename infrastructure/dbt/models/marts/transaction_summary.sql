-- 54Link POS Shell — dbt Transaction Summary Mart
-- Aggregated daily transaction metrics per agent
{{ config(materialized='incremental', unique_key='summary_date || agent_id') }}

WITH daily_txns AS (
    SELECT
        DATE(created_at) AS summary_date,
        agent_id,
        COUNT(*) AS total_transactions,
        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS successful_transactions,
        SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed_transactions,
        SUM(CASE WHEN status = 'reversed' THEN 1 ELSE 0 END) AS reversed_transactions,
        SUM(amount) AS total_volume,
        SUM(fee) AS total_fees,
        SUM(commission) AS total_commission,
        AVG(amount) AS avg_transaction_amount,
        MAX(amount) AS max_transaction_amount,
        COUNT(DISTINCT customer_phone) AS unique_customers
    FROM {{ ref('stg_transactions') }}
    {% if is_incremental() %}
    WHERE created_at > (SELECT MAX(summary_date) FROM {{ this }})
    {% endif %}
    GROUP BY DATE(created_at), agent_id
)

SELECT
    summary_date,
    agent_id,
    total_transactions,
    successful_transactions,
    failed_transactions,
    reversed_transactions,
    ROUND(successful_transactions::NUMERIC / NULLIF(total_transactions, 0) * 100, 2) AS success_rate,
    total_volume,
    total_fees,
    total_commission,
    avg_transaction_amount,
    max_transaction_amount,
    unique_customers,
    CURRENT_TIMESTAMP AS updated_at
FROM daily_txns
