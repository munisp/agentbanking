import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
"""
Anomaly Detection Service
Isolation Forest and statistical methods for detecting anomalies
Port: 8031
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app)
setup_logging("anomaly-detection-service")
app.include_router(metrics_router)

from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import asyncpg
import redis.asyncio as redis
import numpy as np
import json

import os
app = FastAPI(title="Anomaly Detection Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db_pool = None
redis_client = None

# ==================== MODELS ====================

class TransactionAnomaly(BaseModel):
    transaction_id: str
    agent_id: str
    amount: float
    transaction_type: str
    timestamp: datetime

class AnomalyResponse(BaseModel):
    is_anomaly: bool
    anomaly_score: float
    risk_level: str
    reasons: List[str]
    recommended_action: str

class BulkAnalysisRequest(BaseModel):
    agent_id: Optional[str] = None
    days: int = 7
    min_anomaly_score: float = 0.7

# ==================== ANOMALY DETECTION FUNCTIONS ====================

def calculate_z_score(value: float, mean: float, std: float) -> float:
    """Calculate Z-score for statistical anomaly detection"""
    if std == 0:
        return 0.0
    return abs((value - mean) / std)

def detect_transaction_anomaly(transaction: Dict[str, Any], historical_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Detect anomalies in transactions using Isolation Forest-inspired approach
    """
    if not historical_data:
        return {
            "is_anomaly": False,
            "anomaly_score": 0.0,
            "risk_level": "low",
            "reasons": [],
            "recommended_action": "monitor"
        }
    
    # Extract features
    amounts = [t['amount'] for t in historical_data]
    hours = [t['hour'] for t in historical_data]
    
    mean_amount = np.mean(amounts)
    std_amount = np.std(amounts)
    
    # Calculate anomaly scores for different features
    anomaly_scores = []
    reasons = []
    
    # 1. Amount anomaly (Z-score > 3 is unusual)
    amount_z = calculate_z_score(transaction['amount'], mean_amount, std_amount)
    if amount_z > 3:
        anomaly_scores.append(0.8)
        reasons.append(f"Transaction amount (${transaction['amount']:.2f}) is {amount_z:.1f} standard deviations from average (${mean_amount:.2f})")
    elif amount_z > 2:
        anomaly_scores.append(0.5)
        reasons.append(f"Transaction amount is moderately higher than usual")
    
    # 2. Time-based anomaly (unusual hour)
    transaction_hour = transaction['hour']
    hour_counts = {}
    for h in hours:
        hour_counts[h] = hour_counts.get(h, 0) + 1
    
    avg_hour_count = np.mean(list(hour_counts.values()))
    current_hour_count = hour_counts.get(transaction_hour, 0)
    
    if current_hour_count < avg_hour_count * 0.3:  # Less than 30% of average
        anomaly_scores.append(0.6)
        reasons.append(f"Transaction at unusual hour ({transaction_hour}:00)")
    
    # 3. Frequency anomaly (too many transactions in short time)
    recent_transactions = [t for t in historical_data if (datetime.now() - t['timestamp']).total_seconds() < 3600]
    if len(recent_transactions) > 10:
        anomaly_scores.append(0.7)
        reasons.append(f"High transaction frequency: {len(recent_transactions)} transactions in last hour")
    
    # 4. Pattern anomaly (unusual transaction type for this agent)
    type_counts = {}
    for t in historical_data:
        tx_type = t.get('transaction_type', 'unknown')
        type_counts[tx_type] = type_counts.get(tx_type, 0) + 1
    
    current_type = transaction.get('transaction_type', 'unknown')
    current_type_count = type_counts.get(current_type, 0)
    total_transactions = len(historical_data)
    
    if current_type_count / total_transactions < 0.05:  # Less than 5% of transactions
        anomaly_scores.append(0.5)
        reasons.append(f"Unusual transaction type: {current_type}")
    
    # 5. Velocity anomaly (rapid succession of large transactions)
    last_5_min = [t for t in historical_data if (datetime.now() - t['timestamp']).total_seconds() < 300]
    if len(last_5_min) >= 3 and transaction['amount'] > mean_amount:
        anomaly_scores.append(0.9)
        reasons.append(f"Rapid succession of transactions: {len(last_5_min)} in last 5 minutes")
    
    # Calculate overall anomaly score
    if anomaly_scores:
        overall_score = max(anomaly_scores)  # Take highest score
    else:
        overall_score = 0.0
    
    # Determine risk level and action
    if overall_score >= 0.8:
        risk_level = "critical"
        recommended_action = "block_and_review"
    elif overall_score >= 0.6:
        risk_level = "high"
        recommended_action = "flag_for_review"
    elif overall_score >= 0.4:
        risk_level = "medium"
        recommended_action = "monitor_closely"
    else:
        risk_level = "low"
        recommended_action = "allow"
    
    return {
        "is_anomaly": overall_score >= 0.6,
        "anomaly_score": round(overall_score, 2),
        "risk_level": risk_level,
        "reasons": reasons,
        "recommended_action": recommended_action
    }

def detect_order_anomaly(order: Dict[str, Any], agent_history: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Detect anomalies in purchase orders"""
    if not agent_history:
        return {
            "is_anomaly": False,
            "anomaly_score": 0.0,
            "risk_level": "low",
            "reasons": [],
            "recommended_action": "approve"
        }
    
    anomaly_scores = []
    reasons = []
    
    # 1. Order value anomaly
    order_values = [o['total_amount'] for o in agent_history]
    mean_value = np.mean(order_values)
    std_value = np.std(order_values)
    
    value_z = calculate_z_score(order['total_amount'], mean_value, std_value)
    if value_z > 3:
        anomaly_scores.append(0.8)
        reasons.append(f"Order value (${order['total_amount']:.2f}) is unusually high")
    
    # 2. Quantity anomaly
    if 'items' in order:
        total_quantity = sum(item.get('quantity', 0) for item in order['items'])
        historical_quantities = [sum(item.get('quantity', 0) for item in o.get('items', [])) for o in agent_history]
        mean_qty = np.mean(historical_quantities) if historical_quantities else 0
        
        if mean_qty > 0 and total_quantity > mean_qty * 3:
            anomaly_scores.append(0.7)
            reasons.append(f"Order quantity ({total_quantity}) is 3x higher than average")
    
    # 3. New manufacturer anomaly
    if 'manufacturer_id' in order:
        historical_manufacturers = set(o.get('manufacturer_id') for o in agent_history)
        if order['manufacturer_id'] not in historical_manufacturers:
            anomaly_scores.append(0.4)
            reasons.append("First order from this manufacturer")
    
    # Calculate overall score
    overall_score = max(anomaly_scores) if anomaly_scores else 0.0
    
    if overall_score >= 0.7:
        risk_level = "high"
        recommended_action = "manual_approval_required"
    elif overall_score >= 0.5:
        risk_level = "medium"
        recommended_action = "additional_verification"
    else:
        risk_level = "low"
        recommended_action = "auto_approve"
    
    return {
        "is_anomaly": overall_score >= 0.5,
        "anomaly_score": round(overall_score, 2),
        "risk_level": risk_level,
        "reasons": reasons,
        "recommended_action": recommended_action
    }

# ==================== DATABASE INITIALIZATION ====================

async def init_db():
    """Initialize database tables"""
    global db_pool, redis_client
    
    try:
        db_pool = await asyncpg.create_pool(
            host=os.getenv('DB_HOST', 'localhost'),
            port=5432,
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', ''),
            database="remittance",
            min_size=10,
            max_size=20
        )
        
        redis_client = await redis.from_url("redis://localhost:6379", decode_responses=True)
        
        async with db_pool.acquire() as conn:
            # Anomaly detections table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS anomaly_detections (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    entity_type VARCHAR(50) NOT NULL,
                    entity_id UUID NOT NULL,
                    agent_id UUID,
                    anomaly_score DECIMAL(3,2) NOT NULL,
                    risk_level VARCHAR(20) NOT NULL,
                    reasons JSONB,
                    recommended_action VARCHAR(50),
                    status VARCHAR(20) DEFAULT 'pending',
                    resolved_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_entity (entity_type, entity_id),
                    INDEX idx_agent (agent_id),
                    INDEX idx_status (status)
                )
            """)
            
            print("✅ Anomaly Detection tables initialized")
    except Exception as e:
        print(f"❌ Database initialization error: {e}")

@app.on_event("startup")
async def startup():
    await init_db()

@app.on_event("shutdown")
async def shutdown():
    if db_pool:
        await db_pool.close()
    if redis_client:
        await redis_client.close()

# ==================== API ENDPOINTS ====================

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "Anomaly Detection", "port": 8031}

@app.post("/api/anomaly/transaction", response_model=AnomalyResponse)
async def detect_transaction_anomaly_endpoint(transaction: TransactionAnomaly):
    """Detect anomalies in a transaction"""
    try:
        async with db_pool.acquire() as conn:
            # Get historical transactions for this agent
            historical = await conn.fetch("""
                SELECT amount, transaction_type, created_at,
                       EXTRACT(HOUR FROM created_at) as hour
                FROM tigerbeetle_transfers t
                JOIN tigerbeetle_accounts a ON t.debit_account_id = a.id
                WHERE a.user_id = $1
                AND created_at >= CURRENT_DATE - INTERVAL '30 days'
                ORDER BY created_at DESC
                LIMIT 100
            """, transaction.agent_id)
            
            # Prepare historical data
            historical_data = [
                {
                    'amount': float(row['amount']) / 100,  # Convert from kobo
                    'transaction_type': row['transaction_type'],
                    'timestamp': row['created_at'],
                    'hour': int(row['hour'])
                }
                for row in historical
            ]
            
            # Prepare current transaction
            current_tx = {
                'amount': transaction.amount,
                'transaction_type': transaction.transaction_type,
                'hour': transaction.timestamp.hour,
                'timestamp': transaction.timestamp
            }
            
            # Detect anomaly
            result = detect_transaction_anomaly(current_tx, historical_data)
            
            # Save anomaly if detected
            if result['is_anomaly']:
                await conn.execute("""
                    INSERT INTO anomaly_detections 
                    (entity_type, entity_id, agent_id, anomaly_score, risk_level, reasons, recommended_action)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                """, 'transaction', transaction.transaction_id, transaction.agent_id,
                    result['anomaly_score'], result['risk_level'], 
                    json.dumps(result['reasons']), result['recommended_action'])
            
            return AnomalyResponse(**result)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/anomaly/order")
async def detect_order_anomaly_endpoint(order_id: str, agent_id: str):
    """Detect anomalies in a purchase order"""
    try:
        async with db_pool.acquire() as conn:
            # Get current order
            order = await conn.fetchrow("""
                SELECT id, agent_id, manufacturer_id, total_amount, items
                FROM purchase_orders
                WHERE id = $1
            """, order_id)
            
            if not order:
                raise HTTPException(status_code=404, detail="Order not found")
            
            # Get historical orders
            historical = await conn.fetch("""
                SELECT total_amount, manufacturer_id, items
                FROM purchase_orders
                WHERE agent_id = $1 AND id != $2
                ORDER BY created_at DESC
                LIMIT 50
            """, agent_id, order_id)
            
            # Prepare data
            current_order = {
                'total_amount': float(order['total_amount']),
                'manufacturer_id': str(order['manufacturer_id']),
                'items': json.loads(order['items']) if order['items'] else []
            }
            
            historical_orders = [
                {
                    'total_amount': float(o['total_amount']),
                    'manufacturer_id': str(o['manufacturer_id']),
                    'items': json.loads(o['items']) if o['items'] else []
                }
                for o in historical
            ]
            
            # Detect anomaly
            result = detect_order_anomaly(current_order, historical_orders)
            
            # Save anomaly if detected
            if result['is_anomaly']:
                await conn.execute("""
                    INSERT INTO anomaly_detections 
                    (entity_type, entity_id, agent_id, anomaly_score, risk_level, reasons, recommended_action)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                """, 'order', order_id, agent_id,
                    result['anomaly_score'], result['risk_level'], 
                    json.dumps(result['reasons']), result['recommended_action'])
            
            return result
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/anomaly/bulk-analysis")
async def bulk_anomaly_analysis(request: BulkAnalysisRequest):
    """Analyze all recent transactions/orders for anomalies"""
    try:
        async with db_pool.acquire() as conn:
            query = """
                SELECT entity_type, entity_id, agent_id, anomaly_score, risk_level, reasons, created_at
                FROM anomaly_detections
                WHERE created_at >= CURRENT_DATE - INTERVAL '{} days'
                AND anomaly_score >= {}
            """.format(request.days, request.min_anomaly_score)
            
            if request.agent_id:
                query += f" AND agent_id = '{request.agent_id}'"
            
            query += " ORDER BY anomaly_score DESC, created_at DESC LIMIT 100"
            
            anomalies = await conn.fetch(query)
            
            return {
                "total_anomalies": len(anomalies),
                "anomalies": [
                    {
                        "entity_type": a['entity_type'],
                        "entity_id": str(a['entity_id']),
                        "agent_id": str(a['agent_id']),
                        "anomaly_score": float(a['anomaly_score']),
                        "risk_level": a['risk_level'],
                        "reasons": json.loads(a['reasons']) if a['reasons'] else [],
                        "detected_at": a['created_at'].isoformat()
                    }
                    for a in anomalies
                ]
            }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/anomaly/analytics")
async def get_anomaly_analytics():
    """Get platform-wide anomaly analytics"""
    try:
        async with db_pool.acquire() as conn:
            # Anomalies by risk level
            by_risk = await conn.fetch("""
                SELECT risk_level, COUNT(*) as count
                FROM anomaly_detections
                WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
                GROUP BY risk_level
            """)
            
            # Anomalies by entity type
            by_type = await conn.fetch("""
                SELECT entity_type, COUNT(*) as count
                FROM anomaly_detections
                WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
                GROUP BY entity_type
            """)
            
            # Total anomalies
            total = await conn.fetchval("""
                SELECT COUNT(*)
                FROM anomaly_detections
                WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
            """)
            
            return {
                "last_7_days": {
                    "total_anomalies": total or 0,
                    "by_risk_level": {r['risk_level']: r['count'] for r in by_risk},
                    "by_entity_type": {t['entity_type']: t['count'] for t in by_type}
                }
            }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8031)
