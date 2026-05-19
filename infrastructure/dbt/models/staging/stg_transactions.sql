-- 54Link POS Shell — Staging: Transactions
{{ config(materialized='view') }}

SELECT
    id,
    agent_id,
    type AS transaction_type,
    amount,
    fee,
    commission,
    currency,
    status,
    channel,
    customer_phone,
    customer_name,
    reference,
    terminal_id,
    state,
    city,
    latitude,
    longitude,
    risk_score,
    created_at,
    completed_at,
    EXTRACT(HOUR FROM created_at) AS transaction_hour,
    EXTRACT(DOW FROM created_at) AS transaction_day_of_week,
    CASE
        WHEN amount < 5000 THEN 'micro'
        WHEN amount < 50000 THEN 'small'
        WHEN amount < 200000 THEN 'medium'
        WHEN amount < 1000000 THEN 'large'
        ELSE 'enterprise'
    END AS amount_tier
FROM {{ source('posshell', 'transactions') }}
