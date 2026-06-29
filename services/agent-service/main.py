from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional, Dict, List, Any
from datetime import datetime
import uuid

from database import Base, engine
from api import health_router, agent_router
from api.business import business_router
from api.pos_request import pos_request_router
from api.transaction import router as transaction_router
from api.beneficiary import beneficiary_router
from middlewares import RequiredHeadersMiddleware

app = FastAPI(
    title="Agent Service",
    description="54Agent agent management service.",
    version="0.0.0",
)

app.add_middleware(
    RequiredHeadersMiddleware,
    required_headers=["x-tenant-id", "x-keycloak-id"],
    exclude_prefixes=["/health", "/dapr"],
)

# Create/update tables
Base.metadata.create_all(bind=engine)

# Incremental column migrations (safe to run repeatedly)
with engine.connect() as _conn:
    _conn.execute(text("ALTER TABLE agent ADD COLUMN IF NOT EXISTS invited_by VARCHAR"))
    _conn.execute(
        text("ALTER TABLE agent ADD COLUMN IF NOT EXISTS inviter_type VARCHAR")
    )
    _conn.execute(
        text(
            "ALTER TABLE pos_request ADD COLUMN IF NOT EXISTS geofence_latitude VARCHAR"
        )
    )
    _conn.execute(
        text(
            "ALTER TABLE pos_request ADD COLUMN IF NOT EXISTS geofence_longitude VARCHAR"
        )
    )
    _conn.execute(
        text(
            "ALTER TABLE pos_request ADD COLUMN IF NOT EXISTS geofence_radius_m VARCHAR"
        )
    )
    _conn.execute(text("""
        CREATE TABLE IF NOT EXISTS agent_beneficiaries (
            id VARCHAR PRIMARY KEY,
            agent_keycloak_id VARCHAR NOT NULL,
            tenant_id VARCHAR NOT NULL,
            name VARCHAR NOT NULL DEFAULT '',
            account_number VARCHAR NOT NULL DEFAULT '',
            bank_name VARCHAR NOT NULL DEFAULT '',
            bank_code VARCHAR NOT NULL DEFAULT '',
            phone VARCHAR NOT NULL DEFAULT '',
            nickname VARCHAR NOT NULL DEFAULT '',
            is_starred BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """))
    _conn.execute(text("CREATE INDEX IF NOT EXISTS idx_agent_bene_kid ON agent_beneficiaries(agent_keycloak_id, tenant_id)"))
    _conn.commit()

app.include_router(health_router, prefix="", tags=["health"])
app.include_router(beneficiary_router, prefix="", tags=["beneficiaries"])
app.include_router(agent_router, prefix="/agent", tags=["agent"])
app.include_router(business_router, prefix="/agent", tags=["business"])
app.include_router(pos_request_router, prefix="/agent", tags=["pos-requests"])
app.include_router(transaction_router, prefix="/agent", tags=["transactions"])


# ── Trusted Device Fingerprint endpoints ─────────────────────────────────────

_device_store: Dict[str, List[Dict[str, Any]]] = {}


class DeviceRegistration(BaseModel):
    fingerprint: str
    user_agent: Optional[str] = None
    screen_resolution: Optional[str] = None
    timezone: Optional[str] = None
    language: Optional[str] = None
    platform: Optional[str] = None
    label: Optional[str] = None


@app.get("/api/v1/devices/{agent_id}")
async def get_agent_devices(agent_id: str):
    devices = _device_store.get(agent_id, [])
    return {"agent_id": agent_id, "devices": devices, "total": len(devices)}


@app.post("/api/v1/devices/{agent_id}", status_code=201)
async def register_device(agent_id: str, payload: DeviceRegistration):
    devices = _device_store.setdefault(agent_id, [])
    if any(d["fingerprint"] == payload.fingerprint for d in devices):
        raise HTTPException(status_code=409, detail="Device already registered")
    device = {
        "id": str(uuid.uuid4()),
        "agent_id": agent_id,
        "fingerprint": payload.fingerprint,
        "user_agent": payload.user_agent,
        "screen_resolution": payload.screen_resolution,
        "timezone": payload.timezone,
        "language": payload.language,
        "platform": payload.platform,
        "label": payload.label,
        "created_at": datetime.utcnow().isoformat(),
    }
    devices.append(device)
    return device


@app.delete("/api/v1/devices/{agent_id}/{device_id}", status_code=204)
async def remove_device(agent_id: str, device_id: str):
    devices = _device_store.get(agent_id, [])
    updated = [d for d in devices if d["id"] != device_id]
    if len(updated) == len(devices):
        raise HTTPException(status_code=404, detail="Device not found")
    _device_store[agent_id] = updated
