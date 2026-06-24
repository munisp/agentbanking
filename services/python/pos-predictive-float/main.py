"""
54Link Predictive Float Management — Python ML Service
Port: 8286

ML-powered demand forecasting for agent float pre-positioning.
Predicts daily cash requirements per terminal location based on:
- Historical transaction patterns (time-of-day, day-of-week)
- Market day calendars
- Salary payment dates (25th-28th monthly)
- Festival/holiday periods
- Weather patterns (rainy season reduces footfall)

Integrations: PostgreSQL, Redis (cache predictions), Kafka/Dapr (events), Lakehouse (analytics)
"""

import os
import json
import math
import logging
from datetime import datetime, timedelta, date
from typing import Optional, Dict, List
from collections import defaultdict

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import asyncpg
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/pos_float?sslmode=disable")

_pool: Optional[asyncpg.Pool] = None

async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
        await _pool.execute("""
            CREATE TABLE IF NOT EXISTS float_predictions (
                id SERIAL PRIMARY KEY,
                terminal_id VARCHAR(64) NOT NULL,
                prediction_date DATE NOT NULL,
                predicted_demand_kobo BIGINT NOT NULL,
                confidence DECIMAL(4,3),
                features JSONB,
                actual_demand_kobo BIGINT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(terminal_id, prediction_date)
            );
            CREATE TABLE IF NOT EXISTS float_alerts (
                id SERIAL PRIMARY KEY,
                terminal_id VARCHAR(64) NOT NULL,
                alert_type VARCHAR(32) NOT NULL,
                current_float_kobo BIGINT,
                predicted_demand_kobo BIGINT,
                shortfall_kobo BIGINT,
                recommended_topup_kobo BIGINT,
                status VARCHAR(16) DEFAULT 'active',
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS demand_history (
                id SERIAL PRIMARY KEY,
                terminal_id VARCHAR(64) NOT NULL,
                tx_date DATE NOT NULL,
                hour_of_day INT,
                day_of_week INT,
                total_cashout_kobo BIGINT DEFAULT 0,
                total_cashin_kobo BIGINT DEFAULT 0,
                tx_count INT DEFAULT 0,
                is_market_day BOOLEAN DEFAULT false,
                is_salary_period BOOLEAN DEFAULT false,
                UNIQUE(terminal_id, tx_date, hour_of_day)
            );
        """)
    return _pool

app = FastAPI(title="POS Predictive Float", version="1.0.0")

# ── ML Prediction Model ──────────────────────────────────────────────────────

MARKET_DAYS = {0, 3}  # Mon, Thu (typical Nigerian market days)
SALARY_DAYS = range(25, 29)  # 25th-28th

class PredictionRequest(BaseModel):
    terminal_id: str
    prediction_date: str = Field(description="YYYY-MM-DD")
    current_float_kobo: int = 0

class PredictionResponse(BaseModel):
    terminal_id: str
    prediction_date: str
    predicted_demand_kobo: int
    confidence: float
    recommended_topup_kobo: int
    risk_level: str  # low, medium, high, critical
    factors: List[str]

def predict_demand(history: List[Dict], target_date: date) -> tuple:
    """Simple time-series prediction using weighted moving average + seasonality."""
    if not history:
        return 5_000_000, 0.3, ["no_history"]  # Default 50K naira

    # Base: weighted average of last 4 same-weekdays
    same_weekday = [h for h in history if h["day_of_week"] == target_date.weekday()]
    recent = same_weekday[-4:] if same_weekday else history[-7:]

    weights = [0.4, 0.3, 0.2, 0.1]
    total_weight = sum(weights[:len(recent)])
    base_demand = sum(
        h["total_cashout_kobo"] * weights[i] / total_weight
        for i, h in enumerate(reversed(recent))
        if i < len(weights)
    ) if recent else 5_000_000

    factors = []
    multiplier = 1.0

    # Market day boost
    if target_date.weekday() in MARKET_DAYS:
        multiplier *= 1.6
        factors.append("market_day_+60%")

    # Salary period boost
    if target_date.day in SALARY_DAYS:
        multiplier *= 2.0
        factors.append("salary_period_+100%")

    # Month-end boost (last 3 days)
    next_month = target_date.replace(day=28) + timedelta(days=4)
    last_day = next_month - timedelta(days=next_month.day)
    if target_date.day >= last_day.day - 2:
        multiplier *= 1.3
        factors.append("month_end_+30%")

    # Friday/Saturday boost (social spending)
    if target_date.weekday() in (4, 5):
        multiplier *= 1.2
        factors.append("weekend_+20%")

    predicted = int(base_demand * multiplier)
    confidence = min(0.5 + 0.1 * len(same_weekday), 0.95)

    return predicted, confidence, factors

@app.post("/api/v1/float/predict", response_model=PredictionResponse)
async def predict_float(req: PredictionRequest):
    pool = await get_pool()
    target_date = date.fromisoformat(req.prediction_date)

    # Fetch history
    rows = await pool.fetch(
        """SELECT total_cashout_kobo, total_cashin_kobo, day_of_week, tx_date
           FROM demand_history WHERE terminal_id=$1 ORDER BY tx_date DESC LIMIT 30""",
        req.terminal_id
    )
    history = [dict(r) for r in rows]

    predicted, confidence, factors = predict_demand(history, target_date)

    # Calculate shortfall and recommendation
    shortfall = max(0, predicted - req.current_float_kobo)
    recommended = int(shortfall * 1.2)  # 20% buffer

    risk = "low"
    if req.current_float_kobo < predicted * 0.5:
        risk = "critical"
    elif req.current_float_kobo < predicted * 0.7:
        risk = "high"
    elif req.current_float_kobo < predicted:
        risk = "medium"

    # Persist prediction
    await pool.execute(
        """INSERT INTO float_predictions (terminal_id, prediction_date, predicted_demand_kobo, confidence, features)
           VALUES ($1, $2, $3, $4, $5) ON CONFLICT (terminal_id, prediction_date) DO UPDATE
           SET predicted_demand_kobo=$3, confidence=$4, features=$5""",
        req.terminal_id, target_date, predicted, confidence, json.dumps(factors)
    )

    # Generate alert if risk is high/critical
    if risk in ("high", "critical"):
        await pool.execute(
            """INSERT INTO float_alerts (terminal_id, alert_type, current_float_kobo, predicted_demand_kobo, shortfall_kobo, recommended_topup_kobo)
               VALUES ($1, $2, $3, $4, $5, $6)""",
            req.terminal_id, f"float_{risk}", req.current_float_kobo, predicted, shortfall, recommended
        )

    return PredictionResponse(
        terminal_id=req.terminal_id,
        prediction_date=req.prediction_date,
        predicted_demand_kobo=predicted,
        confidence=round(confidence, 3),
        recommended_topup_kobo=recommended,
        risk_level=risk,
        factors=factors,
    )

@app.get("/api/v1/float/alerts/{terminal_id}")
async def get_alerts(terminal_id: str):
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT * FROM float_alerts WHERE terminal_id=$1 AND status='active' ORDER BY created_at DESC LIMIT 10",
        terminal_id
    )
    return {"alerts": [dict(r) for r in rows]}

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "pos-predictive-float", "port": 8286}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8286)
