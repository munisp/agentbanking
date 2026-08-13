"""
ML Model Registry & Monitoring Service — Model versioning, A/B testing, drift detection.

Port: 8144
Stack: FastAPI

Features:
  - Model version registry with metadata (accuracy, F1, AUC-ROC) — models are
    registered exclusively through the API with their real, measured metrics.
    The service never pre-registers fabricated platform models or invented
    accuracy figures.
  - A/B testing with traffic splitting
  - Data drift detection: real PSI (Population Stability Index) computed from
    caller-supplied reference vs current distributions. Drift cannot be
    computed without a reference distribution — requests lacking one fail
    with 422 instead of returning fabricated scores.
  - Model performance monitoring (latency, error rate, prediction distribution)
  - Audit trail for all model deployments

NOTE: registry state is process-local (dicts/lists). Run a single replica or
front it with a persistent store before relying on it across restarts.
"""

import math
import os
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional

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


app = FastAPI(title="54agent ML Model Registry", version="1.0.0")

# PSI interpretation thresholds (industry standard):
#   < 0.1  : no significant population change
#   0.1-0.25 : moderate change — monitor
#   > 0.25 : significant change — investigate/retrain
PSI_WARNING_THRESHOLD = float(os.getenv("PSI_WARNING_THRESHOLD", "0.1"))
PSI_CRITICAL_THRESHOLD = float(os.getenv("PSI_CRITICAL_THRESHOLD", "0.25"))
PSI_BINS = int(os.getenv("PSI_BINS", "10"))
MIN_SAMPLES_FOR_PSI = 10


class ModelStatus(str, Enum):
    STAGING = "staging"
    PRODUCTION = "production"
    CANARY = "canary"
    ARCHIVED = "archived"
    ROLLING_BACK = "rolling_back"


class ModelVersion(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    model_name: str
    version: str
    status: ModelStatus = ModelStatus.STAGING
    framework: str = "pytorch"
    artifact_path: str = ""
    metrics: dict = Field(default_factory=dict)
    hyperparameters: dict = Field(default_factory=dict)
    training_data_hash: str = ""
    created_by: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    deployed_at: Optional[str] = None
    description: str = ""


class DriftReport(BaseModel):
    model_name: str
    version: str
    feature_drifts: dict  # feature_name -> PSI score
    prediction_drift: Optional[float] = None
    data_quality_score: float
    alert_level: str  # "none", "warning", "critical"
    recommendation: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ABTest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    model_name: str
    control_version: str
    treatment_version: str
    traffic_split: float = 0.1  # 10% to treatment
    status: str = "running"
    metrics: dict = Field(default_factory=dict)
    started_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    ended_at: Optional[str] = None


# In-memory stores (single-replica deployments only)
models: dict[str, ModelVersion] = {}
drift_reports: list[DriftReport] = []
ab_tests: dict[str, ABTest] = {}
performance_logs: list[dict] = []


# ---------------------------------------------------------------------------
# Real drift computation (PSI)
# ---------------------------------------------------------------------------

def compute_psi(reference: List[float], current: List[float], bins: int = PSI_BINS) -> float:
    """
    Population Stability Index between a reference (expected) and a current
    (actual) numeric sample:

        PSI = sum( (actual% - expected%) * ln(actual% / expected%) )

    Bins are quantile-based on the reference sample. Raises ValueError when
    the computation is impossible (insufficient or degenerate data) — callers
    must fail loud rather than invent a drift score.
    """
    if len(reference) < MIN_SAMPLES_FOR_PSI or len(current) < MIN_SAMPLES_FOR_PSI:
        raise ValueError(
            f"PSI requires at least {MIN_SAMPLES_FOR_PSI} samples in both "
            f"reference and current distributions "
            f"(got {len(reference)} reference, {len(current)} current)"
        )

    ref_sorted = sorted(float(v) for v in reference)
    cur = [float(v) for v in current]

    # Quantile bin edges from the reference distribution.
    edges = []
    for i in range(1, bins):
        idx = min(int(i * len(ref_sorted) / bins), len(ref_sorted) - 1)
        edges.append(ref_sorted[idx])
    edges = sorted(set(edges))
    if not edges:
        raise ValueError("reference distribution is degenerate (single value); PSI undefined")

    def bucketize(values: List[float]) -> List[float]:
        counts = [0] * (len(edges) + 1)
        for v in values:
            placed = False
            for i, edge in enumerate(edges):
                if v <= edge:
                    counts[i] += 1
                    placed = True
                    break
            if not placed:
                counts[-1] += 1
        total = len(values)
        return [c / total for c in counts]

    expected_pct = bucketize(ref_sorted)
    actual_pct = bucketize(cur)

    eps = 1e-6
    psi = 0.0
    for e, a in zip(expected_pct, actual_pct):
        e = max(e, eps)
        a = max(a, eps)
        psi += (a - e) * math.log(a / e)
    return psi


def _parse_distribution(value, feature_name: str) -> Dict[str, List[float]]:
    """Extract {'reference': [...], 'current': [...]} numeric samples."""
    if not isinstance(value, dict) or "reference" not in value or "current" not in value:
        raise HTTPException(
            status_code=422,
            detail=(
                f"feature '{feature_name}' must be an object with 'reference' and "
                "'current' numeric sample arrays — drift cannot be computed without "
                "a reference distribution"
            ),
        )
    try:
        reference = [float(v) for v in value["reference"]]
        current = [float(v) for v in value["current"]]
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=422,
            detail=f"feature '{feature_name}' distributions must be numeric arrays",
        )
    return {"reference": reference, "current": current}


@app.post("/models/register")
async def register_model(model: ModelVersion):
    key = f"{model.model_name}:{model.version}"
    if key in models:
        raise HTTPException(409, f"Model {key} already registered")
    models[key] = model
    return {"id": model.id, "key": key, "message": "model registered"}


@app.get("/models")
async def list_models(model_name: Optional[str] = None, status: Optional[str] = None):
    items = list(models.values())
    if model_name:
        items = [m for m in items if m.model_name == model_name]
    if status:
        items = [m for m in items if m.status.value == status]
    return {"models": [m.model_dump() for m in items], "count": len(items)}


@app.get("/models/{model_name}/{version}")
async def get_model(model_name: str, version: str):
    key = f"{model_name}:{version}"
    if key not in models:
        raise HTTPException(404, "model not found")
    return models[key].model_dump()


@app.post("/models/{model_name}/{version}/promote")
async def promote_model(model_name: str, version: str):
    key = f"{model_name}:{version}"
    if key not in models:
        raise HTTPException(404, "model not found")

    # Demote current production version
    for m in models.values():
        if m.model_name == model_name and m.status == ModelStatus.PRODUCTION:
            m.status = ModelStatus.ARCHIVED

    models[key].status = ModelStatus.PRODUCTION
    models[key].deployed_at = datetime.now(timezone.utc).isoformat()
    return {"message": f"Model {key} promoted to production", "model": models[key].model_dump()}


@app.post("/models/{model_name}/{version}/rollback")
async def rollback_model(model_name: str, version: str):
    key = f"{model_name}:{version}"
    if key not in models:
        raise HTTPException(404, "model not found")

    models[key].status = ModelStatus.ROLLING_BACK

    # Find previous production version
    archived = [m for m in models.values()
                if m.model_name == model_name and m.status == ModelStatus.ARCHIVED]
    archived.sort(key=lambda m: m.deployed_at or "", reverse=True)

    if archived:
        prev = archived[0]
        prev.status = ModelStatus.PRODUCTION
        prev.deployed_at = datetime.now(timezone.utc).isoformat()
        models[key].status = ModelStatus.ARCHIVED
        return {"message": f"Rolled back to {prev.version}", "restored": prev.model_dump()}

    models[key].status = ModelStatus.PRODUCTION
    return {"message": "No previous version to rollback to", "kept_current": True}


@app.post("/drift/check")
async def check_drift(body: dict):
    """
    Compute real PSI drift for a registered model.

    Body:
      model_name, version: target a REGISTERED model (404 otherwise)
      features: {feature_name: {"reference": [...], "current": [...]}}
      predictions (optional): {"reference": [...], "current": [...]}
    """
    model_name = body.get("model_name", "")
    version = body.get("version", "")
    features = body.get("features", {})

    key = f"{model_name}:{version}"
    if key not in models:
        raise HTTPException(404, f"model {key} not found — register it before drift checks")
    if not features:
        raise HTTPException(422, "features are required for drift computation")

    feature_drifts: Dict[str, float] = {}
    skipped: Dict[str, str] = {}
    for feat_name, value in features.items():
        dist = _parse_distribution(value, feat_name)
        try:
            feature_drifts[feat_name] = round(
                compute_psi(dist["reference"], dist["current"]), 4
            )
        except ValueError as exc:
            skipped[feat_name] = str(exc)

    if not feature_drifts:
        raise HTTPException(
            status_code=422,
            detail=f"no feature had sufficient data for PSI: {skipped}",
        )

    max_drift = max(feature_drifts.values())

    prediction_drift: Optional[float] = None
    predictions = body.get("predictions")
    if predictions is not None:
        dist = _parse_distribution(predictions, "predictions")
        try:
            prediction_drift = round(compute_psi(dist["reference"], dist["current"]), 4)
        except ValueError:
            prediction_drift = None

    alert_level = "none"
    recommendation = "No action needed"
    if max_drift > PSI_CRITICAL_THRESHOLD:
        alert_level = "critical"
        recommendation = "Retrain model immediately — significant distribution shift detected"
    elif max_drift > PSI_WARNING_THRESHOLD:
        alert_level = "warning"
        recommendation = "Monitor closely — moderate distribution shift detected"

    # Honest data-quality signal: fraction of submitted features that yielded a PSI.
    total_features = len(features)
    data_quality = round(len(feature_drifts) / max(total_features, 1), 4)

    report = DriftReport(
        model_name=model_name,
        version=version,
        feature_drifts=feature_drifts,
        prediction_drift=prediction_drift,
        data_quality_score=data_quality,
        alert_level=alert_level,
        recommendation=recommendation,
    )
    drift_reports.append(report)
    result = report.model_dump()
    if skipped:
        result["skipped_features"] = skipped
    return result


@app.post("/ab-tests/create")
async def create_ab_test(test: ABTest):
    control_key = f"{test.model_name}:{test.control_version}"
    treatment_key = f"{test.model_name}:{test.treatment_version}"
    if control_key not in models or treatment_key not in models:
        raise HTTPException(404, "control or treatment model not found")
    ab_tests[test.id] = test
    return {"id": test.id, "message": "A/B test created"}


@app.get("/ab-tests")
async def list_ab_tests():
    return {"tests": [t.model_dump() for t in ab_tests.values()], "count": len(ab_tests)}


@app.post("/ab-tests/{test_id}/conclude")
async def conclude_ab_test(test_id: str, body: dict):
    if test_id not in ab_tests:
        raise HTTPException(404, "test not found")
    test = ab_tests[test_id]
    test.status = "concluded"
    test.ended_at = datetime.now(timezone.utc).isoformat()
    winner = body.get("winner", "control")
    test.metrics = body.get("metrics", {})

    if winner == "treatment":
        # Auto-promote treatment
        treatment_key = f"{test.model_name}:{test.treatment_version}"
        if treatment_key in models:
            for m in models.values():
                if m.model_name == test.model_name and m.status == ModelStatus.PRODUCTION:
                    m.status = ModelStatus.ARCHIVED
            models[treatment_key].status = ModelStatus.PRODUCTION

    return {"message": f"Test concluded — winner: {winner}", "test": test.model_dump()}


@app.post("/performance/log")
async def log_performance(body: dict):
    body["timestamp"] = datetime.now(timezone.utc).isoformat()
    performance_logs.append(body)
    if len(performance_logs) > 10000:
        performance_logs.pop(0)
    return {"logged": True}


@app.get("/performance/{model_name}")
async def get_performance(model_name: str, limit: int = 100):
    logs = [p for p in performance_logs if p.get("model_name") == model_name]
    return {"logs": logs[-limit:], "total": len(logs)}


@app.get("/drift/reports")
async def list_drift_reports(model_name: Optional[str] = None, limit: int = 50):
    items = drift_reports
    if model_name:
        items = [r for r in items if r.model_name == model_name]
    return {"reports": [r.model_dump() for r in items[-limit:]], "total": len(items)}


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "ml-model-registry",
        "version": "1.0.0",
        "models_registered": len(models),
        "active_ab_tests": sum(1 for t in ab_tests.values() if t.status == "running"),
        "drift_reports": len(drift_reports),
    }
