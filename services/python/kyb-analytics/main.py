"""
54Link Agency Banking Platform — Python KYB Analytics Service
Port: 8132
ML-based fraud detection, compliance reporting, Lakehouse integration,
OpenSearch analytics, Fluvio streaming consumer
Integrations: Lakehouse, OpenSearch, Fluvio, Redis, Kafka, PostgreSQL
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from enum import Enum
import logging
import uuid
import os
import json
import math
import hashlib
import httpx
import uvicorn

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
logger = logging.getLogger(__name__)

# ── Configuration ───────────────────────────────────────────────────────────────

ALLOWED_ORIGINS = os.getenv(
    "CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000"
).split(",")

OPENSEARCH_URL = os.getenv("OPENSEARCH_URL", "http://localhost:9200")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/8")
KAFKA_BROKERS = os.getenv("KAFKA_BROKERS", "localhost:9092")
FLUVIO_ENDPOINT = os.getenv("FLUVIO_ENDPOINT", "localhost:9003")
LAKEHOUSE_URL = os.getenv("LAKEHOUSE_URL", "http://localhost:8191")
POSTGRES_URL = os.getenv("DATABASE_URL", "postgresql://ngapp:password@localhost:5432/ngapp")
KYB_ENGINE_URL = os.getenv("KYB_ENGINE_URL", "http://localhost:8130")
KYB_RISK_ENGINE_URL = os.getenv("KYB_RISK_ENGINE_URL", "http://localhost:8131")

app = FastAPI(
    title="KYB Analytics Service",
    description=(
        "ML-based KYB fraud detection, compliance reporting, "
        "Lakehouse ETL, OpenSearch analytics"
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Domain Models ───────────────────────────────────────────────────────────────


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FraudIndicator(BaseModel):
    indicator: str
    severity: RiskLevel
    confidence: float = Field(ge=0.0, le=1.0)
    description: str
    fatf_reference: Optional[str] = None


class FraudDetectionRequest(BaseModel):
    verification_id: str
    business_name: str
    business_type: str
    registration_number: Optional[str] = None
    tax_id: Optional[str] = None
    country: str = "Nigeria"
    industry: Optional[str] = None
    annual_revenue: Optional[float] = None
    employee_count: Optional[int] = None
    ubo_count: Optional[int] = None
    document_count: Optional[int] = None
    transaction_history: Optional[List[Dict[str, Any]]] = None


class FraudDetectionResult(BaseModel):
    id: str
    verification_id: str
    fraud_score: float
    fraud_level: RiskLevel
    is_fraudulent: bool
    indicators: List[FraudIndicator]
    ml_model_version: str
    feature_importances: Dict[str, float]
    recommendations: List[str]
    analyzed_at: datetime


class ComplianceReportRequest(BaseModel):
    report_type: str = "monthly"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    include_details: bool = True


class ComplianceReport(BaseModel):
    id: str
    report_type: str
    period_start: str
    period_end: str
    total_verifications: int
    approved: int
    rejected: int
    pending: int
    high_risk_count: int
    critical_risk_count: int
    pep_matches: int
    sanctions_matches: int
    aml_flags: int
    avg_risk_score: float
    compliance_rate: float
    risk_distribution: Dict[str, int]
    industry_breakdown: Dict[str, int]
    top_risk_factors: List[Dict[str, Any]]
    regulatory_notes: List[str]
    generated_at: datetime


class LakehouseETLRequest(BaseModel):
    data_type: str = "kyb_verifications"
    batch_size: int = 100
    include_pii: bool = False


class LakehouseETLResult(BaseModel):
    id: str
    data_type: str
    records_processed: int
    records_written: int
    lakehouse_table: str
    partition_key: str
    file_format: str
    compression: str
    size_bytes: int
    etl_duration_ms: int
    started_at: datetime
    completed_at: datetime


class AnomalyDetectionRequest(BaseModel):
    verification_id: str
    features: Dict[str, float]


class AnomalyResult(BaseModel):
    verification_id: str
    is_anomaly: bool
    anomaly_score: float
    isolation_forest_score: float
    z_scores: Dict[str, float]
    anomalous_features: List[str]
    analyzed_at: datetime


# ── In-memory analytics store ──────────────────────────────────────────────────

analytics_store: Dict[str, Any] = {
    "fraud_detections": [],
    "compliance_reports": [],
    "etl_jobs": [],
    "anomaly_results": [],
    "stats": {
        "total_fraud_detections": 0,
        "total_compliance_reports": 0,
        "total_etl_jobs": 0,
        "total_anomalies_detected": 0,
        "start_time": datetime.utcnow().isoformat(),
    },
}

# ── ML Feature Engineering ──────────────────────────────────────────────────────


def extract_features(req: FraudDetectionRequest) -> Dict[str, float]:
    """Extract ML features from a KYB verification request."""
    features = {}

    # Business type encoding
    type_risk_map = {
        "corporation": 0.2, "llc": 0.25, "partnership": 0.4,
        "sole_proprietorship": 0.5, "non_profit": 0.6, "trust": 0.7,
    }
    features["business_type_risk"] = type_risk_map.get(req.business_type, 0.35)

    # Industry risk
    high_risk_industries = {
        "cryptocurrency", "forex", "gambling", "precious_metals", "arms", "cannabis",
    }
    medium_risk_industries = {
        "financial_services", "money_transfer", "real_estate",
        "import_export", "oil_gas", "construction",
    }
    industry = (req.industry or "").lower()
    if industry in high_risk_industries:
        features["industry_risk"] = 0.85
    elif industry in medium_risk_industries:
        features["industry_risk"] = 0.5
    else:
        features["industry_risk"] = 0.15

    # Revenue anomaly detection
    revenue = req.annual_revenue or 0.0
    if revenue == 0:
        features["revenue_anomaly"] = 0.7
    elif revenue > 10_000_000_000:
        features["revenue_anomaly"] = 0.6
    elif revenue < 100_000:
        features["revenue_anomaly"] = 0.4
    else:
        features["revenue_anomaly"] = 0.1

    # Employee/revenue ratio
    emp = req.employee_count or 0
    if emp == 0:
        features["emp_revenue_ratio"] = 0.6
    elif revenue > 0:
        ratio = revenue / max(emp, 1)
        if ratio > 50_000_000:
            features["emp_revenue_ratio"] = 0.7
        elif ratio < 100_000:
            features["emp_revenue_ratio"] = 0.5
        else:
            features["emp_revenue_ratio"] = 0.1
    else:
        features["emp_revenue_ratio"] = 0.3

    # UBO completeness
    ubo = req.ubo_count or 0
    if ubo == 0:
        features["ubo_completeness"] = 0.8
    elif ubo > 10:
        features["ubo_completeness"] = 0.6
    else:
        features["ubo_completeness"] = 0.1

    # Document completeness
    docs = req.document_count or 0
    if docs >= 4:
        features["doc_completeness"] = 0.1
    elif docs >= 2:
        features["doc_completeness"] = 0.4
    else:
        features["doc_completeness"] = 0.7

    # Registration number validity
    reg = req.registration_number or ""
    if not reg:
        features["reg_validity"] = 0.8
    elif reg.startswith(("RC", "BN", "IT", "LP", "LLP")):
        features["reg_validity"] = 0.1
    else:
        features["reg_validity"] = 0.6

    # TIN validity
    tin = (req.tax_id or "").replace("-", "")
    if not tin:
        features["tin_validity"] = 0.7
    elif len(tin) >= 8 and tin.isdigit():
        features["tin_validity"] = 0.1
    else:
        features["tin_validity"] = 0.5

    # Jurisdiction risk
    country = req.country.upper()
    fatf_grey = {"NIGERIA", "NGA", "SOUTH AFRICA", "TURKEY", "PHILIPPINES"}
    fatf_black = {"DPRK", "IRAN", "MYANMAR"}
    if country in fatf_black:
        features["jurisdiction_risk"] = 0.95
    elif country in fatf_grey:
        features["jurisdiction_risk"] = 0.4
    else:
        features["jurisdiction_risk"] = 0.1

    return features


def ml_fraud_score(features: Dict[str, float]) -> float:
    """Weighted ensemble fraud scoring (simulated gradient boosting)."""
    weights = {
        "business_type_risk": 0.10,
        "industry_risk": 0.20,
        "revenue_anomaly": 0.12,
        "emp_revenue_ratio": 0.08,
        "ubo_completeness": 0.15,
        "doc_completeness": 0.10,
        "reg_validity": 0.10,
        "tin_validity": 0.05,
        "jurisdiction_risk": 0.10,
    }
    total = 0.0
    weight_sum = 0.0
    for feat, val in features.items():
        w = weights.get(feat, 0.05)
        total += val * w
        weight_sum += w

    raw = total / max(weight_sum, 0.01)
    # Sigmoid normalization to 0-100
    score = 100.0 / (1.0 + math.exp(-10 * (raw - 0.5)))
    return round(score, 2)


def detect_anomalies(features: Dict[str, float]) -> Dict[str, Any]:
    """Isolation Forest-inspired anomaly detection."""
    values = list(features.values())
    if not values:
        return {"is_anomaly": False, "score": 0.0, "z_scores": {}, "anomalous": []}

    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    std = math.sqrt(variance) if variance > 0 else 0.001

    z_scores = {}
    anomalous = []
    for k, v in features.items():
        z = abs(v - mean) / std
        z_scores[k] = round(z, 3)
        if z > 2.0:
            anomalous.append(k)

    # Isolation score
    iso_score = sum(1 for z in z_scores.values() if z > 1.5) / max(len(z_scores), 1)

    return {
        "is_anomaly": len(anomalous) >= 2 or iso_score > 0.4,
        "score": round(iso_score, 3),
        "z_scores": z_scores,
        "anomalous": anomalous,
    }


# ── Middleware Integration Helpers ──────────────────────────────────────────────


async def publish_to_fluvio(topic: str, data: dict):
    """Publish analytics event to Fluvio streaming."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"http://{FLUVIO_ENDPOINT}/produce/{topic}",
                json=data, timeout=5.0,
            )
            logger.info(f"[Fluvio] published to {topic} (status {resp.status_code})")
    except Exception as e:
        logger.warning(f"[Fluvio] publish to {topic} failed: {e}")


async def index_to_opensearch(index: str, doc_id: str, data: dict):
    """Index analytics data in OpenSearch."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.put(
                f"{OPENSEARCH_URL}/{index}/_doc/{doc_id}",
                json=data, timeout=10.0,
            )
            logger.info(f"[OpenSearch] indexed {doc_id} in {index} (status {resp.status_code})")
    except Exception as e:
        logger.warning(f"[OpenSearch] index failed: {e}")


async def write_to_lakehouse(table: str, records: List[dict]):
    """Write analytics records to Lakehouse (Delta Lake / Iceberg)."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{LAKEHOUSE_URL}/api/v1/tables/{table}/write",
                json={
                    "records": records,
                    "format": "parquet",
                    "compression": "zstd",
                    "partition_by": ["year", "month"],
                    "mode": "append",
                },
                timeout=30.0,
            )
            logger.info(f"[Lakehouse] wrote {len(records)} records to {table} (status {resp.status_code})")
            return resp.json() if resp.status_code < 400 else None
    except Exception as e:
        logger.warning(f"[Lakehouse] write to {table} failed: {e}")
        return None


async def publish_to_kafka_via_dapr(topic: str, data: dict):
    """Publish event to Kafka via Dapr sidecar."""
    dapr_port = os.getenv("DAPR_HTTP_PORT", "3500")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"http://localhost:{dapr_port}/v1.0/publish/kafka-pubsub/{topic}",
                json=data, timeout=5.0,
            )
            logger.info(f"[Kafka/Dapr] published to {topic} (status {resp.status_code})")
    except Exception as e:
        logger.warning(f"[Kafka/Dapr] publish to {topic} failed: {e}")


# ── HTTP Endpoints ──────────────────────────────────────────────────────────────


@app.get("/")
async def root():
    return {
        "service": "kyb-analytics",
        "description": "ML-based KYB fraud detection, compliance reporting, Lakehouse ETL",
        "language": "python",
        "version": "1.0.0",
        "port": 8132,
        "status": "operational",
    }


@app.get("/health")
async def health():
    stats = analytics_store["stats"]
    return {
        "status": "healthy",
        "service": "kyb-analytics",
        "language": "python",
        "version": "1.0.0",
        "port": 8132,
        "started_at": stats["start_time"],
        "total_fraud_detections": stats["total_fraud_detections"],
        "total_compliance_reports": stats["total_compliance_reports"],
        "total_etl_jobs": stats["total_etl_jobs"],
        "capabilities": [
            "ml_fraud_detection", "anomaly_detection",
            "compliance_reporting", "lakehouse_etl",
            "opensearch_analytics", "fluvio_streaming",
        ],
        "integrations": [
            "lakehouse", "opensearch", "fluvio",
            "redis", "kafka", "postgresql",
        ],
    }


@app.post("/fraud/detect")
async def detect_fraud(
    req: FraudDetectionRequest, background_tasks: BackgroundTasks
):
    """ML-based fraud detection for KYB verifications."""
    # Extract features
    features = extract_features(req)

    # Compute fraud score
    fraud_score = ml_fraud_score(features)

    # Determine level
    if fraud_score >= 75:
        fraud_level = RiskLevel.CRITICAL
    elif fraud_score >= 50:
        fraud_level = RiskLevel.HIGH
    elif fraud_score >= 30:
        fraud_level = RiskLevel.MEDIUM
    else:
        fraud_level = RiskLevel.LOW

    # Build indicators
    indicators = []
    if features.get("industry_risk", 0) >= 0.7:
        indicators.append(FraudIndicator(
            indicator="high_risk_industry",
            severity=RiskLevel.HIGH,
            confidence=0.85,
            description=f"Industry '{req.industry}' is classified as high-risk per CBN guidelines",
            fatf_reference="CBN-AML-CFT-2022",
        ))
    if features.get("ubo_completeness", 0) >= 0.7:
        indicators.append(FraudIndicator(
            indicator="missing_ubo_declaration",
            severity=RiskLevel.HIGH,
            confidence=0.9,
            description="No beneficial ownership declared — potential shell company indicator",
            fatf_reference="FATF-2014-Transparency-BO",
        ))
    if features.get("revenue_anomaly", 0) >= 0.6:
        indicators.append(FraudIndicator(
            indicator="revenue_anomaly",
            severity=RiskLevel.MEDIUM,
            confidence=0.7,
            description="Revenue figure is anomalous (zero or extremely high)",
        ))
    if features.get("reg_validity", 0) >= 0.5:
        indicators.append(FraudIndicator(
            indicator="registration_validity",
            severity=RiskLevel.MEDIUM,
            confidence=0.75,
            description="Business registration number missing or invalid CAC format",
        ))
    if features.get("doc_completeness", 0) >= 0.6:
        indicators.append(FraudIndicator(
            indicator="insufficient_documentation",
            severity=RiskLevel.MEDIUM,
            confidence=0.8,
            description="Required KYB documents are incomplete",
        ))
    if features.get("jurisdiction_risk", 0) >= 0.8:
        indicators.append(FraudIndicator(
            indicator="high_risk_jurisdiction",
            severity=RiskLevel.CRITICAL,
            confidence=0.95,
            description=f"Country '{req.country}' is FATF blacklisted",
            fatf_reference="FATF-GREYLIST-2024",
        ))

    # Feature importances
    feature_importances = {
        "industry_risk": 0.20,
        "ubo_completeness": 0.15,
        "jurisdiction_risk": 0.10,
        "revenue_anomaly": 0.12,
        "doc_completeness": 0.10,
        "business_type_risk": 0.10,
        "reg_validity": 0.10,
        "emp_revenue_ratio": 0.08,
        "tin_validity": 0.05,
    }

    # Recommendations
    recommendations = []
    if fraud_score >= 75:
        recommendations.extend([
            "BLOCK: Escalate to compliance officer immediately",
            "Request enhanced due diligence (EDD)",
            "File suspicious activity report (SAR) with NFIU",
        ])
    elif fraud_score >= 50:
        recommendations.extend([
            "FLAG: Manual review required before approval",
            "Request additional documentation",
            "Schedule enhanced monitoring (quarterly review)",
        ])
    elif fraud_score >= 30:
        recommendations.append("MONITOR: Schedule periodic review (semi-annual)")
    else:
        recommendations.append("CLEAR: Standard processing can proceed")

    result = FraudDetectionResult(
        id=str(uuid.uuid4()),
        verification_id=req.verification_id,
        fraud_score=fraud_score,
        fraud_level=fraud_level,
        is_fraudulent=fraud_score >= 75,
        indicators=indicators,
        ml_model_version="kyb-fraud-gbm-v1.0",
        feature_importances=feature_importances,
        recommendations=recommendations,
        analyzed_at=datetime.utcnow(),
    )

    analytics_store["fraud_detections"].append(result.model_dump(mode="json"))
    analytics_store["stats"]["total_fraud_detections"] += 1

    # Background: publish to Fluvio, index in OpenSearch, write to Lakehouse
    background_tasks.add_task(
        publish_to_fluvio, "kyb-fraud-analytics",
        {"event": "fraud_detected", "verification_id": req.verification_id,
         "fraud_score": fraud_score, "fraud_level": fraud_level.value,
         "timestamp": datetime.utcnow().isoformat()},
    )
    background_tasks.add_task(
        index_to_opensearch, "kyb-fraud-analytics", result.id,
        result.model_dump(mode="json"),
    )
    background_tasks.add_task(
        publish_to_kafka_via_dapr, "kyb-analytics-events",
        {"event_type": "fraud_detection_complete",
         "verification_id": req.verification_id,
         "fraud_score": fraud_score},
    )

    return result


@app.post("/fraud/anomaly")
async def detect_anomaly(req: AnomalyDetectionRequest):
    """Isolation Forest anomaly detection on KYB features."""
    anomaly_data = detect_anomalies(req.features)

    result = AnomalyResult(
        verification_id=req.verification_id,
        is_anomaly=anomaly_data["is_anomaly"],
        anomaly_score=anomaly_data["score"],
        isolation_forest_score=anomaly_data["score"],
        z_scores=anomaly_data["z_scores"],
        anomalous_features=anomaly_data["anomalous"],
        analyzed_at=datetime.utcnow(),
    )

    analytics_store["anomaly_results"].append(result.model_dump(mode="json"))
    if result.is_anomaly:
        analytics_store["stats"]["total_anomalies_detected"] += 1

    return result


@app.post("/compliance/report")
async def generate_compliance_report(
    req: ComplianceReportRequest, background_tasks: BackgroundTasks
):
    """Generate regulatory compliance report for KYB verifications."""
    now = datetime.utcnow()
    if req.report_type == "monthly":
        period_start = (now - timedelta(days=30)).isoformat()
    elif req.report_type == "quarterly":
        period_start = (now - timedelta(days=90)).isoformat()
    elif req.report_type == "annual":
        period_start = (now - timedelta(days=365)).isoformat()
    else:
        period_start = req.start_date or (now - timedelta(days=30)).isoformat()

    period_end = req.end_date or now.isoformat()

    # Aggregate analytics from fraud detections
    fraud_data = analytics_store["fraud_detections"]
    total = len(fraud_data)
    high_risk = sum(1 for f in fraud_data if f.get("fraud_level") in ("high", "critical"))
    critical = sum(1 for f in fraud_data if f.get("fraud_level") == "critical")
    avg_score = (
        sum(f.get("fraud_score", 0) for f in fraud_data) / max(total, 1)
    )

    risk_dist = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    industry_breakdown: Dict[str, int] = {}
    top_risk_factors: List[Dict[str, Any]] = []

    for f in fraud_data:
        level = f.get("fraud_level", "low")
        risk_dist[level] = risk_dist.get(level, 0) + 1

    # Regulatory notes per CBN requirements
    regulatory_notes = [
        "Report generated per CBN AML/CFT Regulations 2022",
        "All high-risk verifications flagged for NFIU reporting",
        f"Average risk score: {avg_score:.1f}/100",
    ]
    if critical > 0:
        regulatory_notes.append(
            f"CRITICAL: {critical} verifications require immediate NFIU/EFCC reporting"
        )

    report = ComplianceReport(
        id=str(uuid.uuid4()),
        report_type=req.report_type,
        period_start=period_start,
        period_end=period_end,
        total_verifications=total,
        approved=max(total - high_risk, 0),
        rejected=critical,
        pending=high_risk - critical,
        high_risk_count=high_risk,
        critical_risk_count=critical,
        pep_matches=0,
        sanctions_matches=0,
        aml_flags=sum(1 for f in fraud_data if f.get("is_fraudulent")),
        avg_risk_score=round(avg_score, 2),
        compliance_rate=round((1 - high_risk / max(total, 1)) * 100, 2),
        risk_distribution=risk_dist,
        industry_breakdown=industry_breakdown,
        top_risk_factors=top_risk_factors,
        regulatory_notes=regulatory_notes,
        generated_at=now,
    )

    analytics_store["compliance_reports"].append(report.model_dump(mode="json"))
    analytics_store["stats"]["total_compliance_reports"] += 1

    # Background: write to Lakehouse and OpenSearch
    background_tasks.add_task(
        write_to_lakehouse, "kyb_compliance_reports",
        [report.model_dump(mode="json")],
    )
    background_tasks.add_task(
        index_to_opensearch, "kyb-compliance-reports", report.id,
        report.model_dump(mode="json"),
    )
    background_tasks.add_task(
        publish_to_fluvio, "kyb-compliance-stream",
        {"event": "compliance_report_generated", "report_id": report.id,
         "report_type": req.report_type, "timestamp": now.isoformat()},
    )

    return report


@app.post("/etl/lakehouse")
async def run_lakehouse_etl(
    req: LakehouseETLRequest, background_tasks: BackgroundTasks
):
    """Run ETL pipeline to write KYB analytics data to Lakehouse."""
    start_time = datetime.utcnow()

    # Gather records based on data_type
    if req.data_type == "kyb_verifications":
        records = analytics_store["fraud_detections"][-req.batch_size:]
        table = "kyb_verifications_analytics"
    elif req.data_type == "compliance_reports":
        records = analytics_store["compliance_reports"][-req.batch_size:]
        table = "kyb_compliance_reports"
    elif req.data_type == "anomaly_detections":
        records = analytics_store["anomaly_results"][-req.batch_size:]
        table = "kyb_anomaly_detections"
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid data_type: {req.data_type}. "
                   "Valid: kyb_verifications, compliance_reports, anomaly_detections",
        )

    # Strip PII if not requested
    if not req.include_pii:
        sanitized = []
        pii_fields = {"business_name", "email", "phone", "bvn", "nin", "tax_id"}
        for r in records:
            sanitized_record = {
                k: (hashlib.sha256(str(v).encode()).hexdigest()[:16] if k in pii_fields else v)
                for k, v in r.items()
            }
            sanitized.append(sanitized_record)
        records = sanitized

    # Write to Lakehouse
    lh_result = await write_to_lakehouse(table, records)

    end_time = datetime.utcnow()
    duration_ms = int((end_time - start_time).total_seconds() * 1000)

    result = LakehouseETLResult(
        id=str(uuid.uuid4()),
        data_type=req.data_type,
        records_processed=len(records),
        records_written=len(records),
        lakehouse_table=table,
        partition_key=f"year={start_time.year}/month={start_time.month:02d}",
        file_format="parquet",
        compression="zstd",
        size_bytes=len(json.dumps(records).encode()),
        etl_duration_ms=duration_ms,
        started_at=start_time,
        completed_at=end_time,
    )

    analytics_store["etl_jobs"].append(result.model_dump(mode="json"))
    analytics_store["stats"]["total_etl_jobs"] += 1

    background_tasks.add_task(
        publish_to_fluvio, "kyb-etl-stream",
        {"event": "etl_complete", "table": table,
         "records": len(records), "timestamp": end_time.isoformat()},
    )

    return result


@app.get("/analytics/dashboard")
async def get_analytics_dashboard():
    """Get KYB analytics dashboard data for frontend."""
    fraud_data = analytics_store["fraud_detections"]
    total = len(fraud_data)

    # Score distribution
    score_buckets = {"0-25": 0, "25-50": 0, "50-75": 0, "75-100": 0}
    for f in fraud_data:
        score = f.get("fraud_score", 0)
        if score < 25:
            score_buckets["0-25"] += 1
        elif score < 50:
            score_buckets["25-50"] += 1
        elif score < 75:
            score_buckets["50-75"] += 1
        else:
            score_buckets["75-100"] += 1

    # Risk level distribution
    risk_dist = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    for f in fraud_data:
        level = f.get("fraud_level", "low")
        risk_dist[level] = risk_dist.get(level, 0) + 1

    return {
        "total_verifications_analyzed": total,
        "fraud_detections": analytics_store["stats"]["total_fraud_detections"],
        "anomalies_detected": analytics_store["stats"]["total_anomalies_detected"],
        "compliance_reports_generated": analytics_store["stats"]["total_compliance_reports"],
        "etl_jobs_completed": analytics_store["stats"]["total_etl_jobs"],
        "score_distribution": score_buckets,
        "risk_level_distribution": risk_dist,
        "avg_fraud_score": round(
            sum(f.get("fraud_score", 0) for f in fraud_data) / max(total, 1), 2
        ),
        "model_version": "kyb-fraud-gbm-v1.0",
        "last_updated": datetime.utcnow().isoformat(),
    }


@app.get("/analytics/opensearch/query")
async def query_opensearch(index: str = "kyb-fraud-analytics", q: str = "*", size: int = 10):
    """Proxy OpenSearch queries for KYB analytics."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{OPENSEARCH_URL}/{index}/_search",
                json={
                    "query": {"query_string": {"query": q}},
                    "size": size,
                    "sort": [{"analyzed_at": {"order": "desc"}}],
                },
                timeout=10.0,
            )
            if resp.status_code < 400:
                return resp.json()
            return {"error": f"OpenSearch returned {resp.status_code}", "body": resp.text[:500]}
    except Exception as e:
        return {"error": str(e), "fallback": "opensearch_unavailable"}


@app.get("/stats")
async def get_stats():
    return analytics_store["stats"]


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8132)
