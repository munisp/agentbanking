"""
Terminal Ownership Registry - FastAPI microservice
POS terminal lifecycle management: provisioning, assignment, transfer,
maintenance tracking, insurance, and decommissioning.
"""
import os
import sys
import json
import uuid
import signal
import atexit
import logging
from datetime import datetime, timedelta
from typing import Optional, List
from enum import Enum
from fastapi import FastAPI, HTTPException, Depends, Query, Path
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
    "DATABASE_URL", "postgres://postgres:postgres@localhost:5432/terminal_ownership"
)

_pool: Optional[asyncpg.Pool] = None

async def get_db_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
        register_shutdown(lambda: None)
    return _pool

# ── FastAPI App ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="Terminal Ownership Registry",
    description="POS terminal lifecycle management: provisioning, assignment, "
    "transfer, maintenance tracking, insurance, and decommissioning.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Status Transitions ──────────────────────────────────────────────────────

VALID_STATUSES = [
    "provisioned", "assigned", "active", "suspended",
    "maintenance", "decommissioned", "lost", "stolen",
]

STATUS_TRANSITIONS = {
    "provisioned": ["assigned", "decommissioned"],
    "assigned": ["active", "provisioned", "decommissioned"],
    "active": ["suspended", "maintenance", "decommissioned", "lost", "stolen"],
    "suspended": ["active", "decommissioned"],
    "maintenance": ["active", "decommissioned"],
    "decommissioned": [],
    "lost": ["decommissioned"],
    "stolen": ["decommissioned"],
}


# ── DB Schema Init ───────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS terminal_registry (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                serial_number VARCHAR(64) NOT NULL UNIQUE,
                model VARCHAR(64) NOT NULL,
                manufacturer VARCHAR(64),
                firmware_version VARCHAR(32),
                os_version VARCHAR(32),
                imei VARCHAR(20),
                sim_iccid VARCHAR(22),
                status VARCHAR(20) NOT NULL DEFAULT 'provisioned',
                current_agent_id VARCHAR(64),
                current_agent_name VARCHAR(128),
                location_lat DOUBLE PRECISION,
                location_lng DOUBLE PRECISION,
                battery_level INTEGER,
                last_transaction_at TIMESTAMPTZ,
                warranty_expires_at TIMESTAMPTZ,
                insurance_policy_id VARCHAR(64),
                insurance_expires_at TIMESTAMPTZ,
                purchase_price NUMERIC(12, 2),
                purchase_date DATE,
                config_json JSONB DEFAULT '{}',
                notes TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS ownership_transfers (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                terminal_id UUID REFERENCES terminal_registry(id) NOT NULL,
                from_agent_id VARCHAR(64),
                from_agent_name VARCHAR(128),
                to_agent_id VARCHAR(64) NOT NULL,
                to_agent_name VARCHAR(128),
                reason VARCHAR(255),
                approval_status VARCHAR(20) NOT NULL DEFAULT 'pending',
                approved_by VARCHAR(64),
                approved_at TIMESTAMPTZ,
                notes TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS maintenance_records (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                terminal_id UUID REFERENCES terminal_registry(id) NOT NULL,
                issue_type VARCHAR(64) NOT NULL,
                description TEXT NOT NULL,
                technician_name VARCHAR(128),
                resolution TEXT,
                parts_replaced JSONB DEFAULT '[]',
                cost NUMERIC(12, 2),
                started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                completed_at TIMESTAMPTZ,
                next_maintenance_at TIMESTAMPTZ
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS terminal_audit_log (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                terminal_id UUID REFERENCES terminal_registry(id),
                action VARCHAR(64) NOT NULL,
                actor VARCHAR(64),
                old_status VARCHAR(20),
                new_status VARCHAR(20),
                details JSONB DEFAULT '{}',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_tr_serial ON terminal_registry(serial_number)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_tr_status ON terminal_registry(status)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_tr_agent ON terminal_registry(current_agent_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_ot_terminal ON ownership_transfers(terminal_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_mr_terminal ON maintenance_records(terminal_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_tal_terminal ON terminal_audit_log(terminal_id)")
    logger.info("[startup] Terminal ownership tables initialized")


async def audit_log(conn, terminal_id, action, actor=None, old_status=None, new_status=None, details=None):
    await conn.execute(
        """INSERT INTO terminal_audit_log (terminal_id, action, actor, old_status, new_status, details)
        VALUES ($1, $2, $3, $4, $5, $6)""",
        terminal_id, action, actor, old_status, new_status,
        json.dumps(details or {}),
    )


# ── Pydantic Models ─────────────────────────────────────────────────────────

class TerminalProvision(BaseModel):
    serial_number: str = Field(..., min_length=1, max_length=64)
    model: str = Field(..., min_length=1, max_length=64)
    manufacturer: Optional[str] = None
    firmware_version: Optional[str] = None
    imei: Optional[str] = Field(None, max_length=20)
    sim_iccid: Optional[str] = Field(None, max_length=22)
    agent_id: Optional[str] = None
    agent_name: Optional[str] = None
    purchase_price: Optional[float] = None
    purchase_date: Optional[str] = None
    warranty_months: int = Field(default=12, ge=0, le=60)

class TransferRequest(BaseModel):
    to_agent_id: str = Field(..., min_length=1, max_length=64)
    to_agent_name: Optional[str] = None
    reason: str = Field(..., min_length=1, max_length=255)
    notes: Optional[str] = None

class MaintenanceCreate(BaseModel):
    issue_type: str = Field(..., min_length=1, max_length=64)
    description: str = Field(..., min_length=1)
    technician_name: Optional[str] = None
    parts_replaced: Optional[list] = None
    cost: Optional[float] = None

class MaintenanceComplete(BaseModel):
    resolution: str = Field(..., min_length=1)
    parts_replaced: Optional[list] = None
    cost: Optional[float] = None
    next_maintenance_days: int = Field(default=90, ge=0, le=365)

class StatusUpdate(BaseModel):
    status: str
    reason: Optional[str] = None
    actor: Optional[str] = None

class InsuranceUpdate(BaseModel):
    policy_id: str = Field(..., min_length=1, max_length=64)
    expires_at: str


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {
            "status": "healthy",
            "service": "terminal-ownership",
            "version": "2.0.0",
            "database": "connected",
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        return {"status": "degraded", "service": "terminal-ownership", "error": str(e)}


@app.post("/api/v1/terminals/provision")
async def provision_terminal(body: TerminalProvision):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT id FROM terminal_registry WHERE serial_number = $1",
            body.serial_number,
        )
        if existing:
            raise HTTPException(status_code=409, detail="Serial number already registered")

        warranty_expires = None
        if body.warranty_months > 0:
            warranty_expires = datetime.utcnow() + timedelta(days=body.warranty_months * 30)

        initial_status = "assigned" if body.agent_id else "provisioned"
        row = await conn.fetchrow(
            """
            INSERT INTO terminal_registry
            (serial_number, model, manufacturer, firmware_version, imei, sim_iccid,
             status, current_agent_id, current_agent_name,
             purchase_price, warranty_expires_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            RETURNING *
            """,
            body.serial_number, body.model, body.manufacturer,
            body.firmware_version, body.imei, body.sim_iccid,
            initial_status, body.agent_id, body.agent_name,
            body.purchase_price, warranty_expires,
        )
        await audit_log(conn, row["id"], "provisioned", details={
            "serial_number": body.serial_number, "model": body.model,
        })
        logger.info(f"[provision] Terminal {body.serial_number} provisioned")
        return dict(row)


@app.get("/api/v1/terminals/{terminal_id}")
async def get_terminal(terminal_id: str):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM terminal_registry WHERE id = $1",
            uuid.UUID(terminal_id),
        )
        if not row:
            raise HTTPException(status_code=404, detail="Terminal not found")

        transfer_count = await conn.fetchval(
            "SELECT COUNT(*) FROM ownership_transfers WHERE terminal_id = $1",
            uuid.UUID(terminal_id),
        )
        maintenance_count = await conn.fetchval(
            "SELECT COUNT(*) FROM maintenance_records WHERE terminal_id = $1",
            uuid.UUID(terminal_id),
        )
        return {
            **dict(row),
            "transfer_count": transfer_count,
            "maintenance_count": maintenance_count,
            "warranty_active": row["warranty_expires_at"] and row["warranty_expires_at"] > datetime.utcnow(),
            "insurance_active": row["insurance_expires_at"] and row["insurance_expires_at"] > datetime.utcnow(),
        }


@app.get("/api/v1/terminals")
async def list_terminals(
    status: Optional[str] = None,
    agent_id: Optional[str] = None,
    model: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "SELECT * FROM terminal_registry WHERE 1=1"
        count_query = "SELECT COUNT(*) FROM terminal_registry WHERE 1=1"
        params: list = []
        idx = 1

        if status:
            query += f" AND status = ${idx}"
            count_query += f" AND status = ${idx}"
            params.append(status)
            idx += 1
        if agent_id:
            query += f" AND current_agent_id = ${idx}"
            count_query += f" AND current_agent_id = ${idx}"
            params.append(agent_id)
            idx += 1
        if model:
            query += f" AND model = ${idx}"
            count_query += f" AND model = ${idx}"
            params.append(model)
            idx += 1

        total = await conn.fetchval(count_query, *params)
        query += f" ORDER BY created_at DESC LIMIT ${idx} OFFSET ${idx + 1}"
        params.extend([limit, offset])
        rows = await conn.fetch(query, *params)

        return {
            "items": [dict(r) for r in rows],
            "total": total,
            "limit": limit,
            "offset": offset,
        }


@app.post("/api/v1/terminals/{terminal_id}/transfer")
async def transfer_terminal(terminal_id: str, body: TransferRequest):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        terminal = await conn.fetchrow(
            "SELECT * FROM terminal_registry WHERE id = $1",
            uuid.UUID(terminal_id),
        )
        if not terminal:
            raise HTTPException(status_code=404, detail="Terminal not found")
        if terminal["status"] in ("decommissioned", "lost", "stolen"):
            raise HTTPException(
                status_code=400,
                detail=f"Cannot transfer terminal in '{terminal['status']}' status",
            )

        transfer = await conn.fetchrow(
            """
            INSERT INTO ownership_transfers
            (terminal_id, from_agent_id, from_agent_name, to_agent_id, to_agent_name,
             reason, approval_status, notes)
            VALUES ($1, $2, $3, $4, $5, $6, 'approved', $7)
            RETURNING *
            """,
            uuid.UUID(terminal_id),
            terminal["current_agent_id"],
            terminal["current_agent_name"],
            body.to_agent_id,
            body.to_agent_name,
            body.reason,
            body.notes,
        )

        await conn.execute(
            """
            UPDATE terminal_registry
            SET current_agent_id = $2, current_agent_name = $3,
                status = 'assigned', updated_at = NOW()
            WHERE id = $1
            """,
            uuid.UUID(terminal_id), body.to_agent_id, body.to_agent_name,
        )

        await audit_log(
            conn, uuid.UUID(terminal_id), "transferred",
            old_status=terminal["status"], new_status="assigned",
            details={
                "from": terminal["current_agent_id"],
                "to": body.to_agent_id,
                "reason": body.reason,
            },
        )
        logger.info(f"[transfer] Terminal {terminal_id} transferred to {body.to_agent_id}")
        return dict(transfer)


@app.get("/api/v1/terminals/{terminal_id}/transfers")
async def get_transfer_history(terminal_id: str, limit: int = 50, offset: int = 0):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM ownership_transfers WHERE terminal_id = $1",
            uuid.UUID(terminal_id),
        )
        rows = await conn.fetch(
            """SELECT * FROM ownership_transfers
            WHERE terminal_id = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3""",
            uuid.UUID(terminal_id), limit, offset,
        )
        return {"transfers": [dict(r) for r in rows], "total": total}


@app.put("/api/v1/terminals/{terminal_id}/status")
async def update_status(terminal_id: str, body: StatusUpdate):
    if body.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {VALID_STATUSES}")

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        terminal = await conn.fetchrow(
            "SELECT * FROM terminal_registry WHERE id = $1",
            uuid.UUID(terminal_id),
        )
        if not terminal:
            raise HTTPException(status_code=404, detail="Terminal not found")

        current = terminal["status"]
        allowed = STATUS_TRANSITIONS.get(current, [])
        if body.status not in allowed:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot transition from '{current}' to '{body.status}'. Allowed: {allowed}",
            )

        await conn.execute(
            "UPDATE terminal_registry SET status = $2, updated_at = NOW() WHERE id = $1",
            uuid.UUID(terminal_id), body.status,
        )
        await audit_log(
            conn, uuid.UUID(terminal_id), "status_change",
            actor=body.actor, old_status=current, new_status=body.status,
            details={"reason": body.reason},
        )
        return {"terminal_id": terminal_id, "old_status": current, "new_status": body.status}


@app.post("/api/v1/terminals/{terminal_id}/decommission")
async def decommission_terminal(terminal_id: str, reason: str):
    valid_reasons = ["end_of_life", "damaged", "lost", "stolen", "recalled", "replaced"]
    if reason not in valid_reasons:
        raise HTTPException(status_code=400, detail=f"Invalid reason. Must be one of: {valid_reasons}")

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        terminal = await conn.fetchrow(
            "SELECT * FROM terminal_registry WHERE id = $1",
            uuid.UUID(terminal_id),
        )
        if not terminal:
            raise HTTPException(status_code=404, detail="Terminal not found")
        if terminal["status"] == "decommissioned":
            raise HTTPException(status_code=400, detail="Terminal already decommissioned")

        await conn.execute(
            "UPDATE terminal_registry SET status = 'decommissioned', updated_at = NOW() WHERE id = $1",
            uuid.UUID(terminal_id),
        )
        await audit_log(
            conn, uuid.UUID(terminal_id), "decommissioned",
            old_status=terminal["status"], new_status="decommissioned",
            details={"reason": reason},
        )
        return {
            "terminal_id": terminal_id,
            "status": "decommissioned",
            "reason": reason,
            "decommissioned_at": datetime.utcnow().isoformat(),
        }


@app.post("/api/v1/terminals/{terminal_id}/maintenance")
async def create_maintenance(terminal_id: str, body: MaintenanceCreate):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        terminal = await conn.fetchrow(
            "SELECT * FROM terminal_registry WHERE id = $1",
            uuid.UUID(terminal_id),
        )
        if not terminal:
            raise HTTPException(status_code=404, detail="Terminal not found")

        old_status = terminal["status"]
        await conn.execute(
            "UPDATE terminal_registry SET status = 'maintenance', updated_at = NOW() WHERE id = $1",
            uuid.UUID(terminal_id),
        )

        record = await conn.fetchrow(
            """
            INSERT INTO maintenance_records
            (terminal_id, issue_type, description, technician_name, parts_replaced, cost)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING *
            """,
            uuid.UUID(terminal_id), body.issue_type, body.description,
            body.technician_name,
            json.dumps(body.parts_replaced or []),
            body.cost,
        )
        await audit_log(
            conn, uuid.UUID(terminal_id), "maintenance_started",
            old_status=old_status, new_status="maintenance",
            details={"issue_type": body.issue_type},
        )
        return dict(record)


@app.put("/api/v1/terminals/{terminal_id}/maintenance/{record_id}/complete")
async def complete_maintenance(terminal_id: str, record_id: str, body: MaintenanceComplete):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        record = await conn.fetchrow(
            "SELECT * FROM maintenance_records WHERE id = $1 AND terminal_id = $2",
            uuid.UUID(record_id), uuid.UUID(terminal_id),
        )
        if not record:
            raise HTTPException(status_code=404, detail="Maintenance record not found")
        if record["completed_at"]:
            raise HTTPException(status_code=400, detail="Maintenance already completed")

        next_maint = datetime.utcnow() + timedelta(days=body.next_maintenance_days)
        await conn.execute(
            """
            UPDATE maintenance_records
            SET resolution = $2, parts_replaced = $3, cost = $4,
                completed_at = NOW(), next_maintenance_at = $5
            WHERE id = $1
            """,
            uuid.UUID(record_id), body.resolution,
            json.dumps(body.parts_replaced or []),
            body.cost, next_maint,
        )

        await conn.execute(
            "UPDATE terminal_registry SET status = 'active', updated_at = NOW() WHERE id = $1",
            uuid.UUID(terminal_id),
        )
        await audit_log(
            conn, uuid.UUID(terminal_id), "maintenance_completed",
            old_status="maintenance", new_status="active",
            details={"resolution": body.resolution},
        )
        return {"completed": True, "next_maintenance_at": next_maint.isoformat()}


@app.get("/api/v1/terminals/{terminal_id}/maintenance")
async def get_maintenance_history(terminal_id: str, limit: int = 50, offset: int = 0):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM maintenance_records WHERE terminal_id = $1",
            uuid.UUID(terminal_id),
        )
        rows = await conn.fetch(
            """SELECT * FROM maintenance_records
            WHERE terminal_id = $1 ORDER BY started_at DESC LIMIT $2 OFFSET $3""",
            uuid.UUID(terminal_id), limit, offset,
        )
        return {"records": [dict(r) for r in rows], "total": total}


@app.put("/api/v1/terminals/{terminal_id}/insurance")
async def update_insurance(terminal_id: str, body: InsuranceUpdate):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        terminal = await conn.fetchrow(
            "SELECT * FROM terminal_registry WHERE id = $1",
            uuid.UUID(terminal_id),
        )
        if not terminal:
            raise HTTPException(status_code=404, detail="Terminal not found")

        expires_at = datetime.fromisoformat(body.expires_at)
        await conn.execute(
            """UPDATE terminal_registry
            SET insurance_policy_id = $2, insurance_expires_at = $3, updated_at = NOW()
            WHERE id = $1""",
            uuid.UUID(terminal_id), body.policy_id, expires_at,
        )
        await audit_log(
            conn, uuid.UUID(terminal_id), "insurance_updated",
            details={"policy_id": body.policy_id, "expires_at": body.expires_at},
        )
        return {"updated": True, "policy_id": body.policy_id, "expires_at": body.expires_at}


@app.get("/api/v1/terminals/{terminal_id}/audit")
async def get_audit_log(terminal_id: str, limit: int = 100, offset: int = 0):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM terminal_audit_log WHERE terminal_id = $1",
            uuid.UUID(terminal_id),
        )
        rows = await conn.fetch(
            """SELECT * FROM terminal_audit_log
            WHERE terminal_id = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3""",
            uuid.UUID(terminal_id), limit, offset,
        )
        return {"audit_log": [dict(r) for r in rows], "total": total}


@app.get("/api/v1/stats")
async def fleet_stats():
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM terminal_registry")
        by_status = await conn.fetch(
            "SELECT status, COUNT(*) as cnt FROM terminal_registry GROUP BY status"
        )
        pending_maintenance = await conn.fetchval(
            "SELECT COUNT(*) FROM maintenance_records WHERE completed_at IS NULL"
        )
        warranty_expiring = await conn.fetchval(
            "SELECT COUNT(*) FROM terminal_registry WHERE warranty_expires_at IS NOT NULL AND warranty_expires_at < NOW() + INTERVAL '30 days' AND warranty_expires_at > NOW()"
        )
        insurance_expiring = await conn.fetchval(
            "SELECT COUNT(*) FROM terminal_registry WHERE insurance_expires_at IS NOT NULL AND insurance_expires_at < NOW() + INTERVAL '30 days' AND insurance_expires_at > NOW()"
        )
        transfers_today = await conn.fetchval(
            "SELECT COUNT(*) FROM ownership_transfers WHERE created_at >= CURRENT_DATE"
        )
        return {
            "total_terminals": total,
            "by_status": {r["status"]: r["cnt"] for r in by_status},
            "pending_maintenance": pending_maintenance,
            "warranty_expiring_30d": warranty_expiring,
            "insurance_expiring_30d": insurance_expiring,
            "transfers_today": transfers_today,
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
