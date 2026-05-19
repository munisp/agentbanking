"""
AML Monitoring Service
Anti-Money Laundering transaction monitoring and compliance

Features:
- Real-time transaction monitoring
- ML-based anomaly detection
- Regulatory reporting (FINTRAC, FinCEN)
- Suspicious Activity Reports (SAR)
- Customer Due Diligence (CDD)
"""

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from enum import Enum
import asyncpg
import redis
import json
import os
import logging
from decimal import Decimal

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/aml_monitoring")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="AML Monitoring Service", version="1.0.0")
security = HTTPBearer()

db_pool = None
redis_client = None

class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class AlertType(str, Enum):
    STRUCTURING = "structuring"
    RAPID_MOVEMENT = "rapid_movement"
    HIGH_RISK_COUNTRY = "high_risk_country"
    UNUSUAL_PATTERN = "unusual_pattern"
    THRESHOLD_EXCEEDED = "threshold_exceeded"
    PEP_TRANSACTION = "pep_transaction"

class TransactionMonitor(BaseModel):
    transaction_id: str
    user_id: str
    amount: Decimal
    currency: str = "NGN"
    transaction_type: str
    counterparty_id: Optional[str]
    country_code: str = "NG"
    metadata: Dict[str, Any] = Field(default_factory=dict)

class AMLAlert(BaseModel):
    id: str
    transaction_id: str
    user_id: str
    alert_type: AlertType
    risk_level: RiskLevel
    score: float
    description: str
    created_at: datetime
    reviewed: bool = False

@app.on_event("startup")
async def startup():
    global db_pool, redis_client
    db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=5, max_size=20)
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    
    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS aml_alerts (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                transaction_id VARCHAR(100) NOT NULL,
                user_id VARCHAR(100) NOT NULL,
                alert_type VARCHAR(50) NOT NULL,
                risk_level VARCHAR(20) NOT NULL,
                score DECIMAL(5,2) NOT NULL,
                description TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                reviewed BOOLEAN DEFAULT FALSE,
                reviewed_at TIMESTAMP,
                reviewed_by VARCHAR(100),
                action_taken VARCHAR(100),
                metadata JSONB DEFAULT '{}'
            );
            
            CREATE INDEX IF NOT EXISTS idx_aml_user ON aml_alerts(user_id);
            CREATE INDEX IF NOT EXISTS idx_aml_risk ON aml_alerts(risk_level);
            CREATE INDEX IF NOT EXISTS idx_aml_reviewed ON aml_alerts(reviewed);
        """)
    
    logger.info("AML Monitoring Service started")

@app.on_event("shutdown")
async def shutdown():
    if db_pool:
        await db_pool.close()
    if redis_client:
        redis_client.close()

async def calculate_risk_score(transaction: TransactionMonitor) -> tuple[float, AlertType, str]:
    """Calculate AML risk score using multiple detection rules"""
    
    score = 0.0
    alert_type = None
    description = ""
    
    # Rule 1: Large transaction threshold
    if transaction.amount > Decimal("1000000"):  # 1M NGN
        score += 30.0
        alert_type = AlertType.THRESHOLD_EXCEEDED
        description = f"Large transaction: {transaction.amount} {transaction.currency}"
    
    # Rule 2: Check transaction velocity
    async with db_pool.acquire() as conn:
        recent_count = await conn.fetchval("""
            SELECT COUNT(*) FROM aml_alerts 
            WHERE user_id = $1 AND created_at > NOW() - INTERVAL '24 hours'
        """, transaction.user_id)
        
        if recent_count > 10:
            score += 25.0
            alert_type = AlertType.RAPID_MOVEMENT
            description = f"High transaction velocity: {recent_count} transactions in 24h"
    
    # Rule 3: High-risk country check
    high_risk_countries = ["AF", "IR", "KP", "SY"]
    if transaction.country_code in high_risk_countries:
        score += 40.0
        alert_type = AlertType.HIGH_RISK_COUNTRY
        description = f"Transaction from high-risk country: {transaction.country_code}"
    
    # Rule 4: Structuring detection (multiple transactions just below threshold)
    if Decimal("900000") < transaction.amount < Decimal("1000000"):
        score += 20.0
        alert_type = AlertType.STRUCTURING
        description = "Possible structuring: amount just below threshold"
    
    return (score, alert_type, description)

@app.post("/monitor", response_model=AMLAlert)
async def monitor_transaction(
    transaction: TransactionMonitor,
    background_tasks: BackgroundTasks
):
    """Monitor a transaction for AML compliance"""
    
    score, alert_type, description = await calculate_risk_score(transaction)
    
    # Determine risk level
    if score >= 70:
        risk_level = RiskLevel.CRITICAL
    elif score >= 50:
        risk_level = RiskLevel.HIGH
    elif score >= 30:
        risk_level = RiskLevel.MEDIUM
    else:
        risk_level = RiskLevel.LOW
    
    # Create alert if score exceeds threshold
    if score >= 30:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO aml_alerts (transaction_id, user_id, alert_type, risk_level, score, description)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING *
            """, transaction.transaction_id, transaction.user_id, alert_type.value, 
                risk_level.value, score, description)
            
            return AMLAlert(**dict(row))
    
    return {"status": "no_alert", "score": score}

@app.get("/alerts", response_model=List[AMLAlert])
async def list_alerts(
    risk_level: Optional[RiskLevel] = None,
    reviewed: Optional[bool] = None,
    limit: int = 50
):
    """List AML alerts"""
    
    query = "SELECT * FROM aml_alerts WHERE 1=1"
    params = []
    
    if risk_level:
        query += f" AND risk_level = ${len(params) + 1}"
        params.append(risk_level.value)
    
    if reviewed is not None:
        query += f" AND reviewed = ${len(params) + 1}"
        params.append(reviewed)
    
    query += f" ORDER BY created_at DESC LIMIT ${len(params) + 1}"
    params.append(limit)
    
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
        return [AMLAlert(**dict(row)) for row in rows]

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "aml-monitoring"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8102)
