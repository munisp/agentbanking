"""
Transaction Scoring - FastAPI microservice
Real-time transaction risk scoring: heuristic engine (amount/velocity/
counterparty/channel/time) composed with live fraud-engine and smart-routing
scores. Downstream failures fail loud (502) — no fabricated scores, no canned
"approve everything" stubs. Unknown entities return 404.
"""
import os
import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from router import (
    router as scoring_router,
    compute_score,
    TransactionScoreRequest,
    _sender_profiles,
    AMOUNT_THRESHOLDS,
    CHANNEL_RELIABILITY,
    COMPLETION_ESTIMATES,
    SCORING_WEIGHTS,
)

# --- Production: Graceful Shutdown ---
import signal
import sys
import atexit

_shutdown_handlers = []

def register_shutdown(handler):
    _shutdown_handlers.append(handler)

def _graceful_shutdown(signum, frame):
    sig_name = signal.Signals(signum).name if hasattr(signal, 'Signals') else str(signum)
    logging.info(f"[shutdown] Received {sig_name}, shutting down gracefully...")
    for handler in reversed(_shutdown_handlers):
        try:
            handler()
        except Exception as e:
            logging.warning(f"[shutdown] Handler error: {e}")
    logging.info("[shutdown] Cleanup complete, exiting")
    sys.exit(0)

signal.signal(signal.SIGTERM, _graceful_shutdown)
signal.signal(signal.SIGINT, _graceful_shutdown)
atexit.register(lambda: logging.info("[shutdown] atexit handler called"))


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Transaction Scoring", description="Real-time transaction risk scoring with heuristic + live downstream scores", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

app.include_router(scoring_router)

# --- Feedback persistence (Redis required; 503 when unavailable) ---

_redis_client = None
_redis_error: Optional[str] = None

def _get_redis():
    global _redis_client, _redis_error
    if _redis_client is not None:
        return _redis_client
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        _redis_error = "REDIS_URL is not configured"
        return None
    try:
        import redis  # type: ignore
        _redis_client = redis.from_url(redis_url, decode_responses=True)
        _redis_client.ping()
        return _redis_client
    except Exception as exc:
        _redis_error = f"Redis unavailable: {exc}"
        _redis_client = None
        return None

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "transaction-scoring", "version": "1.0.0", "timestamp": datetime.utcnow().isoformat()}

@app.post("/api/v1/scoring/evaluate")
async def evaluate_transaction(transaction_id: str, amount: float, sender_id: str, receiver_id: str, transaction_type: str):
    """Score a transaction with the real scoring engine (502 if downstreams fail)."""
    request = TransactionScoreRequest(
        sender_id=sender_id,
        recipient_id=receiver_id,
        amount=amount,
        transaction_type=transaction_type,
        metadata={"transaction_id": transaction_id},
    )
    result = await compute_score(request)
    return {
        "transaction_id": transaction_id,
        "transaction_ref": result.transaction_ref,
        "risk_score": round(100.0 - result.overall_score, 1),
        "risk_level": result.risk_level,
        "flags": result.factors,
        "recommendation": result.recommendation,
        "breakdown": result.breakdown.model_dump(),
        "scored_at": result.scored_at,
    }

@app.get("/api/v1/scoring/rules")
async def get_scoring_rules():
    """Get the active scoring rules and weights actually used by the engine."""
    rules = [
        {"name": "amount", "weight": SCORING_WEIGHTS["amount"], "config": AMOUNT_THRESHOLDS},
        {"name": "velocity", "weight": SCORING_WEIGHTS["velocity"], "config": {"window_seconds": 3600, "elevated": 5, "limit": 15}},
        {"name": "counterparty", "weight": SCORING_WEIGHTS["counterparty"], "config": {"trusted_threshold": 5}},
        {"name": "channel", "weight": SCORING_WEIGHTS["channel"], "config": CHANNEL_RELIABILITY},
        {"name": "time", "weight": SCORING_WEIGHTS["time"], "config": {"business_hours": "06:00-22:00 UTC"}},
        {"name": "fraud", "weight": SCORING_WEIGHTS["fraud"], "config": {"source": "fraud-engine", "fail_mode": "closed_502"}},
        {"name": "gateway", "weight": SCORING_WEIGHTS["gateway"], "config": {"source": "smart-routing", "fail_mode": "closed_502"}},
    ]
    return {"rules": rules, "total": len(rules), "model_version": "heuristic-1.0.0"}

@app.get("/api/v1/scoring/{entity_id}/profile")
async def get_risk_profile(entity_id: str):
    """Get entity risk profile built from real scoring decisions (404 if unknown)."""
    profile = _sender_profiles.get(entity_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"no risk profile for entity {entity_id}")
    return {
        "entity_id": entity_id,
        "risk_score": round(100.0 - profile["last_score"], 1) if profile["last_score"] is not None else None,
        "risk_level": profile["last_risk_level"],
        "total_transactions": profile["total_transactions"],
        "flagged_transactions": profile["flagged_transactions"],
        "last_updated": profile["last_updated"],
    }

@app.post("/api/v1/scoring/feedback")
async def submit_feedback(transaction_id: str, actual_outcome: str):
    """Persist feedback for model training (503 when no feedback store is configured)."""
    valid_outcomes = ["legitimate", "fraud", "suspicious", "false_positive"]
    if actual_outcome not in valid_outcomes:
        raise HTTPException(400, f"Must be one of: {valid_outcomes}")
    client = _get_redis()
    if client is None:
        raise HTTPException(
            status_code=503,
            detail=f"feedback store unavailable ({_redis_error}); feedback was NOT recorded",
        )
    record = {
        "transaction_id": transaction_id,
        "outcome": actual_outcome,
        "recorded_at": datetime.utcnow().isoformat(),
    }
    try:
        client.rpush("transaction-scoring:feedback", json.dumps(record))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"failed to persist feedback: {exc}")
    return {"transaction_id": transaction_id, "feedback_recorded": True, "outcome": actual_outcome}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
