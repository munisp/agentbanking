"""Recurring Payments Service - Production Implementation"""
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import uuid, os, logging, httpx

logger = logging.getLogger(__name__)
PAYMENT_API = os.getenv("PAYMENT_SERVICE_URL", "http://localhost:8000/api/v1/payment")
NOTIFICATION_API = os.getenv("NOTIFICATION_SERVICE_URL", "http://localhost:8000/api/v1/notification-service")
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
