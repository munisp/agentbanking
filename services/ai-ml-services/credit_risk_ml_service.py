import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
"""
Credit Risk ML Service
Serves credit-risk scores from a versioned, trained model artifact.

Port: 8029

Scoring doctrine:
  - Scores are ONLY produced by a trained model artifact loaded from
    CREDIT_RISK_MODEL_PATH (joblib/pickle; dict artifact with keys
    {"model", "version", ...} or a bare estimator implementing predict_proba).
  - If no artifact is configured or it fails to load, /api/credit-risk/score
    answers HTTP 503 — no fabricated scores, no hardcoded formulas passed off
    as an ML ensemble.
  - The legacy hand-weighted heuristic is reachable ONLY when
    CREDIT_RISK_ML_SIMULATION_MODE=true AND the environment is non-production;
    enabling simulation in production hard-fails at startup.
  - Network risk is a deterministic graph-propagation heuristic computed from
    real guarantor/credit-history rows (not a GNN); DB failures fail loud (502).
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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

from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware

apply_middleware(app)
setup_logging("credit-risk-ml-service")
app.include_router(metrics_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db_pool = None
redis_client = None

# ---------------------------------------------------------------------------
# Model artifact loading (required for scoring)
# ---------------------------------------------------------------------------

ENVIRONMENT = os.getenv("ENVIRONMENT", os.getenv("ENV", "development")).lower()
IS_PRODUCTION = ENVIRONMENT in ("production", "prod")
SIMULATION_MODE = os.getenv("CREDIT_RISK_ML_SIMULATION_MODE", "").lower() == "true"

if SIMULATION_MODE and IS_PRODUCTION:
    raise RuntimeError(
        "CREDIT_RISK_ML_SIMULATION_MODE=true is forbidden in production: "
        "simulated credit scoring must never serve live traffic."
    )

MODEL_PATH = os.getenv("CREDIT_RISK_MODEL_PATH", "")
MODEL_VERSION = "none"
credit_model = None
_model_load_error: Optional[str] = None

# Canonical feature order expected by the trained artifact.
FEATURE_NAMES = [
    "requested_amount",
    "business_revenue",
    "years_in_business",
    "existing_loans",
    "monthly_transactions",
    "avg_transaction_value",
    "payment_history_score",
    "kyb_verification_score",
    "guarantor_count",
    "collateral_value",
]


def _load_model_artifact():
    """Load the trained credit-risk model artifact. Returns (model, version)."""
    global _model_load_error
    if not MODEL_PATH:
        _model_load_error = "CREDIT_RISK_MODEL_PATH is not configured"
        return None, "none"
    try:
        try:
            import joblib  # type: ignore
            artifact = joblib.load(MODEL_PATH)
        except ImportError:
            with open(MODEL_PATH, "rb") as fh:
                artifact = pickle.load(fh)
        if isinstance(artifact, dict):
            model = artifact.get("model")
            version = str(artifact.get("version", "unknown"))
        else:
            model = artifact
            version = "unknown"
        if model is None or not hasattr(model, "predict_proba"):
            _model_load_error = (
                "model artifact does not provide predict_proba; a calibrated "
                "probability estimator is required for credit scoring"
            )
            return None, "none"
        return model, version
    except Exception as exc:  # fail loud at request time, not silently
        _model_load_error = f"failed to load model artifact: {exc}"
        return None, "none"


def _model_available() -> bool:
    return credit_model is not None


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
    confidence: Optional[float] = None
    factors: Dict[str, float]
    network_risk: Optional[float] = None
    model_version: str = "none"
    scoring_method: str = "model"

class NetworkAnalysisRequest(BaseModel):
    agent_id: str
    depth: int = 2  # How many hops to analyze

# ==================== SCORING ====================

def _feature_vector(features: Dict[str, float]) -> List[float]:
    return [float(features[name]) for name in FEATURE_NAMES]


def _policy_for_score(credit_score: int) -> Dict[str, float]:
    """Deterministic pricing/limit policy given a model-derived score."""
    if credit_score >= 750:
        return {"risk_category": "Excellent", "approval_rate": 1.0, "interest_rate": 8.5}
    if credit_score >= 650:
        return {"risk_category": "Good", "approval_rate": 0.8, "interest_rate": 12.0}
    if credit_score >= 550:
        return {"risk_category": "Fair", "approval_rate": 0.6, "interest_rate": 15.5}
    return {"risk_category": "Poor", "approval_rate": 0.4, "interest_rate": 20.0}


def score_with_model(features: Dict[str, float]) -> Dict[str, Any]:
    """Score using the loaded trained artifact. Never called without a model."""
    vector = np.array([_feature_vector(features)])
    proba = credit_model.predict_proba(vector)[0]
    classes = list(getattr(credit_model, "classes_", [0, 1]))
    # Positive/default class: prefer an explicit 'default'/1 class label.
    if 1 in classes:
        default_idx = classes.index(1)
    elif "default" in classes:
        default_idx = classes.index("default")
    else:
        default_idx = len(classes) - 1
    default_prob = float(proba[default_idx])
    confidence = float(max(proba))

    # Map probability of default onto the 300-850 score band.
    credit_score = int(round(850 - default_prob * 550))
    policy = _policy_for_score(credit_score)

    return {
        "credit_score": credit_score,
        "risk_category": policy["risk_category"],
        "default_probability": round(default_prob, 4),
        "approved_limit": round(features["requested_amount"] * policy["approval_rate"], 2),
        "interest_rate": policy["interest_rate"],
        "confidence": round(confidence, 4),
        "factors": {},
        "scoring_method": "model",
        "model_version": MODEL_VERSION,
    }


def score_with_simulation(features: Dict[str, float]) -> Dict[str, Any]:
    """
    Legacy hand-weighted heuristic. SIMULATION ONLY — reachable exclusively
    with CREDIT_RISK_ML_SIMULATION_MODE=true in a non-production environment.
    """
    debt_to_revenue = features['existing_loans'] / max(features['business_revenue'], 1)
    transaction_consistency = features['monthly_transactions'] * features['avg_transaction_value']

    norm_features = {
        'revenue_score': min(features['business_revenue'] / 50_000_000, 1.0),
        'years_score': min(features['years_in_business'] / 20, 1.0),
        'debt_ratio_score': max(1.0 - debt_to_revenue, 0),
        'payment_history': features['payment_history_score'] / 100,
        'kyb_score': features['kyb_verification_score'] / 100,
        'transaction_score': min(transaction_consistency / 10_000_000, 1.0),
        'collateral_score': min(features['collateral_value'] / features['requested_amount'], 1.0) if features['requested_amount'] > 0 else 0,
        'guarantor_score': min(features['guarantor_count'] / 3, 1.0),
    }

    weights = {
        'revenue_score': 0.20, 'years_score': 0.10, 'debt_ratio_score': 0.15,
        'payment_history': 0.25, 'kyb_score': 0.10, 'transaction_score': 0.10,
        'collateral_score': 0.05, 'guarantor_score': 0.05,
    }
    base_score = sum(norm_features[k] * weights[k] for k in weights)
    credit_score = int(300 + (base_score * 550))
    default_prob = 1 / (1 + np.exp(0.01 * (credit_score - 650)))
    policy = _policy_for_score(credit_score)

    return {
        'credit_score': credit_score,
        'risk_category': policy["risk_category"],
        'default_probability': round(float(default_prob), 4),
        'approved_limit': round(features['requested_amount'] * policy["approval_rate"], 2),
        'interest_rate': policy["interest_rate"],
        'confidence': None,  # heuristic simulation has no calibrated confidence
        'factors': {k: round(v * 100, 1) for k, v in norm_features.items()},
        'scoring_method': 'heuristic_simulation',
        'model_version': 'simulation',
    }


async def analyze_network_risk(agent_id: str, depth: int = 2) -> float:
    """
    Deterministic graph-propagation heuristic over the agent's real guarantor
    network (agent_guarantors + agent_credit_history tables). Risk decays 50%
    per hop. This is NOT a neural network; no weights are learned.
    DB errors propagate — callers fail loud instead of silently scoring 0 risk.
    """
    async with db_pool.acquire() as conn:
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
            return 0.0  # genuinely isolated agent — no network risk

        network_ids = list(set([r['agent_id'] for r in network] + [r['guarantor_id'] for r in network]))

        network_scores = await conn.fetch("""
            SELECT agent_id, credit_score, default_count
            FROM agent_credit_history
            WHERE agent_id = ANY($1)
        """, network_ids)

        if not network_scores:
            return 0.0

        total_risk = 0.0
        decay_factor = 0.5

        for member in network_scores:
            member_depth = 1
            for edge in network:
                if edge['guarantor_id'] == member['agent_id']:
                    member_depth = edge['depth']
                    break

            member_score = member['credit_score'] if member['credit_score'] else 600
            member_defaults = member['default_count'] if member['default_count'] else 0
            member_risk = (1 - (member_score - 300) / 550) + (member_defaults * 0.1)
            total_risk += member_risk * (decay_factor ** member_depth)

        return round(min(total_risk / len(network_scores), 1.0), 4)

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

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS ml_credit_scores (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    agent_id UUID NOT NULL,
                    credit_score INTEGER,
                    risk_category VARCHAR(50),
                    default_probability DECIMAL(5,4),
                    approved_limit DECIMAL(15,2),
                    interest_rate DECIMAL(5,2),
                    confidence DECIMAL(5,4),
                    network_risk DECIMAL(5,4),
                    factors JSONB,
                    model_version VARCHAR(100),
                    scoring_method VARCHAR(50),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            print("✅ Credit Risk ML tables initialized")
    except Exception as e:
        print(f"❌ Database initialization error: {e}")

@app.on_event("startup")
async def startup():
    global credit_model, MODEL_VERSION
    credit_model, MODEL_VERSION = _load_model_artifact()
    if credit_model is None:
        print(f"⚠️  Credit-risk model unavailable: {_model_load_error}. "
              "Scoring endpoints will return 503 until a valid artifact is provided."
              + (" SIMULATION MODE ACTIVE (non-prod)." if SIMULATION_MODE else ""))
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
    return {
        "status": "healthy" if (_model_available() or SIMULATION_MODE) else "degraded",
        "service": "Credit Risk ML",
        "port": 8029,
        "model_loaded": _model_available(),
        "model_version": MODEL_VERSION,
        "model_error": None if _model_available() else _model_load_error,
        "simulation_mode": SIMULATION_MODE,
    }

@app.post("/api/credit-risk/score", response_model=CreditScoreResponse)
async def calculate_credit_score(application: CreditApplicationML):
    """Score a credit application with the trained model artifact (503 without one)."""
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

    if _model_available():
        try:
            result = score_with_model(features)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"model inference failed: {e}")
    elif SIMULATION_MODE:
        result = score_with_simulation(features)
    else:
        raise HTTPException(
            status_code=503,
            detail=f"Credit-risk model unavailable: {_model_load_error}. "
                   "Configure CREDIT_RISK_MODEL_PATH with a trained artifact.",
        )

    try:
        network_risk = await analyze_network_risk(application.agent_id, depth=2)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"network risk analysis failed: {e}")

    if network_risk > 0.5:
        result['credit_score'] = int(result['credit_score'] * (1 - network_risk * 0.2))
        result['interest_rate'] += network_risk * 5

    result['network_risk'] = network_risk

    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO ml_credit_scores
            (agent_id, credit_score, risk_category, default_probability, approved_limit,
             interest_rate, confidence, network_risk, factors, model_version, scoring_method)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        """, application.agent_id, result['credit_score'], result['risk_category'],
            result['default_probability'], result['approved_limit'], result['interest_rate'],
            result['confidence'], network_risk, json.dumps(result['factors']),
            result['model_version'], result['scoring_method'])

    if redis_client is not None:
        cache_key = f"credit_score:{application.agent_id}"
        await redis_client.setex(cache_key, 3600, json.dumps(result))

    return CreditScoreResponse(agent_id=application.agent_id, **result)

@app.post("/api/credit-risk/network-analysis")
async def analyze_network(request: NetworkAnalysisRequest):
    """Analyze agent network risk (deterministic graph propagation over real data)."""
    try:
        network_risk = await analyze_network_risk(request.agent_id, request.depth)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"network risk analysis failed: {e}")

    return {
        "agent_id": request.agent_id,
        "network_risk": network_risk,
        "risk_level": "High" if network_risk > 0.7 else "Medium" if network_risk > 0.4 else "Low",
        "analysis_depth": request.depth,
        "method": "graph_propagation_heuristic",
    }

@app.get("/api/credit-risk/history/{agent_id}")
async def get_credit_history(agent_id: str):
    """Get agent's credit score history"""
    try:
        async with db_pool.acquire() as conn:
            history = await conn.fetch("""
                SELECT credit_score, risk_category, default_probability,
                       approved_limit, interest_rate, confidence, network_risk,
                       model_version, scoring_method, created_at
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
                        "confidence": float(h['confidence']) if h['confidence'] is not None else None,
                        "network_risk": float(h['network_risk']) if h['network_risk'] else 0,
                        "model_version": h['model_version'],
                        "scoring_method": h['scoring_method'],
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
