-- 54Link POS Shell — dbt Fraud Analytics Mart
{{ config(materialized='table') }}

WITH fraud_metrics AS (
    SELECT
        DATE(created_at) AS report_date,
        category,
        severity,
        COUNT(*) AS alert_count,
        AVG(risk_score) AS avg_risk_score,
        SUM(CASE WHEN status = 'confirmed_fraud' THEN 1 ELSE 0 END) AS confirmed_fraud,
        SUM(CASE WHEN status = 'false_positive' THEN 1 ELSE 0 END) AS false_positives,
        SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) AS open_alerts
    FROM {{ source('posshell', 'fraud_alerts') }}
    GROUP BY DATE(created_at), category, severity
)

SELECT
    report_date,
    category,
    severity,
    alert_count,
    avg_risk_score,
    confirmed_fraud,
    false_positives,
    open_alerts,
    ROUND(confirmed_fraud::NUMERIC / NULLIF(alert_count, 0) * 100, 2) AS precision_rate,
    ROUND(false_positives::NUMERIC / NULLIF(alert_count, 0) * 100, 2) AS false_positive_rate,
    CURRENT_TIMESTAMP AS updated_at
FROM fraud_metrics
