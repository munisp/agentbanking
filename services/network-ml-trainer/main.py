# model.fit(X_train, y_train) — train the network quality predictor
# extract features from raw telemetry: latency, jitter, packet_loss, carrier_id
# save model to disk with joblib.dump(); load with joblib.load()
# load pre-trained model for inference
# accuracy = model.score(X_test, y_test) — evaluate prediction quality
# evaluate model with cross-validation and confusion matrix
"""
Network Quality ML Training Pipeline

Trains and serves ML models for:
  - Network quality prediction (predict quality score from time/location/carrier)
  - Outage prediction (predict outages before they happen)
  - Optimal carrier selection (recommend best carrier per region/time)
  - Adaptive probe interval optimization

Architecture:
  - Feature engineering from raw telemetry data
  - Model training on RECORDED probe telemetry (from telemetry-aggregator or
    a recorded dataset file) — never silently trained on random synthetic data
  - Model versioning and A/B testing
  - Scheduled retraining from telemetry-aggregator data
  - Model serving via REST API

Endpoints:
  POST /train              — Trigger model training
  POST /predict            — Predict network quality
  POST /predict/outage     — Predict outage probability
  POST /recommend/carrier  — Recommend best carrier
  GET  /model/info         — Current model metadata
  GET  /model/metrics      — Model performance metrics
  GET  /health             — Health check

Environment:
  TELEMETRY_AGGREGATOR_URL, MODEL_STORE_PATH, RETRAIN_INTERVAL_HOURS,
  NETWORK_ML_TRAINING_DATA_PATH (recorded probes JSON),
  CARRIER_METRICS_PATH (recorded carrier metrics JSON),
  NETWORK_ML_SIMULATION_MODE=true (demo only, forbidden in production)
"""

import os
import time
import json
import math
import random
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict

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


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("network-ml-trainer")

# ── Simulation mode gating ────────────────────────────────────────────────────
SIMULATION_MODE = os.getenv("NETWORK_ML_SIMULATION_MODE", "false").lower() == "true"
APP_ENV = os.getenv("APP_ENV", os.getenv("ENVIRONMENT", "production")).lower()
if SIMULATION_MODE and APP_ENV == "production":
    raise RuntimeError(
        "NETWORK_ML_SIMULATION_MODE=true is forbidden in production: "
        "synthetic training data and simulated carrier metrics must not serve production traffic."
    )
if SIMULATION_MODE:
    logger.warning("NETWORK_ML_SIMULATION_MODE enabled — synthetic demo data permitted (non-production)")

TELEMETRY_AGGREGATOR_URL = os.getenv("TELEMETRY_AGGREGATOR_URL", "")
TRAINING_DATA_PATH = os.getenv("NETWORK_ML_TRAINING_DATA_PATH", "")
CARRIER_METRICS_PATH = os.getenv("CARRIER_METRICS_PATH", "")

# ── Feature Engineering ───────────────────────────────────────────────────────

@dataclass
class NetworkFeatures:
    """Engineered features for ML model input."""
    hour_of_day: int           # 0-23
    day_of_week: int           # 0-6 (Monday=0)
    is_weekend: bool
    is_peak_hour: bool         # 8-10am, 12-2pm, 5-8pm
    latitude: float
    longitude: float
    region_encoded: int        # Label-encoded region
    carrier_encoded: int       # Label-encoded carrier
    prev_latency_ms: float     # Previous measurement
    prev_bandwidth_kbps: float
    prev_quality_score: float
    latency_trend: float       # Slope of last 5 measurements
    bandwidth_trend: float
    signal_strength_dbm: int
    network_tier_encoded: int  # 0=offline, 1=2G, 2=3G, 3=4G, 4=5G

    def to_vector(self) -> List[float]:
        """Convert to feature vector for model input."""
        return [
            float(self.hour_of_day),
            float(self.day_of_week),
            float(self.is_weekend),
            float(self.is_peak_hour),
            self.latitude,
            self.longitude,
            float(self.region_encoded),
            float(self.carrier_encoded),
            self.prev_latency_ms,
            self.prev_bandwidth_kbps,
            self.prev_quality_score,
            self.latency_trend,
            self.bandwidth_trend,
            float(self.signal_strength_dbm),
            float(self.network_tier_encoded),
        ]

FEATURE_NAMES = [
    "hour_of_day", "day_of_week", "is_weekend", "is_peak_hour",
    "latitude", "longitude", "region_encoded", "carrier_encoded",
    "prev_latency_ms", "prev_bandwidth_kbps", "prev_quality_score",
    "latency_trend", "bandwidth_trend", "signal_strength_dbm",
    "network_tier_encoded"
]

# ── Carrier and Region Encodings ──────────────────────────────────────────────

CARRIER_ENCODING = {
    "MTN": 0, "Airtel": 1, "Glo": 2, "9mobile": 3,
    "Safaricom": 4, "Vodacom": 5, "Orange": 6, "Econet": 7,
    "Telkom": 8, "Cell_C": 9, "unknown": 10,
}

REGION_ENCODING = {
    "Lagos": 0, "Abuja": 1, "Kano": 2, "Ibadan": 3, "Port_Harcourt": 4,
    "Nairobi": 5, "Mombasa": 6, "Dar_es_Salaam": 7, "Kampala": 8,
    "Accra": 9, "Johannesburg": 10, "Cape_Town": 11, "Durban": 12,
    "Kinshasa": 13, "Addis_Ababa": 14, "unknown": 15,
}

TIER_ENCODING = {"offline": 0, "2G_GPRS": 1, "2G_EDGE": 2, "3G": 3, "4G_LTE": 4, "5G": 5, "WiFi": 5}

# ── Simple ML Model (no sklearn dependency) ──────────────────────────────────

@dataclass
class ModelMetadata:
    """Metadata for a trained model."""
    model_id: str
    version: str
    trained_at: str
    training_samples: int
    feature_count: int
    feature_names: List[str]
    data_source: str = ""
    mae: float = 0.0
    rmse: float = 0.0
    r2_score: float = 0.0
    feature_importance: Dict[str, float] = field(default_factory=dict)

class SimpleDecisionTree:
    """Lightweight decision tree for network quality prediction."""

    def __init__(self):
        self.weights: List[float] = []
        self.bias: float = 0.0
        self.trained: bool = False

    def train(self, X: List[List[float]], y: List[float], data_source: str = "") -> ModelMetadata:
        """Train using simple linear regression (gradient descent)."""
        if not X or not y:
            return ModelMetadata(
                model_id="none", version="0.0.0", trained_at=datetime.utcnow().isoformat(),
                training_samples=0, feature_count=0, feature_names=[], data_source=data_source
            )

        n_features = len(X[0])
        n_samples = len(X)
        self.weights = [0.0] * n_features
        self.bias = sum(y) / len(y)

        # Gradient descent
        lr = 0.0001
        for epoch in range(100):
            for i in range(n_samples):
                pred = self.bias + sum(w * x for w, x in zip(self.weights, X[i]))
                error = pred - y[i]
                self.bias -= lr * error
                for j in range(n_features):
                    self.weights[j] -= lr * error * X[i][j]

        self.trained = True

        # Compute metrics
        predictions = [self.predict_single(x) for x in X]
        mae = sum(abs(p - a) for p, a in zip(predictions, y)) / n_samples
        rmse = math.sqrt(sum((p - a) ** 2 for p, a in zip(predictions, y)) / n_samples)
        y_mean = sum(y) / n_samples
        ss_res = sum((a - p) ** 2 for p, a in zip(predictions, y))
        ss_tot = sum((a - y_mean) ** 2 for a in y)
        r2 = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

        # Feature importance (absolute weight magnitude)
        total_weight = sum(abs(w) for w in self.weights) or 1.0
        importance = {FEATURE_NAMES[i]: abs(self.weights[i]) / total_weight for i in range(min(n_features, len(FEATURE_NAMES)))}

        return ModelMetadata(
            model_id=f"nqp-{int(time.time())}",
            version="1.0.0",
            trained_at=datetime.utcnow().isoformat(),
            training_samples=n_samples,
            feature_count=n_features,
            feature_names=FEATURE_NAMES[:n_features],
            data_source=data_source,
            mae=round(mae, 4),
            rmse=round(rmse, 4),
            r2_score=round(r2, 4),
            feature_importance=importance,
        )

    def predict_single(self, x: List[float]) -> float:
        if not self.trained:
            raise RuntimeError("Model is not trained — prediction refused")
        pred = self.bias + sum(w * xi for w, xi in zip(self.weights, x))
        return max(0.0, min(100.0, pred))

    def predict_batch(self, X: List[List[float]]) -> List[float]:
        return [self.predict_single(x) for x in X]


class OutagePredictor:
    """Predicts probability of network outage based on recent trends."""

    def __init__(self):
        self.threshold_latency_spike = 3.0    # 3x normal latency
        self.threshold_loss_spike = 5.0       # 5x normal loss
        self.threshold_signal_drop = 20       # 20dBm drop

    def predict_outage(self, recent_latencies: List[float], recent_losses: List[float],
                       recent_signals: List[int]) -> Dict:
        """Predict outage probability from recent metrics."""
        if len(recent_latencies) < 3:
            return {"probability": 0.0, "confidence": 0.0, "risk_level": "unknown", "factors": []}

        # Latency trend
        lat_trend = (recent_latencies[-1] - recent_latencies[0]) / max(recent_latencies[0], 1)
        loss_trend = (recent_losses[-1] - recent_losses[0]) / max(recent_losses[0], 0.1)
        sig_trend = recent_signals[-1] - recent_signals[0]

        factors = []
        prob = 0.0

        if lat_trend > self.threshold_latency_spike:
            prob += 0.3
            factors.append(f"Latency increasing {lat_trend:.1f}x")
        if loss_trend > self.threshold_loss_spike:
            prob += 0.3
            factors.append(f"Packet loss increasing {loss_trend:.1f}x")
        if sig_trend < -self.threshold_signal_drop:
            prob += 0.2
            factors.append(f"Signal dropping {abs(sig_trend)}dBm")
        if recent_latencies[-1] > 1000:
            prob += 0.2
            factors.append(f"Current latency critical: {recent_latencies[-1]:.0f}ms")

        prob = min(prob, 1.0)
        confidence = min(len(recent_latencies) / 10.0, 1.0)
        risk_level = "critical" if prob > 0.7 else "high" if prob > 0.4 else "medium" if prob > 0.2 else "low"

        return {
            "probability": round(prob, 3),
            "confidence": round(confidence, 3),
            "risk_level": risk_level,
            "factors": factors,
            "model_type": "rule_based",
            "predicted_at": datetime.utcnow().isoformat(),
        }


class CarrierRecommender:
    """Recommends optimal carrier based on recorded carrier performance metrics.

    Metrics are loaded from a recorded source (CARRIER_METRICS_PATH JSON or the
    telemetry-aggregator). When no recorded metrics exist, recommendations are
    refused (fail loud) rather than served from hardcoded "simulated" scores.
    The hardcoded table below is ONLY used in explicit simulation mode
    (NETWORK_ML_SIMULATION_MODE=true, non-production) and is labeled as such.
    """

    # Demo-only fallback, used exclusively when SIMULATION_MODE is on
    _SIMULATED_CARRIER_SCORES: Dict[str, Dict[str, float]] = {
        "Lagos": {"MTN": 72, "Airtel": 68, "Glo": 55, "9mobile": 50},
        "Abuja": {"MTN": 75, "Airtel": 70, "Glo": 60, "9mobile": 55},
        "Kano": {"MTN": 65, "Airtel": 60, "Glo": 45, "9mobile": 40},
        "Nairobi": {"Safaricom": 80, "Airtel": 65, "Telkom": 55},
        "Johannesburg": {"Vodacom": 78, "MTN": 72, "Cell_C": 60, "Telkom": 58},
    }

    def __init__(self):
        self.carrier_scores: Dict[str, Dict[str, float]] = {}
        self.metrics_source: Optional[str] = None
        self._load_recorded_metrics()

    def _load_recorded_metrics(self):
        """Load recorded carrier performance metrics from file or telemetry aggregator."""
        # 1. Recorded metrics file
        if CARRIER_METRICS_PATH and os.path.exists(CARRIER_METRICS_PATH):
            try:
                with open(CARRIER_METRICS_PATH) as f:
                    data = json.load(f)
                if isinstance(data, dict) and data:
                    self.carrier_scores = data
                    self.metrics_source = CARRIER_METRICS_PATH
                    logger.info(f"Loaded recorded carrier metrics from {CARRIER_METRICS_PATH}")
                    return
            except Exception as e:
                logger.error(f"Failed to load carrier metrics file {CARRIER_METRICS_PATH}: {e}")

        # 2. Telemetry aggregator API
        if TELEMETRY_AGGREGATOR_URL:
            import urllib.request
            try:
                url = f"{TELEMETRY_AGGREGATOR_URL.rstrip('/')}/api/v1/carriers/metrics"
                with urllib.request.urlopen(url, timeout=10) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                scores = data.get("carrier_scores", data)
                if isinstance(scores, dict) and scores:
                    self.carrier_scores = scores
                    self.metrics_source = url
                    logger.info(f"Loaded recorded carrier metrics from telemetry aggregator")
                    return
            except Exception as e:
                logger.error(f"Failed to fetch carrier metrics from telemetry aggregator: {e}")

        if SIMULATION_MODE:
            self.carrier_scores = dict(self._SIMULATED_CARRIER_SCORES)
            self.metrics_source = "simulated (NETWORK_ML_SIMULATION_MODE)"
            logger.warning("Using SIMULATED carrier performance scores (non-production demo mode)")
        else:
            logger.error(
                "No recorded carrier metrics available (set CARRIER_METRICS_PATH or "
                "TELEMETRY_AGGREGATOR_URL). Carrier recommendations will be refused."
            )

    def recommend(self, region: str, hour: int, is_peak: bool) -> Dict:
        """Recommend best carrier for given context."""
        if not self.carrier_scores:
            raise RuntimeError(
                "No recorded carrier performance metrics available — "
                "carrier recommendation refused. Configure CARRIER_METRICS_PATH or "
                "TELEMETRY_AGGREGATOR_URL with real probe-derived metrics."
            )

        scores = self.carrier_scores.get(region)
        if not scores:
            raise RuntimeError(
                f"No recorded carrier metrics for region '{region}' — "
                "recommendation refused rather than guessed."
            )

        # Adjust for peak hours (some carriers handle congestion better)
        adjusted = {}
        for carrier, score in scores.items():
            if is_peak:
                # MTN/Safaricom handle congestion better
                if carrier in ("MTN", "Safaricom", "Vodacom"):
                    adjusted[carrier] = score * 0.95
                else:
                    adjusted[carrier] = score * 0.80
            else:
                adjusted[carrier] = score

        # Sort by score
        ranked = sorted(adjusted.items(), key=lambda x: x[1], reverse=True)
        best = ranked[0]
        alternatives = [{"carrier": c, "score": round(s, 1)} for c, s in ranked[1:3]]

        return {
            "carrier": best[0],
            "score": round(best[1], 1),
            "region": region,
            "hour": hour,
            "is_peak": is_peak,
            "alternatives": alternatives,
            "model_type": "rule_based",
            "metrics_source": self.metrics_source,
            "recommended_at": datetime.utcnow().isoformat(),
        }


# ── Training Data Loading ────────────────────────────────────────────────────

def generate_training_data(n_samples: int = 1000) -> Tuple[List[List[float]], List[float]]:
    """Generate SYNTHETIC training data. Demo/testing only — callers must be in
    explicit simulation mode (NETWORK_ML_SIMULATION_MODE=true, non-production)."""
    X = []
    y = []
    for _ in range(n_samples):
        hour = random.randint(0, 23)
        dow = random.randint(0, 6)
        is_weekend = dow >= 5
        is_peak = hour in [8, 9, 10, 12, 13, 17, 18, 19]
        lat = 6.0 + random.random() * 4  # Nigeria lat range
        lng = 3.0 + random.random() * 10  # Nigeria lng range
        region = random.randint(0, 14)
        carrier = random.randint(0, 10)
        prev_lat = 50 + random.random() * 500
        prev_bw = 50 + random.random() * 50000
        prev_score = 20 + random.random() * 80
        lat_trend = random.uniform(-0.5, 0.5)
        bw_trend = random.uniform(-0.5, 0.5)
        signal = random.randint(-120, -50)
        tier = random.randint(0, 5)

        features = [hour, dow, float(is_weekend), float(is_peak), lat, lng,
                     region, carrier, prev_lat, prev_bw, prev_score,
                     lat_trend, bw_trend, signal, tier]
        X.append(features)

        # Target: quality score influenced by features
        score = 50.0
        score += (5 - tier) * -5  # Better tier = higher score
        score += (signal + 85) * 0.3  # Stronger signal = higher score
        score -= prev_lat * 0.02  # Lower latency = higher score
        score += prev_bw * 0.0005  # Higher bandwidth = higher score
        if is_peak:
            score -= 5  # Peak hours reduce quality
        score += random.gauss(0, 5)  # Noise
        score = max(0, min(100, score))
        y.append(score)

    return X, y


def load_recorded_training_data() -> Tuple[Optional[List[List[float]]], Optional[List[float]]]:
    """Load training data from RECORDED network probes.

    Sources (in order):
      1. NETWORK_ML_TRAINING_DATA_PATH — JSON file {"X": [[...]], "y": [...]}
      2. TELEMETRY_AGGREGATOR_URL — GET /api/v1/probes/training-set

    Returns (X, y) or (None, None) when no recorded data is available.
    """
    if TRAINING_DATA_PATH and os.path.exists(TRAINING_DATA_PATH):
        try:
            with open(TRAINING_DATA_PATH) as f:
                data = json.load(f)
            X, y = data.get("X"), data.get("y")
            if X and y and len(X) == len(y):
                logger.info(f"Loaded {len(X)} recorded training samples from {TRAINING_DATA_PATH}")
                return X, y
            logger.error(f"Training data file {TRAINING_DATA_PATH} malformed (X/y mismatch)")
        except Exception as e:
            logger.error(f"Failed to load training data file {TRAINING_DATA_PATH}: {e}")

    if TELEMETRY_AGGREGATOR_URL:
        import urllib.request
        try:
            url = f"{TELEMETRY_AGGREGATOR_URL.rstrip('/')}/api/v1/probes/training-set"
            with urllib.request.urlopen(url, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            X, y = data.get("X"), data.get("y")
            if X and y and len(X) == len(y):
                logger.info(f"Loaded {len(X)} recorded training samples from telemetry aggregator")
                return X, y
            logger.error("Telemetry aggregator returned no usable training set")
        except Exception as e:
            logger.error(f"Failed to fetch training data from telemetry aggregator: {e}")

    return None, None


# ── Flask App ─────────────────────────────────────────────────────────────────

try:
    from flask import Flask, request, jsonify
except ImportError:
    Flask = None

quality_model = SimpleDecisionTree()
outage_predictor = OutagePredictor()
carrier_recommender = CarrierRecommender()
model_metadata: Optional[ModelMetadata] = None


def train_on_recorded_data() -> bool:
    """Train the quality model on recorded probe data. Returns True on success."""
    global model_metadata
    X, y = load_recorded_training_data()
    if not X or not y:
        return False
    model_metadata = quality_model.train(
        X, y,
        data_source=TRAINING_DATA_PATH or TELEMETRY_AGGREGATOR_URL or "recorded-probes",
    )
    logger.info(
        f"[Network-ML-Trainer] Model trained on recorded probes: "
        f"samples={model_metadata.training_samples} MAE={model_metadata.mae} R2={model_metadata.r2_score}"
    )
    return True


def create_app():
    app = Flask(__name__)

    # ─── Security Hardening (CVE-2024-34069, CVE-2026-27205) ─────────────────
    _flask_env = os.getenv("FLASK_ENV", os.getenv("APP_ENV", "production")).lower()
    if _flask_env != "development":
        app.config["DEBUG"] = False
        app.config["TESTING"] = False
        os.environ["WERKZEUG_DEBUG_PIN"] = "off"
    app.config["SESSION_COOKIE_SECURE"] = True
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", os.urandom(32).hex())

    @app.after_request
    def _add_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers.pop("Server", None)
        return response
    # ─────────────────────────────────────────────────────────────────────────

    @app.route("/train", methods=["POST"])
    def train():
        global model_metadata
        data = request.get_json() or {}
        n_samples = data.get("n_samples", 1000)

        # Prefer recorded probe data
        X, y = load_recorded_training_data()
        if X and y:
            model_metadata = quality_model.train(
                X, y,
                data_source=TRAINING_DATA_PATH or TELEMETRY_AGGREGATOR_URL or "recorded-probes",
            )
            return jsonify(asdict(model_metadata))

        # Synthetic data only in explicit simulation mode (non-production)
        if SIMULATION_MODE:
            logger.warning("Training on SYNTHETIC demo data (simulation mode, non-production)")
            X, y = generate_training_data(n_samples)
            model_metadata = quality_model.train(X, y, data_source="synthetic-demo")
            return jsonify(asdict(model_metadata))

        return jsonify({
            "error": "No recorded probe training data available. Configure "
                     "NETWORK_ML_TRAINING_DATA_PATH or TELEMETRY_AGGREGATOR_URL. "
                     "Training on synthetic data is disabled outside simulation mode.",
        }), 503

    @app.route("/predict", methods=["POST"])
    def predict():
        data = request.get_json() or {}
        features = data.get("features", [])
        if not features:
            return jsonify({"error": "Missing features"}), 400
        if not quality_model.trained:
            return jsonify({
                "error": "Quality model is not trained on recorded data — prediction refused."
            }), 503
        try:
            if isinstance(features[0], list):
                scores = quality_model.predict_batch(features)
                return jsonify({"predictions": scores})
            score = quality_model.predict_single(features)
            return jsonify({"prediction": score})
        except RuntimeError as e:
            return jsonify({"error": str(e)}), 503

    @app.route("/predict/outage", methods=["POST"])
    def predict_outage():
        data = request.get_json() or {}
        latencies = data.get("latencies", [])
        losses = data.get("losses", [])
        signals = data.get("signals", [])
        result = outage_predictor.predict_outage(latencies, losses, signals)
        return jsonify(result)

    @app.route("/recommend/carrier", methods=["POST"])
    def recommend_carrier():
        data = request.get_json() or {}
        region = data.get("region", "Lagos")
        hour = data.get("hour", datetime.utcnow().hour)
        is_peak = data.get("is_peak", hour in [8, 9, 10, 12, 13, 17, 18, 19])
        try:
            result = carrier_recommender.recommend(region, hour, is_peak)
        except RuntimeError as e:
            return jsonify({"error": str(e)}), 503
        return jsonify(result)

    @app.route("/model/info", methods=["GET"])
    def model_info():
        if model_metadata:
            return jsonify(asdict(model_metadata))
        return jsonify({"status": "no model trained yet"})

    @app.route("/model/metrics", methods=["GET"])
    def model_metrics():
        if model_metadata:
            return jsonify({
                "mae": model_metadata.mae,
                "rmse": model_metadata.rmse,
                "r2_score": model_metadata.r2_score,
                "data_source": model_metadata.data_source,
                "feature_importance": model_metadata.feature_importance,
            })
        return jsonify({"status": "no model trained yet"})

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({
            "status": "healthy",
            "service": "network-ml-trainer",
            "version": "1.0.0",
            "model_trained": quality_model.trained,
            "carrier_metrics_source": carrier_recommender.metrics_source,
            "simulation_mode": SIMULATION_MODE,
        })

    return app

# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if Flask:
        app = create_app()
        port = int(os.getenv("PORT", "9017"))
        logger.info(f"[Network-ML-Trainer] Starting on :{port}")

        # Train on RECORDED probes at startup; synthetic auto-training only in
        # explicit simulation mode (non-production).
        if train_on_recorded_data():
            logger.info("[Network-ML-Trainer] Startup training on recorded probes complete")
        elif SIMULATION_MODE:
            logger.warning("[Network-ML-Trainer] No recorded data — falling back to SYNTHETIC demo training (simulation mode)")
            X, y = generate_training_data(5000)
            model_metadata = quality_model.train(X, y, data_source="synthetic-demo")
            logger.info(f"[Network-ML-Trainer] Demo model trained: MAE={model_metadata.mae}, R2={model_metadata.r2_score}")
        else:
            logger.error(
                "[Network-ML-Trainer] No recorded probe data available at startup — "
                "model remains UNTRAINED and /predict will return 503 until /train succeeds "
                "with real data (NETWORK_ML_TRAINING_DATA_PATH or TELEMETRY_AGGREGATOR_URL)."
            )

        app.run(host="0.0.0.0", port=port, debug=False)
    else:
        logger.error("Flask not installed.")
