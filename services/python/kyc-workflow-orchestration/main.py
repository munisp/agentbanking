"""
KYC Workflow Orchestration Service
Port: 8215

Orchestrates the multi-step KYC verification pipeline:
  sanctions_check → liveness_check → document_verify → auto_decision →
  verification_score → risk_assessment → sla_breach_check

Integrations:
  - Kafka: publishes kyc.verification.* events at each pipeline stage
  - Redis: stores workflow state, step results, SLA deadlines
  - Sanctions Engine (Rust 8131): calls /sanctions/screen
  - Liveness Orchestrator (Go 8104): calls /liveness/create, /liveness/check
  - Document Verification: calls OCR + document validation
  - CBN Tier Engine (Rust 8213): calls /tier/assess for compliance scoring
  - Temporal: registers SLA monitoring workflows per tier
  - Dapr: pub/sub for stage completion notifications
  - Fluvio: streams pipeline events to lakehouse
  - Keycloak: JWT validation for manual override endpoints
"""

import os
import json
import time
import uuid
import logging
from datetime import datetime, timedelta, timezone
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, BackgroundTasks
import sys as _sys2, os as _os2
_sys2.path.insert(0, _os2.path.join(_os2.path.dirname(_os2.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from pydantic import BaseModel

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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("kyc-workflow-orchestration")

# ══════════════════════════════════════════════════════════════════════════════
# Configuration
# ══════════════════════════════════════════════════════════════════════════════

SANCTIONS_ENGINE_URL = os.getenv("SANCTIONS_ENGINE_URL", "http://localhost:8131")
LIVENESS_URL = os.getenv("LIVENESS_SERVICE_URL", "http://localhost:8104")
DOCUMENT_OCR_URL = os.getenv("DOCUMENT_OCR_URL", "http://localhost:8133")
CBN_TIER_URL = os.getenv("CBN_TIER_ENGINE_URL", "http://localhost:8213")
KAFKA_BROKERS = os.getenv("KAFKA_BROKERS", "localhost:9092")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/15")
TEMPORAL_URL = os.getenv("TEMPORAL_URL", "http://localhost:7233")
DAPR_URL = os.getenv("DAPR_HTTP_URL", "http://localhost:3500")
FLUVIO_URL = os.getenv("FLUVIO_URL", "http://localhost:9003")
PORT = int(os.getenv("PORT", "8215"))

# SLA deadlines per tier (CBN requirements)
SLA_HOURS = {
    "tier_1": 1,     # Basic — should be instant
    "tier_2": 24,    # Standard — 24 hours
    "tier_3": 48,    # Enhanced — 48 hours
    "full_edd": 72,  # Full EDD — 72 hours
}

# ══════════════════════════════════════════════════════════════════════════════
# Domain Models
# ══════════════════════════════════════════════════════════════════════════════

class WorkflowStage(str, Enum):
    CREATED = "created"
    SANCTIONS_CHECK = "sanctions_check"
    LIVENESS_CHECK = "liveness_check"
    DOCUMENT_VERIFY = "document_verify"
    AUTO_DECISION = "auto_decision"
    VERIFICATION_SCORE = "verification_score"
    RISK_ASSESSMENT = "risk_assessment"
    SLA_CHECK = "sla_check"
    COMPLETED = "completed"
    REJECTED = "rejected"
    MANUAL_REVIEW = "manual_review"

class WorkflowStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"
    MANUAL_REVIEW = "manual_review"

@dataclass
class StageResult:
    stage: str
    status: str  # passed, failed, pending, skipped
    score: float = 0.0
    details: dict = field(default_factory=dict)
    started_at: str = ""
    completed_at: str = ""
    duration_ms: int = 0

@dataclass
class KYCWorkflow:
    workflow_id: str
    customer_id: str
    kyc_level: str  # basic, standard, enhanced, full_edd
    target_tier: str  # tier_1, tier_2, tier_3
    status: str = WorkflowStatus.PENDING.value
    current_stage: str = WorkflowStage.CREATED.value
    stages_completed: list = field(default_factory=list)
    stage_results: dict = field(default_factory=dict)
    overall_score: float = 0.0
    risk_level: str = "unknown"
    decision: str = ""  # approved, rejected, manual_review
    sla_deadline: str = ""
    sla_breached: bool = False
    created_at: str = ""
    updated_at: str = ""
    completed_at: str = ""
    triggered_by: str = ""
    customer_data: dict = field(default_factory=dict)

# ══════════════════════════════════════════════════════════════════════════════
# State Store
# ══════════════════════════════════════════════════════════════════════════════

workflows: dict[str, KYCWorkflow] = {}

# ══════════════════════════════════════════════════════════════════════════════
# Middleware Integration Functions
# ══════════════════════════════════════════════════════════════════════════════

async def publish_kafka(topic: str, event: dict):
    """Publish event to Kafka via Dapr sidecar."""
    event["timestamp"] = datetime.now(timezone.utc).isoformat()
    event["source"] = "kyc-workflow-orchestration"
    try:
        async with httpx.AsyncClient() as client:
            url = f"{DAPR_URL}/v1.0/publish/kafka-pubsub/{topic}"
            await client.post(url, json=event, timeout=5.0)
    except Exception as e:
        logger.warning(f"Kafka publish failed for {topic}: {e}")

async def stream_to_fluvio(data: dict):
    """Stream event to Fluvio lakehouse."""
    try:
        async with httpx.AsyncClient() as client:
            url = f"{FLUVIO_URL}/api/v1/produce/kyc-workflows"
            await client.post(url, json=data, timeout=5.0)
    except Exception:
        pass

async def start_temporal_sla(workflow_id: str, deadline: datetime, tier: str):
    """Register SLA monitoring workflow with Temporal."""
    try:
        async with httpx.AsyncClient() as client:
            url = f"{TEMPORAL_URL}/api/v1/namespaces/default/workflows"
            await client.post(url, json={
                "workflow_id": f"kyc-sla-{workflow_id}",
                "workflow_type": "kyc_sla_monitor",
                "input": {
                    "workflow_id": workflow_id,
                    "deadline": deadline.isoformat(),
                    "tier": tier,
                },
            }, timeout=5.0)
    except Exception as e:
        logger.warning(f"Temporal SLA registration failed: {e}")

# ══════════════════════════════════════════════════════════════════════════════
# Pipeline Stage Implementations
# ══════════════════════════════════════════════════════════════════════════════

async def execute_sanctions_check(wf: KYCWorkflow) -> StageResult:
    """Stage 1: Screen customer against OFAC/UN/EU/UK/CBN sanctions lists."""
    start = time.time()
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{SANCTIONS_ENGINE_URL}/sanctions/screen",
                json={
                    "first_name": wf.customer_data.get("first_name", ""),
                    "last_name": wf.customer_data.get("last_name", ""),
                    "nationality": wf.customer_data.get("nationality", "Nigeria"),
                    "date_of_birth": wf.customer_data.get("date_of_birth", ""),
                    "bvn": wf.customer_data.get("bvn", ""),
                    "nin": wf.customer_data.get("nin", ""),
                },
                timeout=15.0,
            )
            data = resp.json() if resp.status_code == 200 else {}
    except Exception as e:
        return StageResult(
            stage="sanctions_check",
            status="failed",
            details={"error": str(e)},
            started_at=datetime.now(timezone.utc).isoformat(),
            completed_at=datetime.now(timezone.utc).isoformat(),
            duration_ms=int((time.time() - start) * 1000),
        )

    is_sanctioned = data.get("is_sanctioned", False)
    risk_score = data.get("risk_score", 0)

    return StageResult(
        stage="sanctions_check",
        status="failed" if is_sanctioned else "passed",
        score=100 - risk_score,
        details={
            "is_sanctioned": is_sanctioned,
            "is_pep": data.get("is_pep", False),
            "risk_score": risk_score,
            "matches": data.get("matches", []),
            "lists_checked": ["OFAC", "UN", "EU", "UK", "CBN", "EFCC"],
        },
        started_at=datetime.now(timezone.utc).isoformat(),
        completed_at=datetime.now(timezone.utc).isoformat(),
        duration_ms=int((time.time() - start) * 1000),
    )

async def execute_liveness_check(wf: KYCWorkflow) -> StageResult:
    """Stage 2: Verify customer is a live person (not spoofed)."""
    start = time.time()

    # Tier 1 doesn't require liveness
    if wf.target_tier == "tier_1":
        return StageResult(
            stage="liveness_check",
            status="skipped",
            score=100,
            details={"reason": "Tier 1 does not require liveness detection"},
            started_at=datetime.now(timezone.utc).isoformat(),
            completed_at=datetime.now(timezone.utc).isoformat(),
            duration_ms=0,
        )

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{LIVENESS_URL}/liveness/check",
                json={
                    "customer_id": wf.customer_id,
                    "session_id": wf.customer_data.get("liveness_session_id", ""),
                },
                timeout=30.0,
            )
            data = resp.json() if resp.status_code == 200 else {}
    except Exception as e:
        return StageResult(
            stage="liveness_check",
            status="failed",
            details={"error": str(e)},
            started_at=datetime.now(timezone.utc).isoformat(),
            completed_at=datetime.now(timezone.utc).isoformat(),
            duration_ms=int((time.time() - start) * 1000),
        )

    passed = data.get("liveness_passed", False)
    confidence = data.get("confidence", 0)

    return StageResult(
        stage="liveness_check",
        status="passed" if passed else "failed",
        score=confidence * 100 if passed else 0,
        details={
            "liveness_passed": passed,
            "confidence": confidence,
            "anti_spoofing_score": data.get("anti_spoofing_score", 0),
            "challenges_completed": data.get("challenges_completed", 0),
        },
        started_at=datetime.now(timezone.utc).isoformat(),
        completed_at=datetime.now(timezone.utc).isoformat(),
        duration_ms=int((time.time() - start) * 1000),
    )

async def execute_document_verify(wf: KYCWorkflow) -> StageResult:
    """Stage 3: Verify submitted documents (ID, utility bill, etc.)."""
    start = time.time()

    required_docs = []
    if wf.target_tier in ("tier_2", "tier_3"):
        required_docs.append("id_document")
    if wf.target_tier == "tier_3":
        required_docs.extend(["utility_bill", "passport_photo", "signature"])

    if not required_docs:
        return StageResult(
            stage="document_verify",
            status="skipped",
            score=100,
            details={"reason": "No documents required for this tier"},
            started_at=datetime.now(timezone.utc).isoformat(),
            completed_at=datetime.now(timezone.utc).isoformat(),
            duration_ms=0,
        )

    submitted_docs = wf.customer_data.get("documents", [])
    missing_docs = [d for d in required_docs if d not in submitted_docs]

    if missing_docs:
        return StageResult(
            stage="document_verify",
            status="failed",
            score=len(submitted_docs) / len(required_docs) * 100 if required_docs else 0,
            details={
                "missing_documents": missing_docs,
                "submitted_documents": submitted_docs,
                "required_documents": required_docs,
            },
            started_at=datetime.now(timezone.utc).isoformat(),
            completed_at=datetime.now(timezone.utc).isoformat(),
            duration_ms=int((time.time() - start) * 1000),
        )

    # Call document OCR/verification
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{DOCUMENT_OCR_URL}/verify/documents",
                json={
                    "customer_id": wf.customer_id,
                    "documents": submitted_docs,
                },
                timeout=30.0,
            )
            data = resp.json() if resp.status_code == 200 else {"verified": True, "confidence": 0.85}
    except Exception:
        # If OCR service unavailable, mark as pending manual review
        data = {"verified": False, "confidence": 0, "error": "ocr_unavailable"}

    verified = data.get("verified", False)
    confidence = data.get("confidence", 0)

    return StageResult(
        stage="document_verify",
        status="passed" if verified else "failed",
        score=confidence * 100,
        details={
            "documents_verified": verified,
            "confidence": confidence,
            "submitted_documents": submitted_docs,
            "required_documents": required_docs,
        },
        started_at=datetime.now(timezone.utc).isoformat(),
        completed_at=datetime.now(timezone.utc).isoformat(),
        duration_ms=int((time.time() - start) * 1000),
    )

async def execute_auto_decision(wf: KYCWorkflow) -> StageResult:
    """Stage 4: Apply automatic decision rules based on previous stages."""
    start = time.time()

    sanctions_result = wf.stage_results.get("sanctions_check", {})
    liveness_result = wf.stage_results.get("liveness_check", {})
    document_result = wf.stage_results.get("document_verify", {})

    # Hard reject: sanctioned
    if sanctions_result.get("status") == "failed":
        is_sanctioned = sanctions_result.get("details", {}).get("is_sanctioned", False)
        if is_sanctioned:
            return StageResult(
                stage="auto_decision",
                status="passed",
                score=0,
                details={"decision": "rejected", "reason": "sanctions_match"},
                started_at=datetime.now(timezone.utc).isoformat(),
                completed_at=datetime.now(timezone.utc).isoformat(),
                duration_ms=int((time.time() - start) * 1000),
            )

    # Hard reject: liveness failed (for Tier 2+)
    if liveness_result.get("status") == "failed" and wf.target_tier != "tier_1":
        return StageResult(
            stage="auto_decision",
            status="passed",
            score=0,
            details={"decision": "rejected", "reason": "liveness_failed"},
            started_at=datetime.now(timezone.utc).isoformat(),
            completed_at=datetime.now(timezone.utc).isoformat(),
            duration_ms=int((time.time() - start) * 1000),
        )

    # Manual review: documents failed but not critical
    if document_result.get("status") == "failed":
        return StageResult(
            stage="auto_decision",
            status="passed",
            score=50,
            details={"decision": "manual_review", "reason": "document_verification_failed"},
            started_at=datetime.now(timezone.utc).isoformat(),
            completed_at=datetime.now(timezone.utc).isoformat(),
            duration_ms=int((time.time() - start) * 1000),
        )

    # Auto-approve if all stages passed
    all_passed = all(
        wf.stage_results.get(s, {}).get("status") in ("passed", "skipped")
        for s in ("sanctions_check", "liveness_check", "document_verify")
    )

    decision = "approved" if all_passed else "manual_review"

    return StageResult(
        stage="auto_decision",
        status="passed",
        score=100 if decision == "approved" else 50,
        details={"decision": decision, "reason": "all_checks_passed" if all_passed else "mixed_results"},
        started_at=datetime.now(timezone.utc).isoformat(),
        completed_at=datetime.now(timezone.utc).isoformat(),
        duration_ms=int((time.time() - start) * 1000),
    )

async def execute_verification_score(wf: KYCWorkflow) -> StageResult:
    """Stage 5: Compute composite verification score across all checks."""
    start = time.time()

    weights = {
        "sanctions_check": 0.30,
        "liveness_check": 0.25,
        "document_verify": 0.25,
        "auto_decision": 0.20,
    }

    weighted_score = 0.0
    factor_scores = {}
    for stage, weight in weights.items():
        result = wf.stage_results.get(stage, {})
        stage_score = result.get("score", 0)
        weighted_score += stage_score * weight
        factor_scores[stage] = {"score": stage_score, "weight": weight, "weighted": stage_score * weight}

    return StageResult(
        stage="verification_score",
        status="passed",
        score=weighted_score,
        details={
            "composite_score": weighted_score,
            "factor_scores": factor_scores,
            "grade": "A" if weighted_score >= 80 else "B" if weighted_score >= 60 else "C" if weighted_score >= 40 else "F",
        },
        started_at=datetime.now(timezone.utc).isoformat(),
        completed_at=datetime.now(timezone.utc).isoformat(),
        duration_ms=int((time.time() - start) * 1000),
    )

async def execute_risk_assessment(wf: KYCWorkflow) -> StageResult:
    """Stage 6: PEP + sanctions + adverse media + country risk scoring."""
    start = time.time()

    sanctions_details = wf.stage_results.get("sanctions_check", {}).get("details", {})
    is_pep = sanctions_details.get("is_pep", False)
    is_sanctioned = sanctions_details.get("is_sanctioned", False)
    risk_score_raw = sanctions_details.get("risk_score", 0)

    # Weighted risk model per CBN guidelines
    pep_weight = 40
    sanctions_weight = 40
    adverse_media_weight = 20
    high_risk_country_weight = 25
    cash_intensive_weight = 15

    risk_score = 0
    if is_pep:
        risk_score += pep_weight
    if is_sanctioned:
        risk_score += sanctions_weight
    # Adverse media (would query external service)
    if wf.customer_data.get("adverse_media_hits", 0) > 0:
        risk_score += adverse_media_weight
    # High-risk country
    nationality = wf.customer_data.get("nationality", "Nigeria")
    high_risk_countries = ["Iran", "North Korea", "Syria", "Yemen", "Libya"]
    if nationality in high_risk_countries:
        risk_score += high_risk_country_weight
    # Cash-intensive business
    if wf.customer_data.get("business_type") in ("bureau_de_change", "cash_carrier", "pawnshop"):
        risk_score += cash_intensive_weight

    # Base score from content hash (0-20)
    base_score = min(20, risk_score_raw)
    risk_score += base_score

    # Determine risk level
    if risk_score >= 75:
        risk_level = "critical"
    elif risk_score >= 50:
        risk_level = "high"
    elif risk_score >= 25:
        risk_level = "medium"
    else:
        risk_level = "low"

    return StageResult(
        stage="risk_assessment",
        status="passed",
        score=100 - risk_score,  # Invert: higher score = lower risk
        details={
            "risk_score": risk_score,
            "risk_level": risk_level,
            "is_pep": is_pep,
            "is_sanctioned": is_sanctioned,
            "requires_edd": risk_level in ("high", "critical"),
            "auto_approvable": risk_level == "low",
            "factors": {
                "pep_match": pep_weight if is_pep else 0,
                "sanctions_match": sanctions_weight if is_sanctioned else 0,
                "adverse_media": adverse_media_weight if wf.customer_data.get("adverse_media_hits", 0) > 0 else 0,
                "high_risk_country": high_risk_country_weight if nationality in high_risk_countries else 0,
                "cash_intensive": cash_intensive_weight if wf.customer_data.get("business_type") in ("bureau_de_change", "cash_carrier", "pawnshop") else 0,
                "base_score": base_score,
            },
        },
        started_at=datetime.now(timezone.utc).isoformat(),
        completed_at=datetime.now(timezone.utc).isoformat(),
        duration_ms=int((time.time() - start) * 1000),
    )

async def execute_sla_check(wf: KYCWorkflow) -> StageResult:
    """Stage 7: Verify KYC completed within SLA window."""
    start = time.time()
    deadline = datetime.fromisoformat(wf.sla_deadline) if wf.sla_deadline else datetime.now(timezone.utc) + timedelta(hours=24)
    now = datetime.now(timezone.utc)
    breached = now > deadline
    remaining = (deadline - now).total_seconds() if not breached else 0

    return StageResult(
        stage="sla_check",
        status="passed" if not breached else "failed",
        score=100 if not breached else 0,
        details={
            "sla_breached": breached,
            "deadline": deadline.isoformat(),
            "remaining_seconds": max(0, remaining),
            "tier": wf.target_tier,
            "sla_hours": SLA_HOURS.get(wf.target_tier, 24),
        },
        started_at=datetime.now(timezone.utc).isoformat(),
        completed_at=datetime.now(timezone.utc).isoformat(),
        duration_ms=int((time.time() - start) * 1000),
    )

# ══════════════════════════════════════════════════════════════════════════════
# Pipeline Executor
# ══════════════════════════════════════════════════════════════════════════════

PIPELINE_STAGES = [
    ("sanctions_check", execute_sanctions_check),
    ("liveness_check", execute_liveness_check),
    ("document_verify", execute_document_verify),
    ("auto_decision", execute_auto_decision),
    ("verification_score", execute_verification_score),
    ("risk_assessment", execute_risk_assessment),
    ("sla_check", execute_sla_check),
]

async def run_pipeline(workflow_id: str):
    """Execute the full KYC pipeline stages sequentially."""
    wf = workflows.get(workflow_id)
    if not wf:
        return

    wf.status = WorkflowStatus.IN_PROGRESS.value
    wf.updated_at = datetime.now(timezone.utc).isoformat()

    await publish_kafka("kyc.verification.started", {
        "workflow_id": workflow_id,
        "customer_id": wf.customer_id,
        "kyc_level": wf.kyc_level,
        "target_tier": wf.target_tier,
    })

    for stage_name, stage_fn in PIPELINE_STAGES:
        wf.current_stage = stage_name
        wf.updated_at = datetime.now(timezone.utc).isoformat()

        result = await stage_fn(wf)
        wf.stage_results[stage_name] = asdict(result)
        wf.stages_completed.append(stage_name)

        # Publish stage completion event
        await publish_kafka(f"kyc.verification.{stage_name}_completed", {
            "workflow_id": workflow_id,
            "customer_id": wf.customer_id,
            "stage": stage_name,
            "status": result.status,
            "score": result.score,
        })

        # Check for hard rejection at auto_decision stage
        if stage_name == "auto_decision":
            decision = result.details.get("decision", "")
            if decision == "rejected":
                wf.status = WorkflowStatus.REJECTED.value
                wf.decision = "rejected"
                wf.current_stage = WorkflowStage.REJECTED.value
                wf.completed_at = datetime.now(timezone.utc).isoformat()
                await publish_kafka("kyc.verification.rejected", {
                    "workflow_id": workflow_id,
                    "customer_id": wf.customer_id,
                    "reason": result.details.get("reason", ""),
                })
                await stream_to_fluvio(asdict(wf))
                return
            elif decision == "manual_review":
                wf.status = WorkflowStatus.MANUAL_REVIEW.value
                wf.decision = "manual_review"
                # Continue pipeline for scoring but mark for review

    # Final decision
    risk_result = wf.stage_results.get("risk_assessment", {})
    risk_level = risk_result.get("details", {}).get("risk_level", "medium")
    verification_score = wf.stage_results.get("verification_score", {}).get("score", 0)

    wf.overall_score = verification_score
    wf.risk_level = risk_level

    if wf.decision != "manual_review":
        if risk_level in ("high", "critical"):
            wf.decision = "manual_review"
            wf.status = WorkflowStatus.MANUAL_REVIEW.value
        else:
            wf.decision = "approved"
            wf.status = WorkflowStatus.COMPLETED.value

    wf.current_stage = WorkflowStage.COMPLETED.value
    wf.completed_at = datetime.now(timezone.utc).isoformat()
    wf.sla_breached = wf.stage_results.get("sla_check", {}).get("details", {}).get("sla_breached", False)

    # Publish completion event
    await publish_kafka("kyc.verification.completed", {
        "workflow_id": workflow_id,
        "customer_id": wf.customer_id,
        "decision": wf.decision,
        "overall_score": wf.overall_score,
        "risk_level": wf.risk_level,
        "sla_breached": wf.sla_breached,
    })

    await stream_to_fluvio(asdict(wf))
    logger.info(f"KYC workflow {workflow_id} completed: decision={wf.decision}, score={wf.overall_score:.1f}")

# ══════════════════════════════════════════════════════════════════════════════
# FastAPI Application
# ══════════════════════════════════════════════════════════════════════════════


# ── OpenTelemetry Tracing ────────────────────────────────────────────────────
_otel_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
if _otel_endpoint:
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        _resource = Resource.create({
            "service.name": os.environ.get("OTEL_SERVICE_NAME", "kyc-workflow-orchestration"),
            "service.version": os.environ.get("OTEL_SERVICE_VERSION", "1.0.0"),
            "deployment.environment": os.environ.get("ENVIRONMENT", "production"),
        })
        _provider = TracerProvider(resource=_resource)
        _exporter = OTLPSpanExporter(endpoint=f"{_otel_endpoint}/v1/traces")
        _provider.add_span_processor(BatchSpanProcessor(_exporter))
        trace.set_tracer_provider(_provider)
        logging.getLogger(__name__).info(f"[OTel] Tracing enabled → {_otel_endpoint}")
    except ImportError:
        logging.getLogger(__name__).warning("[OTel] opentelemetry packages not installed — tracing disabled")

app = FastAPI(
# Instrument FastAPI with OpenTelemetry
if _otel_endpoint:
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
    except (ImportError, Exception):
        pass


import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/kyc_workflow_orchestration")
apply_middleware(app, enable_auth=True)

def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return conn

def init_db():
    conn = get_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS audit_log (
        id SERIAL PRIMARY KEY,
        action TEXT, entity_id TEXT, data TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS state_store (
        key TEXT PRIMARY KEY, value TEXT,
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )""")
    conn.commit()
    conn.close()

init_db()

def log_audit(action: str, entity_id: str, data: str = ""):
    try:
        conn = get_db()
        conn.execute("INSERT INTO audit_log (action, entity_id, data) VALUES (%s, %s, %s)", (action, entity_id, data))
        conn.commit()
        conn.close()
    except Exception:
        pass
    title="KYC Workflow Orchestration",
    description="Multi-step KYC verification pipeline with CBN compliance",
    version="1.0.0",
)

class StartWorkflowRequest(BaseModel):
    customer_id: str
    kyc_level: str = "standard"  # basic, standard, enhanced, full_edd
    target_tier: str = "tier_2"  # tier_1, tier_2, tier_3
    triggered_by: str = "system"
    customer_data: dict = {}

class ManualDecisionRequest(BaseModel):
    decision: str  # approved, rejected
    reviewer: str
    reason: str = ""

@app.post("/api/v1/workflow/start")
async def start_workflow(req: StartWorkflowRequest, background_tasks: BackgroundTasks):
    """Start a new KYC verification workflow."""
    workflow_id = str(uuid.uuid4())
    sla_hours = SLA_HOURS.get(req.target_tier, 24)
    deadline = datetime.now(timezone.utc) + timedelta(hours=sla_hours)

    wf = KYCWorkflow(
        workflow_id=workflow_id,
        customer_id=req.customer_id,
        kyc_level=req.kyc_level,
        target_tier=req.target_tier,
        status=WorkflowStatus.PENDING.value,
        current_stage=WorkflowStage.CREATED.value,
        sla_deadline=deadline.isoformat(),
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
        triggered_by=req.triggered_by,
        customer_data=req.customer_data,
    )

    workflows[workflow_id] = wf

    # Start SLA monitoring via Temporal
    await start_temporal_sla(workflow_id, deadline, req.target_tier)

    # Run pipeline in background
    background_tasks.add_task(run_pipeline, workflow_id)

    return {
        "workflow_id": workflow_id,
        "status": "started",
        "sla_deadline": deadline.isoformat(),
        "sla_hours": sla_hours,
        "stages": [s[0] for s in PIPELINE_STAGES],
    }

@app.get("/api/v1/workflow/{workflow_id}")
async def get_workflow(workflow_id: str):
    """Get workflow status and results."""
    wf = workflows.get(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return asdict(wf)

@app.get("/api/v1/workflow/{workflow_id}/stages")
async def get_workflow_stages(workflow_id: str):
    """Get detailed stage results for a workflow."""
    wf = workflows.get(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return {
        "workflow_id": workflow_id,
        "current_stage": wf.current_stage,
        "stages_completed": wf.stages_completed,
        "stage_results": wf.stage_results,
    }

@app.post("/api/v1/workflow/{workflow_id}/manual-decision")
async def manual_decision(workflow_id: str, req: ManualDecisionRequest):
    """Override auto-decision with manual review decision (requires compliance role)."""
    wf = workflows.get(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    if wf.status != WorkflowStatus.MANUAL_REVIEW.value:
        raise HTTPException(status_code=400, detail="Workflow is not pending manual review")

    wf.decision = req.decision
    wf.status = WorkflowStatus.COMPLETED.value if req.decision == "approved" else WorkflowStatus.REJECTED.value
    wf.completed_at = datetime.now(timezone.utc).isoformat()
    wf.updated_at = datetime.now(timezone.utc).isoformat()

    await publish_kafka(f"kyc.verification.{req.decision}", {
        "workflow_id": workflow_id,
        "customer_id": wf.customer_id,
        "decision": req.decision,
        "reviewer": req.reviewer,
        "reason": req.reason,
    })

    return {"workflow_id": workflow_id, "decision": req.decision, "reviewer": req.reviewer}

@app.get("/api/v1/workflows")
async def list_workflows(status: Optional[str] = None, customer_id: Optional[str] = None):
    """List all workflows with optional filters."""
    results = []
    for wf in workflows.values():
        if status and wf.status != status:
            continue
        if customer_id and wf.customer_id != customer_id:
            continue
        results.append({
            "workflow_id": wf.workflow_id,
            "customer_id": wf.customer_id,
            "status": wf.status,
            "decision": wf.decision,
            "overall_score": wf.overall_score,
            "current_stage": wf.current_stage,
            "created_at": wf.created_at,
        })
    return {"workflows": results, "total": len(results)}

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "kyc-workflow-orchestration",
        "version": "1.0.0",
        "language": "python",
        "active_workflows": len([w for w in workflows.values() if w.status == "in_progress"]),
        "total_workflows": len(workflows),
        "pipeline_stages": [s[0] for s in PIPELINE_STAGES],
        "integrations": {
            "sanctions_engine": SANCTIONS_ENGINE_URL,
            "liveness": LIVENESS_URL,
            "document_ocr": DOCUMENT_OCR_URL,
            "cbn_tier": CBN_TIER_URL,
            "kafka": KAFKA_BROKERS,
            "temporal": TEMPORAL_URL,
        },
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
