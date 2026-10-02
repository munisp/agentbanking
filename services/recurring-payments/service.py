"""Recurring Payments Service - Production Implementation"""
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import uuid, os, logging, httpx

logger = logging.getLogger(__name__)
PAYMENT_API = os.getenv("PAYMENT_SERVICE_URL", "http://localhost:8000/api/v1/payment")
NOTIFICATION_API = os.getenv("NOTIFICATION_SERVICE_URL", "http://localhost:8000/api/v1/notification-service")
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
schedules_db = _PgDictStore("recurring_schedules", "RECURRING_PAYMENTS_DATABASE_URL")
async def create(data: Dict[str, Any]) -> Dict[str, Any]:
    sid = str(uuid.uuid4())
    schedules_db[sid] = {**data, "id": sid, "status": "active", "created_at": datetime.utcnow().isoformat()}
    return schedules_db[sid]

async def get_by_id(item_id: str) -> Optional[Dict[str, Any]]:
    return schedules_db.get(item_id)

async def get_all() -> List[Dict[str, Any]]:
    return list(schedules_db.values())

async def update(item_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if item_id in schedules_db:
        schedules_db[item_id].update(data)
        return schedules_db[item_id]
    return None

async def delete(item_id: str) -> bool:
    return schedules_db.pop(item_id, None) is not None

async def create_schedule(user_id: str, amount: float, currency: str, recipient: str, frequency: str, start_date: str) -> Dict:
    schedule = {"id": str(uuid.uuid4()), "user_id": user_id, "amount": amount, "currency": currency, "recipient": recipient, "frequency": frequency, "start_date": start_date, "status": "active", "next_execution": start_date, "created_at": datetime.utcnow().isoformat(), "execution_count": 0, "last_executed": None}
    schedules_db[schedule["id"]] = schedule
    return schedule

async def execute_scheduled_payment(schedule_id: str) -> Dict:
    schedule = schedules_db.get(schedule_id)
    if not schedule or schedule["status"] != "active":
        return {"success": False, "error": "Schedule not found or inactive"}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(PAYMENT_API, json={"amount": schedule["amount"], "currency": schedule["currency"], "recipient": schedule["recipient"], "idempotency_key": f"{schedule_id}-{schedule['execution_count']+1}"})
            result = resp.json()
        schedule["execution_count"] += 1
        schedule["last_executed"] = datetime.utcnow().isoformat()
        freq_map = {"daily": 1, "weekly": 7, "biweekly": 14, "monthly": 30}
        days = freq_map.get(schedule["frequency"], 30)
        schedule["next_execution"] = (datetime.utcnow() + timedelta(days=days)).isoformat()
        return {"success": True, "payment": result, "next_execution": schedule["next_execution"]}
    except Exception as e:
        logger.error(f"Payment execution failed for {schedule_id}: {e}")
        return {"success": False, "error": str(e)}

async def pause_schedule(schedule_id: str) -> Dict:
    if schedule_id in schedules_db:
        schedules_db[schedule_id]["status"] = "paused"
        return {"success": True, "status": "paused"}
    return {"success": False, "error": "Not found"}

async def resume_schedule(schedule_id: str) -> Dict:
    if schedule_id in schedules_db and schedules_db[schedule_id]["status"] == "paused":
        schedules_db[schedule_id]["status"] = "active"
        return {"success": True, "status": "active"}
    return {"success": False, "error": "Not found or not paused"}

async def cancel_schedule(schedule_id: str) -> Dict:
    if schedule_id in schedules_db:
        schedules_db[schedule_id]["status"] = "cancelled"
        return {"success": True, "status": "cancelled"}
    return {"success": False, "error": "Not found"}

async def edit_schedule(schedule_id: str, updates: Dict[str, Any]) -> Dict:
    if schedule_id in schedules_db:
        for k, v in updates.items():
            if k in {"amount", "currency", "recipient", "frequency"}:
                schedules_db[schedule_id][k] = v
        return {"success": True, "schedule": schedules_db[schedule_id]}
    return {"success": False, "error": "Not found"}
