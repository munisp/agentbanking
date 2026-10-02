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

# ── Round-11 persistence fix (wave-6: asyncpg) ────────────────────────────
# Process-memory containers replaced by Postgres-backed stores so business
# data survives restarts. Wave-6 upgrade: all DB I/O now runs on asyncpg via
# a dedicated background event loop, so async FastAPI handlers no longer
# block the main loop on sync SQLAlchemy calls. Same dict/list-compatible
# public API; {ENV}_DATABASE_URL convention unchanged.
import os as _r11_os
import json as _r11_json
import asyncio as _r11_asyncio
import threading as _r11_threading
import asyncpg as _r11_apg

_r11_loop = _r11_asyncio.new_event_loop()


def _r11_loop_main(loop):
    _r11_asyncio.set_event_loop(loop)
    loop.run_forever()


_r11_threading.Thread(
    target=_r11_loop_main, args=(_r11_loop,), daemon=True, name="r11-pg-io"
).start()


def _r11_sync(coro):
    """Run an asyncpg coroutine on the dedicated loop and wait for it."""
    return _r11_asyncio.run_coroutine_threadsafe(coro, _r11_loop).result()


class _PgDictStore:
    """Dict-compatible store persisted to Postgres (replaces in-memory dict)."""

    def __init__(self, table, env, model_name=None):
        if not table.replace("_", "").isalnum():
            raise ValueError("unsafe table name: %r" % table)
        self._model_name = model_name
        self._table = table
        url = _r11_os.getenv(
            env, "postgresql://postgres:postgres@localhost:5432/platform"
        )
        self._pool = _r11_sync(_r11_apg.create_pool(url, min_size=1, max_size=10))
        _r11_sync(self._ensure())

    async def _ensure(self):
        async with self._pool.acquire() as c:
            await c.execute(
                'CREATE TABLE IF NOT EXISTS "%s" ('
                "key VARCHAR(128) PRIMARY KEY, "
                "data TEXT NOT NULL, "
                "updated_at TIMESTAMPTZ NOT NULL DEFAULT now()"
                ")" % self._table
            )

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

    async def _aset(self, k, payload):
        async with self._pool.acquire() as c:
            await c.execute(
                'INSERT INTO "%s" (key, data) VALUES ($1, $2) '
                "ON CONFLICT (key) DO UPDATE SET data = EXCLUDED.data, "
                "updated_at = now()" % self._table,
                str(k), payload,
            )

    def __setitem__(self, k, v):
        _r11_sync(self._aset(k, self._ser(v)))

    async def _aget(self, k):
        async with self._pool.acquire() as c:
            return await c.fetchval(
                'SELECT data FROM "%s" WHERE key = $1' % self._table, str(k)
            )

    def __getitem__(self, k):
        raw = _r11_sync(self._aget(k))
        if raw is None:
            raise KeyError(k)
        return self._deser(raw)

    def get(self, k, default=None):
        try:
            return self[k]
        except KeyError:
            return default

    async def _adel(self, k):
        async with self._pool.acquire() as c:
            return await c.execute(
                'DELETE FROM "%s" WHERE key = $1' % self._table, str(k)
            )

    def __delitem__(self, k):
        res = _r11_sync(self._adel(k))
        if res == "DELETE 0":
            raise KeyError(k)

    def __contains__(self, k):
        return _r11_sync(self._aget(k)) is not None

    def setdefault(self, k, default=None):
        try:
            return self[k]
        except KeyError:
            self[k] = default
            return default

    async def _aall(self):
        async with self._pool.acquire() as c:
            return await c.fetch('SELECT key, data FROM "%s"' % self._table)

    def _all(self):
        return _r11_sync(self._aall())

    def values(self):
        return [self._deser(r["data"]) for r in self._all()]

    def keys(self):
        return [r["key"] for r in self._all()]

    def items(self):
        return [(r["key"], self._deser(r["data"])) for r in self._all()]

    def __len__(self):
        async def _n():
            async with self._pool.acquire() as c:
                return await c.fetchval('SELECT COUNT(*) FROM "%s"' % self._table)
        return _r11_sync(_n())

    def pop(self, k, default=None):
        try:
            v = self[k]
            del self[k]
            return v
        except KeyError:
            return default

    def clear(self):
        async def _c():
            async with self._pool.acquire() as c:
                await c.execute('DELETE FROM "%s"' % self._table)
        _r11_sync(_c())
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
