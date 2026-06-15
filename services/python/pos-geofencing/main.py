"""
POS Geofencing - FastAPI microservice
Location-based POS terminal management with geofence alerts, territory mapping,
proximity services, and real-time boundary violation detection.
"""
import os
import sys
import math
import json
import uuid
import signal
import atexit
import logging
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Depends
import sys as _sys2, os as _os2
_sys2.path.insert(0, _os2.path.join(_os2.path.dirname(_os2.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import asyncpg

# ── Graceful Shutdown ────────────────────────────────────────────────────────

_shutdown_handlers: list = []

def register_shutdown(handler):
    _shutdown_handlers.append(handler)

def _graceful_shutdown(signum, frame):
    sig_name = signal.Signals(signum).name if hasattr(signal, "Signals") else str(signum)
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

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgres://postgres:postgres@localhost:5432/pos_geofencing"
)

_pool: Optional[asyncpg.Pool] = None

async def get_db_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
        register_shutdown(lambda: None)
    return _pool

# ── FastAPI App ──────────────────────────────────────────────────────────────


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
            "service.name": os.environ.get("OTEL_SERVICE_NAME", "pos-geofencing"),
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
    title="POS Geofencing",
    description="Location-based POS terminal management with geofence alerts, "
    "territory mapping, proximity services, and boundary violation detection.",
    version="2.0.0",
)
apply_middleware(app, enable_auth=True)
# Instrument FastAPI with OpenTelemetry
if _otel_endpoint:
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
    except (ImportError, Exception):
        pass


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── DB Schema Init ───────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS geofences (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name VARCHAR(128) NOT NULL,
                description TEXT,
                center_lat DOUBLE PRECISION NOT NULL,
                center_lng DOUBLE PRECISION NOT NULL,
                radius_m DOUBLE PRECISION NOT NULL CHECK (radius_m > 0 AND radius_m <= 100000),
                zone_type VARCHAR(32) NOT NULL DEFAULT 'circular',
                agent_id VARCHAR(64),
                region VARCHAR(64),
                status VARCHAR(20) NOT NULL DEFAULT 'active',
                metadata JSONB DEFAULT '{}',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS geofence_events (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                geofence_id UUID REFERENCES geofences(id),
                terminal_id VARCHAR(64) NOT NULL,
                event_type VARCHAR(20) NOT NULL,
                lat DOUBLE PRECISION NOT NULL,
                lng DOUBLE PRECISION NOT NULL,
                distance_to_center_m DOUBLE PRECISION NOT NULL,
                distance_to_boundary_m DOUBLE PRECISION NOT NULL,
                is_inside BOOLEAN NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS terminal_locations (
                terminal_id VARCHAR(64) PRIMARY KEY,
                lat DOUBLE PRECISION NOT NULL,
                lng DOUBLE PRECISION NOT NULL,
                accuracy_m DOUBLE PRECISION,
                speed_kmh DOUBLE PRECISION,
                heading DOUBLE PRECISION,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_gf_events_terminal
            ON geofence_events(terminal_id, created_at DESC)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_gf_events_fence
            ON geofence_events(geofence_id, created_at DESC)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_gf_status ON geofences(status)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_gf_agent ON geofences(agent_id)
        """)
    logger.info("[startup] Geofence tables initialized")

# ── Haversine Distance ───────────────────────────────────────────────────────

def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

# ── Pydantic Models ──────────────────────────────────────────────────────────

class GeofenceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: Optional[str] = None
    center_lat: float = Field(..., ge=-90, le=90)
    center_lng: float = Field(..., ge=-180, le=180)
    radius_m: float = Field(..., gt=0, le=100_000)
    zone_type: str = Field(default="circular", pattern="^(circular|polygon)$")
    agent_id: Optional[str] = None
    region: Optional[str] = None

class LocationCheck(BaseModel):
    terminal_id: str = Field(..., min_length=1, max_length=64)
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    accuracy_m: Optional[float] = None
    speed_kmh: Optional[float] = None
    heading: Optional[float] = None

class GeofenceUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=128)
    radius_m: Optional[float] = Field(None, gt=0, le=100_000)
    status: Optional[str] = Field(None, pattern="^(active|inactive|archived)$")
    description: Optional[str] = None

# ── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {
            "status": "healthy",
            "service": "pos-geofencing",
            "version": "2.0.0",
            "database": "connected",
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        return {"status": "degraded", "service": "pos-geofencing", "error": str(e)}

@app.post("/api/v1/geofence/create")
async def create_geofence(body: GeofenceCreate):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO geofences (name, description, center_lat, center_lng, radius_m,
                                   zone_type, agent_id, region)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING *
            """,
            body.name, body.description, body.center_lat, body.center_lng,
            body.radius_m, body.zone_type, body.agent_id, body.region,
        )
        logger.info(f"[geofence] Created geofence {row['id']} '{body.name}'")
        return dict(row)

@app.post("/api/v1/geofence/check")
async def check_location(body: LocationCheck):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO terminal_locations (terminal_id, lat, lng, accuracy_m, speed_kmh, heading, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, NOW())
            ON CONFLICT (terminal_id) DO UPDATE
            SET lat=$2, lng=$3, accuracy_m=$4, speed_kmh=$5, heading=$6, updated_at=NOW()
            """,
            body.terminal_id, body.lat, body.lng,
            body.accuracy_m, body.speed_kmh, body.heading,
        )

        fences = await conn.fetch(
            "SELECT * FROM geofences WHERE status = 'active'"
        )

        results = []
        violations = []
        for fence in fences:
            dist = haversine_m(body.lat, body.lng, fence["center_lat"], fence["center_lng"])
            inside = dist <= fence["radius_m"]
            boundary_dist = fence["radius_m"] - dist

            results.append({
                "geofence_id": str(fence["id"]),
                "name": fence["name"],
                "distance_to_center_m": round(dist, 2),
                "distance_to_boundary_m": round(abs(boundary_dist), 2),
                "is_inside": inside,
            })

            event_type = "inside" if inside else "violation"
            if not inside:
                violations.append(fence["name"])

            await conn.execute(
                """
                INSERT INTO geofence_events
                (geofence_id, terminal_id, event_type, lat, lng,
                 distance_to_center_m, distance_to_boundary_m, is_inside)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                fence["id"], body.terminal_id, event_type,
                body.lat, body.lng, round(dist, 2),
                round(abs(boundary_dist), 2), inside,
            )

        nearest = min(results, key=lambda r: r["distance_to_center_m"]) if results else None

        return {
            "terminal_id": body.terminal_id,
            "location": {"lat": body.lat, "lng": body.lng},
            "checked_at": datetime.utcnow().isoformat(),
            "geofences_checked": len(results),
            "violations": violations,
            "in_any_zone": any(r["is_inside"] for r in results),
            "nearest_zone": nearest,
            "details": results,
        }

@app.get("/api/v1/geofence/alerts")
async def get_alerts(
    agent_id: Optional[str] = None,
    terminal_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        base_query = """
            SELECT e.*, g.name as geofence_name, g.agent_id
            FROM geofence_events e
            JOIN geofences g ON e.geofence_id = g.id
            WHERE e.event_type = 'violation'
        """
        params: list = []
        idx = 1

        if agent_id:
            base_query += f" AND g.agent_id = ${idx}"
            params.append(agent_id)
            idx += 1
        if terminal_id:
            base_query += f" AND e.terminal_id = ${idx}"
            params.append(terminal_id)
            idx += 1

        count_query = f"SELECT COUNT(*) FROM ({base_query}) sub"
        total = await conn.fetchval(count_query, *params)

        base_query += f" ORDER BY e.created_at DESC LIMIT ${idx} OFFSET ${idx + 1}"
        params.extend([limit, offset])

        rows = await conn.fetch(base_query, *params)
        return {
            "alerts": [dict(r) for r in rows],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

@app.get("/api/v1/geofence/zones")
async def list_zones(
    region: Optional[str] = None,
    status: str = "active",
    limit: int = 50,
    offset: int = 0,
):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        params: list = [status]
        query = "SELECT * FROM geofences WHERE status = $1"
        idx = 2

        if region:
            query += f" AND region = ${idx}"
            params.append(region)
            idx += 1

        count_q = f"SELECT COUNT(*) FROM ({query}) sub"
        total = await conn.fetchval(count_q, *params)

        query += f" ORDER BY created_at DESC LIMIT ${idx} OFFSET ${idx + 1}"
        params.extend([limit, offset])
        rows = await conn.fetch(query, *params)

        return {
            "zones": [dict(r) for r in rows],
            "total": total,
            "region": region,
            "limit": limit,
            "offset": offset,
        }

@app.get("/api/v1/geofence/{geofence_id}")
async def get_geofence(geofence_id: str):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM geofences WHERE id = $1", uuid.UUID(geofence_id)
        )
        if not row:
            raise HTTPException(status_code=404, detail="Geofence not found")
        event_count = await conn.fetchval(
            "SELECT COUNT(*) FROM geofence_events WHERE geofence_id = $1",
            uuid.UUID(geofence_id),
        )
        violation_count = await conn.fetchval(
            "SELECT COUNT(*) FROM geofence_events WHERE geofence_id = $1 AND event_type = 'violation'",
            uuid.UUID(geofence_id),
        )
        return {
            **dict(row),
            "event_count": event_count,
            "violation_count": violation_count,
        }

@app.put("/api/v1/geofence/{geofence_id}")
async def update_geofence(geofence_id: str, body: GeofenceUpdate):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT * FROM geofences WHERE id = $1", uuid.UUID(geofence_id)
        )
        if not existing:
            raise HTTPException(status_code=404, detail="Geofence not found")

        updates = {k: v for k, v in body.dict().items() if v is not None}
        if not updates:
            return dict(existing)

        set_parts = []
        params = [uuid.UUID(geofence_id)]
        idx = 2
        for k, v in updates.items():
            set_parts.append(f"{k} = ${idx}")
            params.append(v)
            idx += 1
        set_parts.append("updated_at = NOW()")

        query = f"UPDATE geofences SET {', '.join(set_parts)} WHERE id = $1 RETURNING *"
        row = await conn.fetchrow(query, *params)
        return dict(row)

@app.delete("/api/v1/geofence/{geofence_id}")
async def delete_geofence(geofence_id: str):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE geofences SET status = 'archived', updated_at = NOW() WHERE id = $1",
            uuid.UUID(geofence_id),
        )
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Geofence not found")
        return {"archived": True, "geofence_id": geofence_id}

@app.get("/api/v1/geofence/terminal/{terminal_id}/history")
async def terminal_geofence_history(
    terminal_id: str, limit: int = 50, offset: int = 0
):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM geofence_events WHERE terminal_id = $1",
            terminal_id,
        )
        rows = await conn.fetch(
            """
            SELECT e.*, g.name as geofence_name
            FROM geofence_events e
            JOIN geofences g ON e.geofence_id = g.id
            WHERE e.terminal_id = $1
            ORDER BY e.created_at DESC
            LIMIT $2 OFFSET $3
            """,
            terminal_id, limit, offset,
        )
        return {
            "terminal_id": terminal_id,
            "events": [dict(r) for r in rows],
            "total": total,
        }

@app.get("/api/v1/geofence/stats")
async def geofence_stats():
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        total_zones = await conn.fetchval("SELECT COUNT(*) FROM geofences")
        active_zones = await conn.fetchval(
            "SELECT COUNT(*) FROM geofences WHERE status = 'active'"
        )
        total_events = await conn.fetchval("SELECT COUNT(*) FROM geofence_events")
        violations_today = await conn.fetchval(
            "SELECT COUNT(*) FROM geofence_events WHERE event_type = 'violation' AND created_at >= CURRENT_DATE"
        )
        unique_terminals = await conn.fetchval(
            "SELECT COUNT(DISTINCT terminal_id) FROM terminal_locations"
        )
        return {
            "total_zones": total_zones,
            "active_zones": active_zones,
            "total_events": total_events,
            "violations_today": violations_today,
            "tracked_terminals": unique_terminals,
        }

@app.post("/api/v1/geofence/bulk-check")
async def bulk_check_terminals():
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        terminals = await conn.fetch("SELECT * FROM terminal_locations")
        fences = await conn.fetch("SELECT * FROM geofences WHERE status = 'active'")

        results = []
        for t in terminals:
            t_violations = []
            for f in fences:
                dist = haversine_m(t["lat"], t["lng"], f["center_lat"], f["center_lng"])
                if dist > f["radius_m"]:
                    t_violations.append({
                        "geofence_id": str(f["id"]),
                        "name": f["name"],
                        "distance_over_m": round(dist - f["radius_m"], 2),
                    })
            results.append({
                "terminal_id": t["terminal_id"],
                "lat": t["lat"],
                "lng": t["lng"],
                "violations": t_violations,
                "violation_count": len(t_violations),
            })

        return {
            "checked_terminals": len(results),
            "terminals_with_violations": sum(1 for r in results if r["violation_count"] > 0),
            "results": results,
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
