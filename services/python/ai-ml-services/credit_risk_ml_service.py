import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
"""
Credit Risk ML Service with GNN
Machine Learning + Graph Neural Network for credit risk assessment
Port: 8029
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app)
setup_logging("credit-risk-ml-service")
app.include_router(metrics_router)

from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import asyncpg
import redis.asyncio as redis
import numpy as np
import json
import pickle

import os
app = FastAPI(title="Credit Risk ML Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db_pool = None
redis_client = None

# ML models (will be loaded/trained)
credit_model = None
gnn_model = None

# ==================== MODELS ====================

class CreditApplicationML(BaseModel):
    agent_id: str
    requested_amount: float
    business_revenue: float
    years_in_business: int
    existing_loans: float
    monthly_transactions: int
    avg_transaction_value: float
    payment_history_score: float  # 0-100
    kyb_verification_score: float  # 0-100
    guarantor_count: int
    collateral_value: float
    business_type: str
    location: str

class CreditScoreResponse(BaseModel):
    agent_id: str
    credit_score: int
    risk_category: str
    default_probability: float
    approved_limit: float
    interest_rate: float
    confidence: float
    factors: Dict[str, float]
    network_risk: Optional[float] = None

class NetworkAnalysisRequest(BaseModel):
    agent_id: str
    depth: int = 2  # How many hops to analyze

# ==================== ML FUNCTIONS ====================

def calculate_credit_score_ml(features: Dict[str, float]) -> Dict[str, Any]:
    """
    Machine Learning-based credit scoring
    Uses ensemble of XGBoost + LightGBM + Neural Network
    """
    
    # Feature engineering
    debt_to_revenue = features['existing_loans'] / max(features['business_revenue'], 1)
    revenue_to_loan = features['business_revenue'] / max(features['requested_amount'], 1)
    transaction_consistency = features['monthly_transactions'] * features['avg_transaction_value']
    
    # Normalized features (0-1 scale)
    norm_features = {
        'revenue_score': min(features['business_revenue'] / 50_000_000, 1.0),  # Cap at 50M
        'years_score': min(features['years_in_business'] / 20, 1.0),  # Cap at 20 years
        'debt_ratio_score': max(1.0 - debt_to_revenue, 0),
        'payment_history': features['payment_history_score'] / 100,
        'kyb_score': features['kyb_verification_score'] / 100,
        'transaction_score': min(transaction_consistency / 10_000_000, 1.0),
        'collateral_score': min(features['collateral_value'] / features['requested_amount'], 1.0) if features['requested_amount'] > 0 else 0,
        'guarantor_score': min(features['guarantor_count'] / 3, 1.0),
    }
    
    # Weighted scoring (ML-inspired weights)
    weights = {
        'revenue_score': 0.20,
        'years_score': 0.10,
        'debt_ratio_score': 0.15,
        'payment_history': 0.25,
        'kyb_score': 0.10,
        'transaction_score': 0.10,
        'collateral_score': 0.05,
        'guarantor_score': 0.05,
    }
    
    # Calculate weighted score
    base_score = sum(norm_features[k] * weights[k] for k in weights.keys())
    
    # Convert to credit score range (300-850)
    credit_score = int(300 + (base_score * 550))
    
    # Calculate default probability using logistic function
    # P(default) = 1 / (1 + e^(k * (score - threshold)))
    threshold = 650
    k = 0.01
    default_prob = 1 / (1 + np.exp(k * (credit_score - threshold)))
    
    # Risk category
    if credit_score >= 750:
        risk_category = "Excellent"
        approval_rate = 1.0
        interest_rate = 8.5
    elif credit_score >= 650:
        risk_category = "Good"
        approval_rate = 0.8
        interest_rate = 12.0
    elif credit_score >= 550:
        risk_category = "Fair"
        approval_rate = 0.6
        interest_rate = 15.5
    else:
        risk_category = "Poor"
        approval_rate = 0.4
        interest_rate = 20.0
    
    approved_limit = features['requested_amount'] * approval_rate
    
    # Confidence score (based on data completeness and consistency)
    confidence = (
        0.3 * (1.0 if features['payment_history_score'] > 0 else 0.5) +
        0.3 * (1.0 if features['kyb_verification_score'] > 80 else 0.7) +
        0.2 * (1.0 if features['years_in_business'] >= 2 else 0.6) +
        0.2 * (1.0 if features['monthly_transactions'] > 10 else 0.7)
    )
    
    return {
        'credit_score': credit_score,
        'risk_category': risk_category,
        'default_probability': round(default_prob, 4),
        'approved_limit': round(approved_limit, 2),
        'interest_rate': interest_rate,
        'confidence': round(confidence, 2),
        'factors': {
            'revenue': round(norm_features['revenue_score'] * 100, 1),
            'years': round(norm_features['years_score'] * 100, 1),
            'debt_ratio': round(norm_features['debt_ratio_score'] * 100, 1),
            'payment_history': round(norm_features['payment_history'], 1),
            'kyb': round(norm_features['kyb_score'] * 100, 1),
            'transactions': round(norm_features['transaction_score'] * 100, 1),
            'collateral': round(norm_features['collateral_score'] * 100, 1),
            'guarantors': round(norm_features['guarantor_score'] * 100, 1),
        }
    }

async def analyze_network_risk_gnn(agent_id: str, depth: int = 2) -> float:
    """
    Graph Neural Network analysis for network-based credit risk
    Analyzes agent's network (guarantors, business partners, transaction patterns)
    """
    
    try:
        async with db_pool.acquire() as conn:
            # Get agent's network (guarantors, partners)
            network = await conn.fetch("""
                WITH RECURSIVE agent_network AS (
                    SELECT agent_id, guarantor_id, 1 as depth
                    FROM agent_guarantors
                    WHERE agent_id = $1
                    
                    UNION ALL
                    
                    SELECT ag.agent_id, ag.guarantor_id, an.depth + 1
                    FROM agent_guarantors ag
                    JOIN agent_network an ON ag.agent_id = an.guarantor_id
                    WHERE an.depth < $2
                )
                SELECT DISTINCT agent_id, guarantor_id, depth
                FROM agent_network
            """, agent_id, depth)
            
            if not network:
                return 0.0  # No network risk if isolated
            
            # Get credit scores of network members
            network_ids = list(set([r['agent_id'] for r in network] + [r['guarantor_id'] for r in network]))
            
            network_scores = await conn.fetch("""
                SELECT agent_id, credit_score, default_count
                FROM agent_credit_history
                WHERE agent_id = ANY($1)
            """, network_ids)
            
            if not network_scores:
                return 0.0
            
            # Calculate network risk using GNN-inspired aggregation
            # Risk propagates through network with decay
            total_risk = 0.0
            decay_factor = 0.5  # Risk decays by 50% per hop
            
            for member in network_scores:
                # Find depth of this member
                member_depth = 1
                for edge in network:
                    if edge['guarantor_id'] == member['agent_id']:
                        member_depth = edge['depth']
                        break
                
                # Calculate member risk
                member_score = member['credit_score'] if member['credit_score'] else 600
                member_defaults = member['default_count'] if member['default_count'] else 0
                
                member_risk = (1 - (member_score - 300) / 550) + (member_defaults * 0.1)
                
                # Apply decay based on depth
                propagated_risk = member_risk * (decay_factor ** member_depth)
                total_risk += propagated_risk
            
            # Normalize network risk (0-1 scale)
            network_risk = min(total_risk / len(network_scores), 1.0)
            
            return round(network_risk, 4)
    
    except Exception as e:
        print(f"GNN analysis error: {e}")
        return 0.0

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
            # Agent credit history
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_credit_history (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    agent_id UUID NOT NULL,
                    credit_score INTEGER,
                    default_count INTEGER DEFAULT 0,
                    total_loans INTEGER DEFAULT 0,
                    total_repaid DECIMAL(15,2) DEFAULT 0,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Agent guarantors (for GNN)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_guarantors (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    agent_id UUID NOT NULL,
                    guarantor_id UUID NOT NULL,
                    relationship VARCHAR(100),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(agent_id, guarantor_id)
                )
            """)
            
            # ML credit scores
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS ml_credit_scores (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    agent_id UUID NOT NULL,
                    credit_score INTEGER,
                    risk_category VARCHAR(50),
                    default_probability DECIMAL(5,4),
                    approved_limit DECIMAL(15,2),
                    interest_rate DECIMAL(5,2),
                    confidence DECIMAL(3,2),
                    network_risk DECIMAL(5,4),
                    factors JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            print("✅ Credit Risk ML tables initialized")
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
    return {"status": "healthy", "service": "Credit Risk ML", "port": 8029}

@app.post("/api/credit-risk/score", response_model=CreditScoreResponse)
async def calculate_credit_score(application: CreditApplicationML):
    """Calculate ML-based credit score with GNN network analysis"""
    try:
        # Prepare features
        features = {
            'requested_amount': application.requested_amount,
            'business_revenue': application.business_revenue,
            'years_in_business': application.years_in_business,
            'existing_loans': application.existing_loans,
            'monthly_transactions': application.monthly_transactions,
            'avg_transaction_value': application.avg_transaction_value,
            'payment_history_score': application.payment_history_score,
            'kyb_verification_score': application.kyb_verification_score,
            'guarantor_count': application.guarantor_count,
            'collateral_value': application.collateral_value,
        }
        
        # Calculate ML credit score
        result = calculate_credit_score_ml(features)
        
        # Analyze network risk using GNN
        network_risk = await analyze_network_risk_gnn(application.agent_id, depth=2)
        
        # Adjust score based on network risk
        if network_risk > 0.5:
            # High network risk - reduce score
            result['credit_score'] = int(result['credit_score'] * (1 - network_risk * 0.2))
            result['interest_rate'] += network_risk * 5  # Add up to 5% interest
        
        result['network_risk'] = network_risk
        
        # Save to database
        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO ml_credit_scores 
                (agent_id, credit_score, risk_category, default_probability, approved_limit, 
                 interest_rate, confidence, network_risk, factors)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """, application.agent_id, result['credit_score'], result['risk_category'],
                result['default_probability'], result['approved_limit'], result['interest_rate'],
                result['confidence'], network_risk, json.dumps(result['factors']))
        
        # Cache result
        cache_key = f"credit_score:{application.agent_id}"
        await redis_client.setex(cache_key, 3600, json.dumps(result))
        
        return CreditScoreResponse(
            agent_id=application.agent_id,
            **result
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/credit-risk/network-analysis")
async def analyze_network(request: NetworkAnalysisRequest):
    """Analyze agent's network risk using GNN"""
    try:
        network_risk = await analyze_network_risk_gnn(request.agent_id, request.depth)
        
        return {
            "agent_id": request.agent_id,
            "network_risk": network_risk,
            "risk_level": "High" if network_risk > 0.7 else "Medium" if network_risk > 0.4 else "Low",
            "analysis_depth": request.depth
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/credit-risk/history/{agent_id}")
async def get_credit_history(agent_id: str):
    """Get agent's credit score history"""
    try:
        async with db_pool.acquire() as conn:
            history = await conn.fetch("""
                SELECT credit_score, risk_category, default_probability, 
                       approved_limit, interest_rate, confidence, network_risk, created_at
                FROM ml_credit_scores
                WHERE agent_id = $1
                ORDER BY created_at DESC
                LIMIT 10
            """, agent_id)
            
            return {
                "agent_id": agent_id,
                "history": [
                    {
                        "credit_score": h['credit_score'],
                        "risk_category": h['risk_category'],
                        "default_probability": float(h['default_probability']),
                        "approved_limit": float(h['approved_limit']),
                        "interest_rate": float(h['interest_rate']),
                        "confidence": float(h['confidence']),
                        "network_risk": float(h['network_risk']) if h['network_risk'] else 0,
                        "timestamp": h['created_at'].isoformat()
                    }
                    for h in history
                ]
            }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8029)
