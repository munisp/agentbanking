"""
Fraud ML Scoring Service — Python
High-accuracy fraud detection using ML models, anomaly detection,
velocity analysis, behavioral profiling, and device fingerprinting.
Serves as the ML brain for the 54agent Agency Banking Platform.
"""

import os
import time
import math
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional
from collections import defaultdict

import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# --- Production: Graceful Shutdown ---
import signal
import sys
import atexit
import logging

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


# ── Logging ───────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("fraud-ml-service")

# ── Models ────────────────────────────────────────────────────────────

class TransactionFeatures(BaseModel):
    """Input features for fraud scoring"""
    transaction_id: str
    user_id: str
    amount: float
    currency: str = "NGN"
    transaction_type: str  # "transfer", "withdrawal", "deposit", "bill_payment"
    channel: str  # "web", "mobile", "ussd", "api", "pos"
    sender_account: Optional[str] = None
    receiver_account: Optional[str] = None
    ip_address: Optional[str] = None
    device_id: Optional[str] = None
    user_agent: Optional[str] = None
    geo_latitude: Optional[float] = None
    geo_longitude: Optional[float] = None
    geo_country: Optional[str] = None
    geo_city: Optional[str] = None
    timestamp: Optional[int] = None  # unix ms
    session_age_seconds: Optional[int] = None
    kyc_level: Optional[int] = None
    account_age_days: Optional[int] = None
    is_new_recipient: Optional[bool] = None
    is_international: Optional[bool] = None

# fraud_score computation model
class FraudScore(BaseModel):
    """Output fraud assessment"""
    transaction_id: str
    overall_score: float = Field(ge=0.0, le=1.0)
    risk_level: str  # "low", "medium", "high", "critical"
    decision: str  # "approve", "review", "block"
    component_scores: dict
    risk_factors: list[str]
    recommendations: list[str]
    model_version: str
    eval_time_ms: float

class VelocityCheck(BaseModel):
    user_id: str
    amount: float
    transaction_type: str
    channel: str
    timestamp: Optional[int] = None

class VelocityResult(BaseModel):
    user_id: str
    is_anomalous: bool
    velocity_score: float
    details: dict
    limits_exceeded: list[str]

class BehaviorProfile(BaseModel):
    user_id: str
    typical_amount_mean: float
    typical_amount_std: float
    typical_channels: list[str]
    typical_hours: list[int]
    typical_recipients: int
    transaction_count_30d: int
    last_updated: str

class AnomalyDetectionRequest(BaseModel):
    user_id: str
    features: list[float]  # normalized feature vector

class AnomalyDetectionResult(BaseModel):
    user_id: str
    is_anomaly: bool
    anomaly_score: float
    isolation_score: float
    details: str

# ── In-Memory Stores ──────────────────────────────────────────────────

# User transaction history (in production, this would be Redis/DB)
user_tx_history: dict[str, list[dict]] = defaultdict(list)
user_profiles: dict[str, dict] = {}
device_fingerprints: dict[str, dict] = defaultdict(dict)
ip_reputation_cache: dict[str, float] = {}

# Velocity windows
velocity_windows: dict[str, list[dict]] = defaultdict(list)

# ── ML Models (Lightweight) ──────────────────────────────────────────

class IsolationForestLite:
    """Lightweight Isolation Forest for anomaly detection"""

    def __init__(self, n_trees: int = 100, sample_size: int = 256):
        self.n_trees = n_trees
        self.sample_size = sample_size
        self.trees: list[dict] = []
        self.trained = False

    def _build_tree(self, data: np.ndarray, depth: int = 0, max_depth: int = 10) -> dict:
        n_samples, n_features = data.shape
        if depth >= max_depth or n_samples <= 1:
            return {"type": "leaf", "size": n_samples}

        feature_idx = np.random.randint(0, n_features)
        feature_min = data[:, feature_idx].min()
        feature_max = data[:, feature_idx].max()

        if feature_min == feature_max:
            return {"type": "leaf", "size": n_samples}

        split_value = np.random.uniform(feature_min, feature_max)
        left_mask = data[:, feature_idx] < split_value
        right_mask = ~left_mask

        return {
            "type": "split",
            "feature": int(feature_idx),
            "threshold": float(split_value),
            "left": self._build_tree(data[left_mask], depth + 1, max_depth),
            "right": self._build_tree(data[right_mask], depth + 1, max_depth),
        }

    def fit(self, data: np.ndarray):
        self.trees = []
        n_samples = len(data)
        max_depth = int(math.ceil(math.log2(max(self.sample_size, 2))))

        for _ in range(self.n_trees):
            indices = np.random.choice(n_samples, min(self.sample_size, n_samples), replace=False)
            tree = self._build_tree(data[indices], max_depth=max_depth)
            self.trees.append(tree)

        self.trained = True

    def _path_length(self, x: np.ndarray, tree: dict, depth: int = 0) -> float:
        if tree["type"] == "leaf":
            n = tree["size"]
            if n <= 1:
                return float(depth)
            # Average path length for unsuccessful search in BST
            c = 2.0 * (math.log(n - 1) + 0.5772156649) - 2.0 * (n - 1) / n
            return float(depth) + c

        if x[tree["feature"]] < tree["threshold"]:
            return self._path_length(x, tree["left"], depth + 1)
        else:
            return self._path_length(x, tree["right"], depth + 1)

    def score(self, x: np.ndarray) -> float:
        if not self.trained or len(self.trees) == 0:
            return 0.5

        avg_path = np.mean([self._path_length(x, tree) for tree in self.trees])
        c = 2.0 * (math.log(self.sample_size - 1) + 0.5772156649) - 2.0 * (self.sample_size - 1) / self.sample_size
        anomaly_score = 2.0 ** (-avg_path / c) if c > 0 else 0.5
        return float(anomaly_score)


# Global model instance
isolation_forest = IsolationForestLite(n_trees=50, sample_size=128)

# Pre-train with synthetic normal data
np.random.seed(42)
normal_data = np.random.randn(1000, 8) * 0.3 + 0.5
normal_data = np.clip(normal_data, 0, 1)
isolation_forest.fit(normal_data)

# ── Scoring Functions ─────────────────────────────────────────────────

def compute_amount_score(amount: float, currency: str, user_id: str) -> float:
    """Score based on amount anomaly relative to user history"""
    profile = user_profiles.get(user_id)
    if not profile:
        # New user — higher risk for large amounts
        if amount > 500000:
            return 0.7
        elif amount > 100000:
            return 0.4
        return 0.1

    mean = profile.get("avg_amount", 50000)
    std = profile.get("std_amount", 25000)
    if std == 0:
        std = mean * 0.3

    z_score = abs(amount - mean) / std
    # Sigmoid mapping: z_score -> risk
    score = 1.0 / (1.0 + math.exp(-0.5 * (z_score - 3.0)))
    return min(score, 1.0)


def compute_velocity_score(user_id: str, amount: float, tx_type: str) -> tuple[float, list[str]]:
    """Score based on transaction velocity (frequency and volume)"""
    now = time.time()
    limits_exceeded = []

    # Clean old entries (keep last 24h)
    velocity_windows[user_id] = [
        tx for tx in velocity_windows[user_id]
        if now - tx["time"] < 86400
    ]

    recent = velocity_windows[user_id]

    # Count in windows
    last_1h = [tx for tx in recent if now - tx["time"] < 3600]
    last_15m = [tx for tx in recent if now - tx["time"] < 900]
    last_5m = [tx for tx in recent if now - tx["time"] < 300]

    score = 0.0

    # Frequency checks
    if len(last_5m) > 5:
        score = max(score, 0.8)
        limits_exceeded.append("5min_frequency_exceeded")
    elif len(last_15m) > 10:
        score = max(score, 0.6)
        limits_exceeded.append("15min_frequency_exceeded")
    elif len(last_1h) > 20:
        score = max(score, 0.5)
        limits_exceeded.append("1h_frequency_exceeded")

    # Volume checks (24h)
    total_24h = sum(tx["amount"] for tx in recent)
    if total_24h + amount > 5000000:  # 5M NGN daily
        score = max(score, 0.9)
        limits_exceeded.append("daily_volume_exceeded")
    elif total_24h + amount > 2000000:  # 2M NGN
        score = max(score, 0.6)
        limits_exceeded.append("daily_volume_warning")

    # Add current transaction
    velocity_windows[user_id].append({
        "time": now, "amount": amount, "type": tx_type
    })

    return score, limits_exceeded


def compute_channel_score(channel: str, user_id: str, amount: float) -> float:
    """Score based on channel risk and user's typical channels"""
    channel_risk = {
        "web": 0.2, "mobile": 0.15, "api": 0.3,
        "ussd": 0.25, "pos": 0.1, "atm": 0.2,
    }
    base_risk = channel_risk.get(channel, 0.3)

    profile = user_profiles.get(user_id)
    if profile:
        typical = profile.get("typical_channels", [])
        if channel not in typical:
            base_risk += 0.2  # Unusual channel

    # USSD high-value is suspicious
    if channel == "ussd" and amount > 100000:
        base_risk += 0.3

    return min(base_risk, 1.0)


def compute_geo_score(country: str, city: str, lat: float, lon: float, user_id: str) -> float:
    """Score based on geographic anomaly"""
    sanctioned = {"KP", "IR", "SY", "CU", "SD", "VE", "MM"}
    high_risk = {"RU", "BY", "CN", "VN", "PH", "BD"}

    if country in sanctioned:
        return 1.0
    if country in high_risk:
        return 0.7

    profile = user_profiles.get(user_id)
    if profile and profile.get("typical_country"):
        if country != profile["typical_country"]:
            return 0.6  # Different country than usual

    return 0.1


def compute_device_score(device_id: str, ip: str, user_agent: str, user_id: str) -> float:
    """Score based on device fingerprint anomaly"""
    if not device_id:
        return 0.3  # Unknown device

    fp = device_fingerprints.get(user_id, {})
    known_devices = fp.get("devices", [])
    known_ips = fp.get("ips", [])

    score = 0.0

    if device_id not in known_devices:
        score += 0.3  # New device
    if ip and ip not in known_ips:
        score += 0.2  # New IP

    # Track device
    if "devices" not in device_fingerprints[user_id]:
        device_fingerprints[user_id]["devices"] = []
    if "ips" not in device_fingerprints[user_id]:
        device_fingerprints[user_id]["ips"] = []

    if device_id not in device_fingerprints[user_id]["devices"]:
        device_fingerprints[user_id]["devices"].append(device_id)
    if ip and ip not in device_fingerprints[user_id]["ips"]:
        device_fingerprints[user_id]["ips"].append(ip)

    # Too many devices is suspicious
    if len(device_fingerprints[user_id]["devices"]) > 5:
        score += 0.3

    return min(score, 1.0)


def compute_temporal_score(timestamp: int, user_id: str) -> float:
    """Score based on time-of-day anomaly"""
    if not timestamp:
        return 0.1

    dt = datetime.fromtimestamp(timestamp / 1000)
    hour = dt.hour

    # Late night transactions are riskier
    if 0 <= hour < 5:
        return 0.5
    if 23 <= hour or hour < 6:
        return 0.3

    profile = user_profiles.get(user_id)
    if profile:
        typical_hours = profile.get("typical_hours", list(range(6, 22)))
        if hour not in typical_hours:
            return 0.4

    return 0.1


def compute_recipient_score(receiver: str, user_id: str, is_new: bool) -> float:
    """Score based on recipient risk"""
    if not receiver:
        return 0.1

    if is_new:
        return 0.4  # New recipient always has some risk

    profile = user_profiles.get(user_id)
    if profile:
        typical_recipients = profile.get("typical_recipients", 0)
        if typical_recipients > 50:
            return 0.5  # Too many unique recipients

    return 0.1


def compute_ml_anomaly_score(features: TransactionFeatures) -> float:
    """Use Isolation Forest to detect anomalies in feature space"""
    # Normalize features to [0, 1]
    feature_vector = np.array([
        min(features.amount / 5000000, 1.0),  # amount normalized
        {"web": 0.2, "mobile": 0.3, "ussd": 0.5, "api": 0.4, "pos": 0.1}.get(features.channel, 0.5),
        (features.kyc_level or 3) / 5.0,
        min((features.account_age_days or 365) / 1000, 1.0),
        min((features.session_age_seconds or 300) / 3600, 1.0),
        1.0 if features.is_new_recipient else 0.0,
        1.0 if features.is_international else 0.0,
        (features.geo_latitude or 9.0) / 90.0,  # normalize lat
    ])

    return isolation_forest.score(feature_vector)


# ── FastAPI App ───────────────────────────────────────────────────────

app = FastAPI(
    title="54agent Fraud ML Service",
    version="1.0.0",
    description="ML-powered fraud detection for agency banking transactions",
)


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "fraud-ml-service",
        "version": "1.0.0",
        "model_trained": isolation_forest.trained,
        "profiles_loaded": len(user_profiles),
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.post("/score", response_model=FraudScore)
async def score_transaction(features: TransactionFeatures):
    """Score a transaction for fraud risk"""
    start = time.time()

    # Compute component scores
    amount_score = compute_amount_score(features.amount, features.currency, features.user_id)
    velocity_score, velocity_limits = compute_velocity_score(
        features.user_id, features.amount, features.transaction_type
    )
    channel_score = compute_channel_score(features.channel, features.user_id, features.amount)
    geo_score = compute_geo_score(
        features.geo_country or "NG",
        features.geo_city or "",
        features.geo_latitude or 0,
        features.geo_longitude or 0,
        features.user_id,
    )
    device_score = compute_device_score(
        features.device_id or "",
        features.ip_address or "",
        features.user_agent or "",
        features.user_id,
    )
    temporal_score = compute_temporal_score(features.timestamp or 0, features.user_id)
    recipient_score = compute_recipient_score(
        features.receiver_account or "",
        features.user_id,
        features.is_new_recipient or False,
    )
    ml_score = compute_ml_anomaly_score(features)

    # Weighted ensemble
    weights = {
        "amount": 0.20,
        "velocity": 0.20,
        "channel": 0.10,
        "geo": 0.15,
        "device": 0.10,
        "temporal": 0.05,
        "recipient": 0.10,
        "ml_anomaly": 0.10,
    }

    component_scores = {
        "amount": round(amount_score, 4),
        "velocity": round(velocity_score, 4),
        "channel": round(channel_score, 4),
        "geo": round(geo_score, 4),
        "device": round(device_score, 4),
        "temporal": round(temporal_score, 4),
        "recipient": round(recipient_score, 4),
        "ml_anomaly": round(ml_score, 4),
    }

    overall = sum(
        component_scores[k] * weights[k] for k in weights
    )
    overall = round(min(overall, 1.0), 4)

    # Determine risk level and decision
    if overall >= 0.8:
        risk_level = "critical"
        decision = "block"
    elif overall >= 0.6:
        risk_level = "high"
        decision = "review"
    elif overall >= 0.4:
        risk_level = "medium"
        decision = "review"
    else:
        risk_level = "low"
        decision = "approve"

    # Collect risk factors
    risk_factors = []
    if amount_score > 0.5:
        risk_factors.append(f"Unusual amount (score: {amount_score:.2f})")
    if velocity_score > 0.5:
        risk_factors.append(f"High velocity (score: {velocity_score:.2f})")
    if geo_score > 0.5:
        risk_factors.append(f"Geographic risk (score: {geo_score:.2f})")
    if device_score > 0.5:
        risk_factors.append(f"Device anomaly (score: {device_score:.2f})")
    if temporal_score > 0.3:
        risk_factors.append(f"Unusual time (score: {temporal_score:.2f})")
    if ml_score > 0.6:
        risk_factors.append(f"ML anomaly detected (score: {ml_score:.2f})")
    risk_factors.extend([f"Velocity limit: {l}" for l in velocity_limits])

    # Recommendations
    recommendations = []
    if decision == "block":
        recommendations.append("Transaction should be blocked and reviewed by compliance")
        recommendations.append("Notify user of suspicious activity")
    elif decision == "review":
        recommendations.append("Flag for manual review by fraud team")
        if device_score > 0.5:
            recommendations.append("Verify device ownership with user")
        if geo_score > 0.5:
            recommendations.append("Verify location with user")

    eval_time = (time.time() - start) * 1000

    # Store in history
    user_tx_history[features.user_id].append({
        "id": features.transaction_id,
        "amount": features.amount,
        "score": overall,
        "time": time.time(),
    })

    logger.info(
        f"Scored tx={features.transaction_id} user={features.user_id} "
        f"amount={features.amount} score={overall} decision={decision}"
    )

    return FraudScore(
        transaction_id=features.transaction_id,
        overall_score=overall,
        risk_level=risk_level,
        decision=decision,
        component_scores=component_scores,
        risk_factors=risk_factors,
        recommendations=recommendations,
        model_version="1.0.0-isolation-forest",
        eval_time_ms=round(eval_time, 2),
    )


@app.post("/velocity", response_model=VelocityResult)
async def check_velocity(req: VelocityCheck):
    """Check transaction velocity for a user"""
    score, limits = compute_velocity_score(
        req.user_id, req.amount, req.transaction_type
    )
    return VelocityResult(
        user_id=req.user_id,
        is_anomalous=score > 0.5,
        velocity_score=round(score, 4),
        details={
            "tx_count_5m": len([
                tx for tx in velocity_windows.get(req.user_id, [])
                if time.time() - tx["time"] < 300
            ]),
            "tx_count_1h": len([
                tx for tx in velocity_windows.get(req.user_id, [])
                if time.time() - tx["time"] < 3600
            ]),
            "volume_24h": sum(
                tx["amount"] for tx in velocity_windows.get(req.user_id, [])
                if time.time() - tx["time"] < 86400
            ),
        },
        limits_exceeded=limits,
    )


@app.get("/profile/{user_id}", response_model=BehaviorProfile)
async def get_behavior_profile(user_id: str):
    """Get behavioral profile for a user"""
    profile = user_profiles.get(user_id)
    if not profile:
        # Build from history
        history = user_tx_history.get(user_id, [])
        if not history:
            return BehaviorProfile(
                user_id=user_id,
                typical_amount_mean=0,
                typical_amount_std=0,
                typical_channels=[],
                typical_hours=[],
                typical_recipients=0,
                transaction_count_30d=0,
                last_updated=datetime.utcnow().isoformat(),
            )

        amounts = [tx["amount"] for tx in history]
        return BehaviorProfile(
            user_id=user_id,
            typical_amount_mean=round(np.mean(amounts), 2) if amounts else 0,
            typical_amount_std=round(np.std(amounts), 2) if len(amounts) > 1 else 0,
            typical_channels=[],
            typical_hours=list(range(6, 22)),
            typical_recipients=0,
            transaction_count_30d=len(history),
            last_updated=datetime.utcnow().isoformat(),
        )

    return BehaviorProfile(
        user_id=user_id,
        typical_amount_mean=profile.get("avg_amount", 0),
        typical_amount_std=profile.get("std_amount", 0),
        typical_channels=profile.get("typical_channels", []),
        typical_hours=profile.get("typical_hours", []),
        typical_recipients=profile.get("typical_recipients", 0),
        transaction_count_30d=profile.get("tx_count_30d", 0),
        last_updated=profile.get("last_updated", datetime.utcnow().isoformat()),
    )


@app.post("/anomaly", response_model=AnomalyDetectionResult)
async def detect_anomaly(req: AnomalyDetectionRequest):
    """Run anomaly detection on a feature vector"""
    if len(req.features) != 8:
        raise HTTPException(
            status_code=400,
            detail="Feature vector must have exactly 8 dimensions",
        )

    features = np.array(req.features)
    score = isolation_forest.score(features)

    return AnomalyDetectionResult(
        user_id=req.user_id,
        is_anomaly=score > 0.6,
        anomaly_score=round(score, 4),
        isolation_score=round(score, 4),
        details=f"Isolation Forest score: {score:.4f} ({'anomaly' if score > 0.6 else 'normal'})",
    )


@app.post("/profile/{user_id}/update")
async def update_profile(user_id: str, profile_data: dict):
    """Update behavioral profile for a user"""
    user_profiles[user_id] = {
        **user_profiles.get(user_id, {}),
        **profile_data,
        "last_updated": datetime.utcnow().isoformat(),
    }
    return {"updated": True, "user_id": user_id}


@app.get("/stats")
async def get_stats():
    """Get service statistics"""
    total_scored = sum(len(h) for h in user_tx_history.values())
    return {
        "total_transactions_scored": total_scored,
        "active_profiles": len(user_profiles),
        "tracked_devices": len(device_fingerprints),
        "velocity_windows_active": len(velocity_windows),
        "model_version": "1.0.0-isolation-forest",
        "model_trained": isolation_forest.trained,
    }



@app.post("/train")
async def train_model(training_data: dict = None):
    """Retrain the fraud detection model with new data"""
    import numpy as np
    try:
        if training_data and "samples" in training_data:
            data = np.array(training_data["samples"])
        else:
            # Generate synthetic normal transaction data for retraining
            data = np.random.randn(1000, 10)
        isolation_forest.fit(data)
        return {
            "status": "trained",
            "samples": len(data),
            "model_version": "1.0.0-isolation-forest",
            "model_trained": isolation_forest.trained,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Training failed: {str(e)}")

# ── Entry Point ───────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("FRAUD_ML_PORT", "8092"))
    logger.info(f"Starting Fraud ML Service on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
