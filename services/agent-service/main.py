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

# ── Round-11 persistence fix ───────────────────────────────────────────────
# Process-memory dict replaced by a dict-compatible Postgres-backed store so
# business data survives restarts. Mirrors sibling-service convention:
# {ENV}_DATABASE_URL, pool_pre_ping, auto-created table (python-owned schema).
import os as _r11_os
import json as _r11_json
from datetime import datetime as _r11_dt, timezone as _r11_tz
from sqlalchemy import (
    create_engine as _r11_ce,
    Column as _r11_Col,
    String as _r11_Str,
    DateTime as _r11_DT,
    Text as _r11_Txt,
)
from sqlalchemy.orm import sessionmaker as _r11_sm, declarative_base as _r11_db

_R11Base = _r11_db()


class _R11Row(_R11Base):
    __abstract__ = True
    key = _r11_Col(_r11_Str(128), primary_key=True)
    data = _r11_Col(_r11_Txt, nullable=False)
    updated_at = _r11_Col(
        _r11_DT(timezone=True),
        default=lambda: _r11_dt.now(_r11_tz.utc),
        onupdate=lambda: _r11_dt.now(_r11_tz.utc),
    )


class _PgDictStore:
    """Dict-compatible store persisted to Postgres (replaces in-memory dict)."""

    def __init__(self, table, env, model_name=None):
        self._model_name = model_name
        self._Row = type("_R11_%s" % table, (_R11Row,), {"__tablename__": table})
        url = _r11_os.getenv(
            env, "postgresql://postgres:postgres@localhost:5432/platform"
        )
        self._engine = _r11_ce(url, pool_pre_ping=True, pool_size=5, max_overflow=5)
        _R11Base.metadata.create_all(self._engine)
        self._Session = _r11_sm(bind=self._engine, autoflush=False, autocommit=False)

    @staticmethod
    def _ser(v):
        def _cv(x):
            if hasattr(x, "model_dump"):
                return x.model_dump()
            if hasattr(x, "dict") and callable(x.dict):
                return x.dict()
            return x
        if isinstance(v, list):
            v = [_cv(x) for x in v]
        else:
            v = _cv(v)
        return _r11_json.dumps(v, default=str)

    def _deser(self, raw):
        d = _r11_json.loads(raw)
        if self._model_name:
            cls = globals().get(self._model_name)
            if cls is not None:
                if isinstance(d, list):
                    return [cls(**x) if isinstance(x, dict) else x for x in d]
                return cls(**d)
        return d

    def __setitem__(self, k, v):
        s = self._Session()
        try:
            row = s.get(self._Row, str(k))
            payload = self._ser(v)
            if row is None:
                s.add(self._Row(key=str(k), data=payload))
            else:
                row.data = payload
            s.commit()
        finally:
            s.close()

    def __getitem__(self, k):
        s = self._Session()
        try:
            row = s.get(self._Row, str(k))
            if row is None:
                raise KeyError(k)
            return self._deser(row.data)
        finally:
            s.close()

    def get(self, k, default=None):
        try:
            return self[k]
        except KeyError:
            return default

    def __delitem__(self, k):
        s = self._Session()
        try:
            row = s.get(self._Row, str(k))
            if row is None:
                raise KeyError(k)
            s.delete(row)
            s.commit()
        finally:
            s.close()

    def __contains__(self, k):
        s = self._Session()
        try:
            return s.get(self._Row, str(k)) is not None
        finally:
            s.close()

    def setdefault(self, k, default=None):
        try:
            return self[k]
        except KeyError:
            self[k] = default
            return default

    def _all(self):
        s = self._Session()
        try:
            return s.query(self._Row).all()
        finally:
            s.close()

    def values(self):
        return [self._deser(r.data) for r in self._all()]

    def keys(self):
        return [r.key for r in self._all()]

    def items(self):
        return [(r.key, self._deser(r.data)) for r in self._all()]

    def __len__(self):
        s = self._Session()
        try:
            return s.query(self._Row).count()
        finally:
            s.close()

    def pop(self, k, default=None):
        try:
            v = self[k]
            del self[k]
            return v
        except KeyError:
            return default

    def clear(self):
        s = self._Session()
        try:
            s.query(self._Row).delete()
            s.commit()
        finally:
            s.close()


_device_store = _PgDictStore("agent_service_devices", "AGENT_SERVICE_DATABASE_URL")
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
    _device_store[agent_id] = devices  # round-11: write back mutation
    return device


@app.delete("/api/v1/devices/{agent_id}/{device_id}", status_code=204)
async def remove_device(agent_id: str, device_id: str):
    devices = _device_store.get(agent_id, [])
    updated = [d for d in devices if d["id"] != device_id]
    if len(updated) == len(devices):
        raise HTTPException(status_code=404, detail="Device not found")
    _device_store[agent_id] = updated
