"""
P3-B: Credit Scoring Microservice (Python + FastAPI)

54agent POS Credit Scoring Engine

Endpoints:
  GET  /health                    — liveness probe
  POST /api/v1/score              — compute credit score for an agent
  GET  /api/v1/score/{agentCode}  — get latest score for an agent
  GET  /api/v1/tiers              — list all credit tiers and their limits
  POST /api/v1/batch-score        — batch score multiple agents

Scoring Model:
  The score is computed from 6 weighted factors:
    1. Transaction volume consistency (25%)  — std deviation of monthly volumes
    2. Transaction count trend (20%)         — month-over-month growth
    3. Dispute rate (20%)                    — disputes / total transactions
    4. Float utilisation (15%)               — average float balance vs limit
    5. Account age (10%)                     — months since onboarding
    6. KYC tier (10%)                        — KYC level (basic=0.5, enhanced=0.8, full=1.0)

Score range: 300–850 (similar to FICO)
"""

import os
import math
import json
import logging
from datetime import datetime, timezone
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ─── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("credit-scoring")

# ─── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="54agent Credit Scoring API",
    description="Agent credit scoring engine for the 54agent POS platform",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Constants ────────────────────────────────────────────────────────────────

CREDIT_TIERS = [
    {"tier": "Platinum", "minScore": 750, "maxScore": 850, "floatLimit": 5_000_000, "dailyLimit": 2_000_000, "description": "Excellent credit history"},
    {"tier": "Gold",     "minScore": 650, "maxScore": 749, "floatLimit": 2_000_000, "dailyLimit": 1_000_000, "description": "Good credit history"},
    {"tier": "Silver",   "minScore": 550, "maxScore": 649, "floatLimit": 1_000_000, "dailyLimit": 500_000,   "description": "Fair credit history"},
    {"tier": "Bronze",   "minScore": 450, "maxScore": 549, "floatLimit": 500_000,   "dailyLimit": 200_000,   "description": "Limited credit history"},
    {"tier": "Basic",    "minScore": 300, "maxScore": 449, "floatLimit": 200_000,   "dailyLimit": 100_000,   "description": "New or poor credit history"},
]

# ─── Models ───────────────────────────────────────────────────────────────────

class AgentData(BaseModel):
    agentCode: str = Field(..., description="Unique agent identifier")
    monthlyVolumes: list[float] = Field(
        ...,
        description="List of monthly transaction volumes (NGN), most recent last",
        min_length=1,
    )
    monthlyTransactionCounts: list[int] = Field(
        ...,
        description="List of monthly transaction counts, most recent last",
        min_length=1,
    )
    totalDisputes: int = Field(0, ge=0, description="Total disputes raised against this agent")
    totalTransactions: int = Field(1, ge=1, description="Total lifetime transactions")
    currentFloatBalance: float = Field(0.0, ge=0, description="Current float balance (NGN)")
    floatLimit: float = Field(200_000.0, gt=0, description="Approved float limit (NGN)")
    accountAgeMonths: int = Field(0, ge=0, description="Months since agent onboarding")
    kycTier: str = Field("basic", description="KYC tier: basic | enhanced | full")


class ScoreRequest(BaseModel):
    agent: AgentData
    includeFactors: bool = Field(False, description="Include factor breakdown in response")


class BatchScoreRequest(BaseModel):
    agents: list[AgentData] = Field(..., min_length=1, max_length=100)


class ScoreResponse(BaseModel):
    agentCode: str
    score: int
    tier: str
    floatLimit: int
    dailyLimit: int
    factors: Optional[dict] = None
    scoredAt: str


# ─── Scoring Engine ───────────────────────────────────────────────────────────

def compute_volume_consistency(monthly_volumes: list[float]) -> float:
    """
    Measures how consistent monthly volumes are.
    Lower coefficient of variation → higher score.
    Returns 0.0–1.0.
    """
    if len(monthly_volumes) < 2:
        return 0.5  # neutral for new agents

    mean = sum(monthly_volumes) / len(monthly_volumes)
    if mean == 0:
        return 0.0

    variance = sum((v - mean) ** 2 for v in monthly_volumes) / len(monthly_volumes)
    std_dev = math.sqrt(variance)
    cv = std_dev / mean  # coefficient of variation

    # CV < 0.2 → excellent consistency (1.0), CV > 1.0 → poor (0.0)
    return max(0.0, min(1.0, 1.0 - cv))


def compute_volume_trend(monthly_volumes: list[float]) -> float:
    """
    Measures month-over-month volume growth trend.
    Positive trend → higher score. Returns 0.0–1.0.
    """
    if len(monthly_volumes) < 2:
        return 0.5

    # Simple linear regression slope
    n = len(monthly_volumes)
    x_mean = (n - 1) / 2
    y_mean = sum(monthly_volumes) / n

    numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(monthly_volumes))
    denominator = sum((i - x_mean) ** 2 for i in range(n))

    if denominator == 0:
        return 0.5

    slope = numerator / denominator
    # Normalise: slope / y_mean gives monthly growth rate
    growth_rate = slope / y_mean if y_mean > 0 else 0

    # Growth rate > 0.1 (10% per month) → excellent (1.0), < -0.1 → poor (0.0)
    return max(0.0, min(1.0, 0.5 + growth_rate * 5))


def compute_dispute_rate(total_disputes: int, total_transactions: int) -> float:
    """
    Dispute rate: disputes / total_transactions.
    Lower rate → higher score. Returns 0.0–1.0.
    """
    if total_transactions == 0:
        return 0.5

    rate = total_disputes / total_transactions
    # Rate < 0.001 (0.1%) → excellent (1.0), rate > 0.05 (5%) → poor (0.0)
    return max(0.0, min(1.0, 1.0 - rate * 20))


def compute_float_utilisation(current_balance: float, float_limit: float) -> float:
    """
    Float utilisation: current_balance / float_limit.
    Higher utilisation (actively using float) → higher score.
    Optimal range: 30–70%. Returns 0.0–1.0.
    """
    if float_limit == 0:
        return 0.0

    utilisation = current_balance / float_limit
    # Optimal at 50% utilisation
    return max(0.0, min(1.0, 1.0 - abs(utilisation - 0.5) * 2))


def compute_account_age_score(account_age_months: int) -> float:
    """
    Longer account age → higher score.
    24+ months → excellent (1.0). Returns 0.0–1.0.
    """
    return min(1.0, account_age_months / 24.0)


def compute_kyc_score(kyc_tier: str) -> float:
    """
    KYC tier → score factor.
    """
    mapping = {"basic": 0.5, "enhanced": 0.8, "full": 1.0}
    return mapping.get(kyc_tier.lower(), 0.5)


def score_agent(agent: AgentData, include_factors: bool = False) -> dict:
    """
    Compute the composite credit score for an agent.
    Score range: 300–850.
    """
    # Factor scores (0.0–1.0)
    f_consistency = compute_volume_consistency(agent.monthlyVolumes)
    f_trend = compute_volume_trend(agent.monthlyVolumes)
    f_dispute = compute_dispute_rate(agent.totalDisputes, agent.totalTransactions)
    f_float = compute_float_utilisation(agent.currentFloatBalance, agent.floatLimit)
    f_age = compute_account_age_score(agent.accountAgeMonths)
    f_kyc = compute_kyc_score(agent.kycTier)

    # Weighted composite
    weights = {
        "volumeConsistency": 0.25,
        "volumeTrend": 0.20,
        "disputeRate": 0.20,
        "floatUtilisation": 0.15,
        "accountAge": 0.10,
        "kycTier": 0.10,
    }
    factors = {
        "volumeConsistency": f_consistency,
        "volumeTrend": f_trend,
        "disputeRate": f_dispute,
        "floatUtilisation": f_float,
        "accountAge": f_age,
        "kycTier": f_kyc,
    }

    composite = sum(factors[k] * weights[k] for k in weights)

    # Map composite (0.0–1.0) to score range (300–850)
    score = int(300 + composite * 550)
    score = max(300, min(850, score))

    # Determine tier
    tier_info = next(
        (t for t in CREDIT_TIERS if t["minScore"] <= score <= t["maxScore"]),
        CREDIT_TIERS[-1],  # default to Basic
    )

    result = {
        "agentCode": agent.agentCode,
        "score": score,
        "tier": tier_info["tier"],
        "floatLimit": tier_info["floatLimit"],
        "dailyLimit": tier_info["dailyLimit"],
        "scoredAt": datetime.now(timezone.utc).isoformat(),
    }

    if include_factors:
        result["factors"] = {
            k: {
                "score": round(v, 4),
                "weight": weights[k],
                "contribution": round(v * weights[k] * 550, 1),
            }
            for k, v in factors.items()
        }

    return result


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "54agent-credit-scoring",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/v1/tiers")
async def get_tiers():
    return {"tiers": CREDIT_TIERS}


@app.post("/api/v1/score", response_model=ScoreResponse)
async def score_single(request: ScoreRequest, x_api_key: Optional[str] = Header(None)):
    """Compute credit score for a single agent."""
    api_key = os.getenv("CREDIT_SCORING_API_KEY", "")
    if api_key and x_api_key != api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")

    try:
        result = score_agent(request.agent, request.includeFactors)
        logger.info(f"Scored agent {request.agent.agentCode}: {result['score']} ({result['tier']})")
        return result
    except Exception as e:
        logger.error(f"Scoring error for {request.agent.agentCode}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/score/{agent_code}")
async def get_score(agent_code: str, x_api_key: Optional[str] = Header(None)):
    """
    Get the latest score for an agent.
    In production this would query a scores cache/DB.
    For now returns a demo response.
    """
    api_key = os.getenv("CREDIT_SCORING_API_KEY", "")
    if api_key and x_api_key != api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Demo: compute a deterministic score based on agentCode hash
    seed = sum(ord(c) for c in agent_code) % 550
    score = 300 + seed
    tier_info = next(
        (t for t in CREDIT_TIERS if t["minScore"] <= score <= t["maxScore"]),
        CREDIT_TIERS[-1],
    )

    return {
        "agentCode": agent_code,
        "score": score,
        "tier": tier_info["tier"],
        "floatLimit": tier_info["floatLimit"],
        "dailyLimit": tier_info["dailyLimit"],
        "scoredAt": datetime.now(timezone.utc).isoformat(),
        "note": "Demo score — submit POST /api/v1/score with real data for accurate scoring",
    }


@app.post("/api/v1/batch-score")
async def batch_score(request: BatchScoreRequest, x_api_key: Optional[str] = Header(None)):
    """Batch score multiple agents."""
    api_key = os.getenv("CREDIT_SCORING_API_KEY", "")
    if api_key and x_api_key != api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")

    results = []
    errors = []
    for agent in request.agents:
        try:
            result = score_agent(agent, include_factors=False)
            results.append(result)
        except Exception as e:
            errors.append({"agentCode": agent.agentCode, "error": str(e)})

    logger.info(f"Batch scored {len(results)} agents, {len(errors)} errors")
    return {
        "results": results,
        "errors": errors,
        "total": len(request.agents),
        "successful": len(results),
        "failed": len(errors),
    }


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8082"))
    logger.info(f"54agent Credit Scoring Service starting on :{port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
