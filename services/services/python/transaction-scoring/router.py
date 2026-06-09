import os
import hashlib
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

import httpx

router = APIRouter(prefix="/transaction-scoring", tags=["transaction-scoring"])

FRAUD_ENGINE_URL = os.getenv("FRAUD_ENGINE_URL", "http://localhost:8016/fraud")
SMART_ROUTING_URL = os.getenv("SMART_ROUTING_URL", "http://localhost:8000/smart-routing")


class TransactionScoreRequest(BaseModel):
    sender_id: str = Field(..., description="Sender account/agent ID")
    recipient_id: str = Field(..., description="Recipient account/agent ID")
    amount: float = Field(..., gt=0)
    currency: str = Field(default="NGN")
    transaction_type: str = Field(..., description="transfer|bill_payment|cash_in|cash_out|airtime|merchant")
    channel: str = Field(default="mobile", description="mobile|pos|ussd|web|api")
    recipient_bank_code: Optional[str] = None
    biller_code: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ScoreBreakdown(BaseModel):
    amount_score: float = Field(..., description="Score based on amount normality (0-100)")
    velocity_score: float = Field(..., description="Score based on transaction frequency (0-100)")
    counterparty_score: float = Field(..., description="Score based on counterparty history (0-100)")
    channel_score: float = Field(..., description="Score based on channel reliability (0-100)")
    time_score: float = Field(..., description="Score based on time-of-day patterns (0-100)")
    fraud_score: float = Field(..., description="Inverse fraud risk score (0-100, higher=safer)")
    gateway_score: float = Field(..., description="Gateway success probability (0-100)")


class TransactionScoreResponse(BaseModel):
    transaction_ref: str
    overall_score: float = Field(..., description="Composite success probability (0-100)")
    risk_level: str = Field(..., description="low|medium|high|critical")
    recommendation: str = Field(..., description="approve|review|decline")
    breakdown: ScoreBreakdown
    factors: List[str] = Field(default_factory=list, description="Human-readable factors")
    estimated_completion_seconds: Optional[int] = None
    scored_at: str


_sender_history: Dict[str, List[Dict[str, Any]]] = {}
_counterparty_history: Dict[str, int] = {}
_scoring_analytics: Dict[str, Any] = {
    "total_scored": 0,
    "total_approved": 0,
    "total_declined": 0,
    "total_review": 0,
    "score_sum": 0.0,
    "recent_decisions": [],
    "hourly_counts": {},
}

CHANNEL_RELIABILITY = {
    "pos": 95.0, "web": 92.0, "mobile": 90.0, "api": 93.0, "ussd": 85.0
}

COMPLETION_ESTIMATES = {
    "transfer": 30, "bill_payment": 15, "cash_in": 5,
    "cash_out": 10, "airtime": 5, "merchant": 8
}

AMOUNT_THRESHOLDS = {
    "NGN": {"low": 10_000, "medium": 100_000, "high": 1_000_000},
    "USD": {"low": 50, "medium": 500, "high": 5_000},
}


def _compute_amount_score(amount: float, currency: str, tx_type: str) -> tuple:
    thresholds = AMOUNT_THRESHOLDS.get(currency, AMOUNT_THRESHOLDS["NGN"])
    factors = []
    if amount <= thresholds["low"]:
        score = 98.0
    elif amount <= thresholds["medium"]:
        score = 85.0
        factors.append(f"Amount {amount:,.0f} {currency} is in medium range")
    elif amount <= thresholds["high"]:
        score = 65.0
        factors.append(f"Amount {amount:,.0f} {currency} is high - additional verification recommended")
    else:
        score = 40.0
        factors.append(f"Amount {amount:,.0f} {currency} exceeds high threshold - manual review likely")
    return score, factors


def _compute_velocity_score(sender_id: str) -> tuple:
    now = datetime.utcnow()
    history = _sender_history.get(sender_id, [])
    recent = [h for h in history if (now - h["time"]).total_seconds() < 3600]
    factors = []
    if len(recent) == 0:
        score = 95.0
    elif len(recent) < 5:
        score = 90.0
    elif len(recent) < 15:
        score = 70.0
        factors.append(f"{len(recent)} transactions in last hour - elevated velocity")
    else:
        score = 35.0
        factors.append(f"{len(recent)} transactions in last hour - velocity limit risk")
    return score, factors


def _compute_counterparty_score(sender_id: str, recipient_id: str) -> tuple:
    key = f"{sender_id}->{recipient_id}"
    count = _counterparty_history.get(key, 0)
    factors = []
    if count >= 5:
        score = 97.0
        factors.append("Trusted counterparty (5+ previous transactions)")
    elif count >= 1:
        score = 85.0
    else:
        score = 65.0
        factors.append("First-time counterparty - additional checks may apply")
    return score, factors


def _compute_time_score() -> tuple:
    hour = datetime.utcnow().hour
    factors = []
    if 6 <= hour <= 22:
        score = 95.0
    elif 22 < hour or hour < 2:
        score = 75.0
        factors.append("Late-night transaction - slightly elevated risk window")
    else:
        score = 80.0
    return score, factors


async def _get_fraud_score(request: TransactionScoreRequest) -> tuple:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(f"{FRAUD_ENGINE_URL}/check_transaction", json={
                "sender_id": request.sender_id,
                "amount": request.amount,
                "transaction_type": request.transaction_type,
            })
            if resp.status_code == 200:
                data = resp.json()
                risk = data.get("risk_score", 0.1)
                score = max(0, (1.0 - risk) * 100)
                factors = []
                if score < 50:
                    factors.append(f"Fraud engine flagged: risk_score={risk:.2f}")
                return score, factors
    except Exception:
        pass
    return 88.0, []


async def _get_gateway_score(request: TransactionScoreRequest) -> tuple:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(f"{SMART_ROUTING_URL}/predict", json={
                "amount": request.amount,
                "currency": request.currency,
                "destination_bank": request.recipient_bank_code or "default",
            })
            if resp.status_code == 200:
                data = resp.json()
                prob = data.get("success_probability", 0.92)
                return prob * 100, []
    except Exception:
        pass
    return 92.0, []


@router.post("/score", response_model=TransactionScoreResponse)
async def score_transaction(request: TransactionScoreRequest):
    ref = hashlib.sha256(
        f"{request.sender_id}{request.recipient_id}{request.amount}{time.time()}".encode()
    ).hexdigest()[:16]

    amount_score, amount_factors = _compute_amount_score(request.amount, request.currency, request.transaction_type)
    velocity_score, velocity_factors = _compute_velocity_score(request.sender_id)
    counterparty_score, cp_factors = _compute_counterparty_score(request.sender_id, request.recipient_id)
    channel_score = CHANNEL_RELIABILITY.get(request.channel, 85.0)
    time_score, time_factors = _compute_time_score()
    fraud_score, fraud_factors = await _get_fraud_score(request)
    gateway_score, gw_factors = await _get_gateway_score(request)

    weights = {
        "amount": 0.20, "velocity": 0.15, "counterparty": 0.10,
        "channel": 0.10, "time": 0.05, "fraud": 0.25, "gateway": 0.15
    }
    overall = (
        amount_score * weights["amount"]
        + velocity_score * weights["velocity"]
        + counterparty_score * weights["counterparty"]
        + channel_score * weights["channel"]
        + time_score * weights["time"]
        + fraud_score * weights["fraud"]
        + gateway_score * weights["gateway"]
    )

    if overall >= 80:
        risk_level, recommendation = "low", "approve"
    elif overall >= 60:
        risk_level, recommendation = "medium", "approve"
    elif overall >= 40:
        risk_level, recommendation = "high", "review"
    else:
        risk_level, recommendation = "critical", "decline"

    all_factors = amount_factors + velocity_factors + cp_factors + time_factors + fraud_factors + gw_factors

    _sender_history.setdefault(request.sender_id, []).append({
        "time": datetime.utcnow(), "amount": request.amount, "type": request.transaction_type
    })
    cp_key = f"{request.sender_id}->{request.recipient_id}"
    _counterparty_history[cp_key] = _counterparty_history.get(cp_key, 0) + 1

    _scoring_analytics["total_scored"] += 1
    _scoring_analytics["score_sum"] += overall
    if recommendation == "approve":
        _scoring_analytics["total_approved"] += 1
    elif recommendation == "decline":
        _scoring_analytics["total_declined"] += 1
    elif recommendation == "review":
        _scoring_analytics["total_review"] += 1
    hour_key = datetime.utcnow().strftime("%Y-%m-%d-%H")
    _scoring_analytics["hourly_counts"][hour_key] = _scoring_analytics["hourly_counts"].get(hour_key, 0) + 1
    _scoring_analytics["recent_decisions"].append({
        "ref": ref, "score": round(overall, 1), "decision": recommendation,
        "risk": risk_level, "amount": request.amount, "at": datetime.utcnow().isoformat(),
    })
    if len(_scoring_analytics["recent_decisions"]) > 100:
        _scoring_analytics["recent_decisions"] = _scoring_analytics["recent_decisions"][-100:]

    return TransactionScoreResponse(
        transaction_ref=ref,
        overall_score=round(overall, 1),
        risk_level=risk_level,
        recommendation=recommendation,
        breakdown=ScoreBreakdown(
            amount_score=round(amount_score, 1),
            velocity_score=round(velocity_score, 1),
            counterparty_score=round(counterparty_score, 1),
            channel_score=round(channel_score, 1),
            time_score=round(time_score, 1),
            fraud_score=round(fraud_score, 1),
            gateway_score=round(gateway_score, 1),
        ),
        factors=all_factors,
        estimated_completion_seconds=COMPLETION_ESTIMATES.get(request.transaction_type, 30),
        scored_at=datetime.utcnow().isoformat(),
    )


@router.get("/history/{sender_id}")
async def get_sender_score_history(sender_id: str):
    history = _sender_history.get(sender_id, [])
    return {
        "sender_id": sender_id,
        "transaction_count_1h": len([h for h in history if (datetime.utcnow() - h["time"]).total_seconds() < 3600]),
        "transaction_count_24h": len([h for h in history if (datetime.utcnow() - h["time"]).total_seconds() < 86400]),
        "total_transactions": len(history),
    }


@router.get("/analytics")
async def get_scoring_analytics():
    total = _scoring_analytics["total_scored"]
    avg_score = round(_scoring_analytics["score_sum"] / max(total, 1), 1)
    approval_rate = round(_scoring_analytics["total_approved"] / max(total, 1) * 100, 1)
    decline_rate = round(_scoring_analytics["total_declined"] / max(total, 1) * 100, 1)
    return {
        "total_scored": total,
        "total_approved": _scoring_analytics["total_approved"],
        "total_declined": _scoring_analytics["total_declined"],
        "total_review": _scoring_analytics["total_review"],
        "avg_score": avg_score,
        "approval_rate_pct": approval_rate,
        "decline_rate_pct": decline_rate,
        "hourly_counts": _scoring_analytics["hourly_counts"],
        "recent_decisions": _scoring_analytics["recent_decisions"][-20:],
    }


@router.get("/thresholds")
async def get_scoring_thresholds():
    return {
        "amount_thresholds": AMOUNT_THRESHOLDS,
        "channel_reliability": CHANNEL_RELIABILITY,
        "completion_estimates": COMPLETION_ESTIMATES,
        "weights": {
            "amount": 0.20, "velocity": 0.15, "counterparty": 0.10,
            "channel": 0.10, "time": 0.05, "fraud": 0.25, "gateway": 0.15
        },
    }
