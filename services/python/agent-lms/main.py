import httpx
"""
Agent Learning Management System - FastAPI microservice
Training and certification platform for agents with course management, assessments, and progress tracking
"""
import os
import sys
import logging
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query, Path
import sys as _sys2, os as _os2
_sys2.path.insert(0, _os2.path.join(_os2.path.dirname(_os2.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from fastapi.middleware.cors import CORSMiddleware
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
logger = logging.getLogger(__name__)


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
            "service.name": os.environ.get("OTEL_SERVICE_NAME", "agent-lms"),
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


# ── Middleware: Kafka via Dapr ─────────────────────────────────────────────────

DAPR_HTTP_PORT = os.environ.get("DAPR_HTTP_PORT", "3500")

async def publish_kafka(topic: str, data: dict):
    """Publish domain event to Kafka via Dapr sidecar."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            url = f"http://localhost:{DAPR_HTTP_PORT}/v1.0/publish/kafka-pubsub/{topic}"
            resp = await client.post(url, json=data)
            if resp.status_code < 300:
                logger.info(f"Published to {topic}")
            else:
                logger.warning(f"Dapr publish to {topic} returned {resp.status_code}")
    except Exception as e:
        logger.warning(f"Failed to publish to {topic}: {e}")

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

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/agent_lms")
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
    title="Agent Learning Management System",
    description="Training and certification platform for agents with course management, assessments, and progress tracking",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    """Service health check endpoint."""
    return {"status": "healthy", "service": "agent-lms", "version": "1.0.0", "timestamp": datetime.utcnow().isoformat()}

@app.get("/api/v1/courses")
async def list_courses(category: str = None, level: str = None):
    """List available training courses."""
    return {"courses": [], "total": 0, "filters": {"category": category, "level": level}}

@app.get("/api/v1/courses/{course_id}")
async def get_course(course_id: str):
    """Get course details including modules and assessments."""
    return {
        "course_id": course_id,
        "title": "",
        "description": "",
        "modules": [],
        "duration_hours": 0,
        "passing_score": 70,
        "certification": True,
        "prerequisites": [],
    }

@app.post("/api/v1/enrollments")
async def enroll_agent(agent_id: str, course_id: str):
    """Enroll an agent in a training course."""
    return {
        "enrollment_id": f"ENR-{agent_id}-{course_id}",
        "agent_id": agent_id,
        "course_id": course_id,
        "status": "enrolled",
        "enrolled_at": __import__('datetime').datetime.utcnow().isoformat(),
        "deadline": None,
    }

@app.get("/api/v1/agents/{agent_id}/progress")
async def get_agent_progress(agent_id: str):
    """Get agent's overall learning progress and certifications."""
    return {
        "agent_id": agent_id,
        "courses_completed": 0,
        "courses_in_progress": 0,
        "certifications": [],
        "total_hours": 0,
        "average_score": 0,
    }

@app.post("/api/v1/assessments/{assessment_id}/submit")
async def submit_assessment(assessment_id: str, agent_id: str, answers: list):
    """Submit assessment answers for grading."""
    return {
        "assessment_id": assessment_id,
        "agent_id": agent_id,
        "score": 0,
        "passed": False,
        "feedback": [],
        "submitted_at": __import__('datetime').datetime.utcnow().isoformat(),
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)


@app.on_event("startup")
async def startup_event():
    """Register service with Kafka on startup."""
    await publish_kafka("agent.lms.started", {
        "service": "agent-lms",
        "timestamp": datetime.utcnow().isoformat() if "datetime" in dir() else "startup",
    })
