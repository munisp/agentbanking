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

# --- PostgreSQL Persistence ---
import asyncpg
from typing import Optional

_pg_pool: Optional[asyncpg.Pool] = None

async def get_pg_pool() -> Optional[asyncpg.Pool]:
    global _pg_pool
    if _pg_pool is None:
        try:
            _pg_pool = await asyncpg.create_pool(
                dsn=os.environ.get("DATABASE_URL", "postgresql://localhost:5432/agentbanking"),
                min_size=2, max_size=10, command_timeout=10
            )
            await _pg_pool.execute("""
                CREATE TABLE IF NOT EXISTS service_state (
                    key TEXT PRIMARY KEY,
                    value JSONB NOT NULL DEFAULT '{}',
                    service TEXT NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
        except Exception:
            _pg_pool = None
    return _pg_pool

async def pg_get(key: str, service: str):
    pool = await get_pg_pool()
    if pool:
        row = await pool.fetchrow(
            "SELECT value FROM service_state WHERE key = $1 AND service = $2", key, service
        )
        return row["value"] if row else None
    return None

async def pg_set(key: str, value, service: str):
    pool = await get_pg_pool()
    if pool:
        import json
        await pool.execute(
            "INSERT INTO service_state (key, value, service, updated_at) VALUES ($1, $2::jsonb, $3, NOW()) "
            "ON CONFLICT (key) DO UPDATE SET value = $2::jsonb, updated_at = NOW()",
            key, json.dumps(value) if not isinstance(value, str) else value, service
        )
# --- End PostgreSQL Persistence ---


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

app = FastAPI(

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/agent_lms")

@app.on_event("startup")
async def _init_pg_pool():
    await get_pg_pool()

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
    # Load persisted state from PostgreSQL
    _pg_cached = await pg_get("list_courses", "agent-lms")
    if _pg_cached is not None:
        import json as _json
        try:
            return _json.loads(_pg_cached) if isinstance(_pg_cached, str) else _pg_cached
        except Exception:
            pass

    return {"courses": [], "total": 0, "filters": {"category": category, "level": level}}

@app.get("/api/v1/courses/{course_id}")
async def get_course(course_id: str):
    """Get course details including modules and assessments."""
    # Load persisted state from PostgreSQL
    _pg_cached = await pg_get("get_course", "agent-lms")
    if _pg_cached is not None:
        import json as _json
        try:
            return _json.loads(_pg_cached) if isinstance(_pg_cached, str) else _pg_cached
        except Exception:
            pass

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
    # Persist operation result to PostgreSQL
    import json as _json, time as _time
    await pg_set("enroll_agent_" + str(int(_time.time() * 1000)), _json.dumps({"action": "enroll_agent", "timestamp": _time.time()}), "agent-lms")

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
    # Load persisted state from PostgreSQL
    _pg_cached = await pg_get("get_agent_progress", "agent-lms")
    if _pg_cached is not None:
        import json as _json
        try:
            return _json.loads(_pg_cached) if isinstance(_pg_cached, str) else _pg_cached
        except Exception:
            pass

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
    # Persist operation result to PostgreSQL
    import json as _json, time as _time
    await pg_set("submit_assessment_" + str(int(_time.time() * 1000)), _json.dumps({"action": "submit_assessment", "timestamp": _time.time()}), "agent-lms")

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
