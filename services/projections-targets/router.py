import os
import uuid
from datetime import datetime, date
from typing import Any, Dict, List, Optional
from enum import Enum

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="/projections-targets", tags=["projections-targets"])


class TargetLevel(str, Enum):
    BANK = "bank"
    BANK_TO_AGENT = "bank_to_agent"
    AGENT_PERSONAL = "agent_personal"


class TargetMetric(str, Enum):
    TRANSACTION_COUNT = "transaction_count"
    TRANSACTION_VOLUME = "transaction_volume"
    REVENUE = "revenue"
    NEW_CUSTOMERS = "new_customers"
    CASH_IN_VOLUME = "cash_in_volume"
    CASH_OUT_VOLUME = "cash_out_volume"
    BILL_PAYMENT_COUNT = "bill_payment_count"
    AIRTIME_SALES = "airtime_sales"


class TargetPeriod(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class TargetCreate(BaseModel):
    level: TargetLevel
    metric: TargetMetric
    period: TargetPeriod
    target_value: float = Field(..., gt=0)
    currency: str = Field(default="NGN")
    bank_id: Optional[str] = None
    agent_id: Optional[str] = None
    territory_id: Optional[str] = None
    start_date: str = Field(..., description="YYYY-MM-DD")
    end_date: str = Field(..., description="YYYY-MM-DD")
    notes: Optional[str] = None


class TargetResponse(BaseModel):
    id: str
    level: TargetLevel
    metric: TargetMetric
    period: TargetPeriod
    target_value: float
    actual_value: float = 0.0
    achievement_pct: float = 0.0
    currency: str
    bank_id: Optional[str] = None
    agent_id: Optional[str] = None
    territory_id: Optional[str] = None
    start_date: str
    end_date: str
    status: str = "active"
    notes: Optional[str] = None
    created_at: str
    updated_at: str


class ProjectionRequest(BaseModel):
    entity_type: str = Field(..., description="bank|agent|territory")
    entity_id: str
    metric: TargetMetric
    months_ahead: int = Field(default=3, ge=1, le=24)


class ProjectionResponse(BaseModel):
    entity_type: str
    entity_id: str
    metric: TargetMetric
    projections: List[Dict[str, Any]]
    confidence: float
    generated_at: str


_targets: Dict[str, TargetResponse] = {}
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
_actuals = _PgDictStore("projections_actuals", "PROJECTIONS_DATABASE_URL")
_history: Dict[str, List[Dict[str, Any]]] = {}
_bank_agents: Dict[str, List[str]] = {}


@router.post("/bank-agents")
async def register_bank_agents(bank_id: str, agent_ids: List[str]):
    _bank_agents[bank_id] = list(set(_bank_agents.get(bank_id, []) + agent_ids))
    return {"bank_id": bank_id, "total_agents": len(_bank_agents[bank_id]), "agents": _bank_agents[bank_id]}


@router.get("/bank-agents/{bank_id}")
async def get_bank_agents(bank_id: str):
    return {"bank_id": bank_id, "agents": _bank_agents.get(bank_id, [])}


@router.post("/targets", response_model=TargetResponse)
async def create_target(request: TargetCreate):
    if request.level == TargetLevel.BANK and not request.bank_id:
        raise HTTPException(status_code=400, detail="bank_id required for bank-level targets")
    if request.level == TargetLevel.BANK_TO_AGENT and (not request.bank_id or not request.agent_id):
        raise HTTPException(status_code=400, detail="bank_id and agent_id required for bank-to-agent targets")
    if request.level == TargetLevel.AGENT_PERSONAL and not request.agent_id:
        raise HTTPException(status_code=400, detail="agent_id required for agent personal targets")

    target_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    target = TargetResponse(
        id=target_id,
        level=request.level,
        metric=request.metric,
        period=request.period,
        target_value=request.target_value,
        actual_value=0.0,
        achievement_pct=0.0,
        currency=request.currency,
        bank_id=request.bank_id,
        agent_id=request.agent_id,
        territory_id=request.territory_id,
        start_date=request.start_date,
        end_date=request.end_date,
        notes=request.notes,
        created_at=now,
        updated_at=now,
    )
    _targets[target_id] = target

    if request.level == TargetLevel.BANK and request.bank_id:
        agents = _bank_agents.get(request.bank_id, [])
        if agents:
            per_agent_value = round(request.target_value / len(agents), 2)
            for aid in agents:
                child_id = str(uuid.uuid4())
                child = TargetResponse(
                    id=child_id,
                    level=TargetLevel.BANK_TO_AGENT,
                    metric=request.metric,
                    period=request.period,
                    target_value=per_agent_value,
                    actual_value=0.0,
                    achievement_pct=0.0,
                    currency=request.currency,
                    bank_id=request.bank_id,
                    agent_id=aid,
                    territory_id=request.territory_id,
                    start_date=request.start_date,
                    end_date=request.end_date,
                    notes=f"Auto-propagated from bank target {target_id} ({per_agent_value}/{request.target_value})",
                    created_at=now,
                    updated_at=now,
                )
                _targets[child_id] = child

    return target


@router.get("/targets", response_model=List[TargetResponse])
async def list_targets(
    level: Optional[TargetLevel] = None,
    bank_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    metric: Optional[TargetMetric] = None,
    status: Optional[str] = Query(default=None, description="active|completed|missed"),
):
    targets = list(_targets.values())
    if level:
        targets = [t for t in targets if t.level == level]
    if bank_id:
        targets = [t for t in targets if t.bank_id == bank_id]
    if agent_id:
        targets = [t for t in targets if t.agent_id == agent_id]
    if metric:
        targets = [t for t in targets if t.metric == metric]
    if status:
        targets = [t for t in targets if t.status == status]
    return targets


@router.get("/targets/{target_id}", response_model=TargetResponse)
async def get_target(target_id: str):
    if target_id not in _targets:
        raise HTTPException(status_code=404, detail="Target not found")
    return _targets[target_id]


@router.put("/targets/{target_id}", response_model=TargetResponse)
async def update_target(target_id: str, request: TargetCreate):
    if target_id not in _targets:
        raise HTTPException(status_code=404, detail="Target not found")
    target = _targets[target_id]
    target.target_value = request.target_value
    target.end_date = request.end_date
    target.notes = request.notes
    target.updated_at = datetime.utcnow().isoformat()
    if target.target_value > 0:
        target.achievement_pct = round((target.actual_value / target.target_value) * 100, 1)
    return target


@router.delete("/targets/{target_id}")
async def delete_target(target_id: str):
    if target_id not in _targets:
        raise HTTPException(status_code=404, detail="Target not found")
    del _targets[target_id]
    return {"status": "deleted", "target_id": target_id}


@router.post("/targets/{target_id}/record-actual")
async def record_actual(target_id: str, value: float):
    if target_id not in _targets:
        raise HTTPException(status_code=404, detail="Target not found")
    target = _targets[target_id]
    target.actual_value += value
    if target.target_value > 0:
        target.achievement_pct = round((target.actual_value / target.target_value) * 100, 1)
    if target.achievement_pct >= 100:
        target.status = "completed"
    target.updated_at = datetime.utcnow().isoformat()

    _history.setdefault(target_id, []).append({
        "value": value,
        "cumulative": target.actual_value,
        "achievement_pct": target.achievement_pct,
        "recorded_at": datetime.utcnow().isoformat(),
    })

    return {
        "target_id": target_id,
        "actual_value": target.actual_value,
        "target_value": target.target_value,
        "achievement_pct": target.achievement_pct,
        "status": target.status,
    }


@router.get("/targets/{target_id}/history")
async def get_target_history(target_id: str):
    if target_id not in _targets:
        raise HTTPException(status_code=404, detail="Target not found")
    return {
        "target_id": target_id,
        "target": _targets[target_id],
        "history": _history.get(target_id, []),
    }


@router.post("/projections", response_model=ProjectionResponse)
async def generate_projection(request: ProjectionRequest):
    base_values = {
        TargetMetric.TRANSACTION_COUNT: 1500,
        TargetMetric.TRANSACTION_VOLUME: 25_000_000,
        TargetMetric.REVENUE: 750_000,
        TargetMetric.NEW_CUSTOMERS: 120,
        TargetMetric.CASH_IN_VOLUME: 15_000_000,
        TargetMetric.CASH_OUT_VOLUME: 10_000_000,
        TargetMetric.BILL_PAYMENT_COUNT: 800,
        TargetMetric.AIRTIME_SALES: 2_500_000,
    }

    entity_targets = [
        t for t in _targets.values()
        if (t.bank_id == request.entity_id or t.agent_id == request.entity_id)
        and t.metric == request.metric
    ]

    if entity_targets:
        base = sum(t.actual_value for t in entity_targets if t.actual_value > 0) / max(len(entity_targets), 1)
        if base == 0:
            base = base_values.get(request.metric, 1000)
    else:
        base = base_values.get(request.metric, 1000)

    growth_rates = {
        TargetMetric.TRANSACTION_COUNT: 0.08,
        TargetMetric.TRANSACTION_VOLUME: 0.10,
        TargetMetric.REVENUE: 0.07,
        TargetMetric.NEW_CUSTOMERS: 0.12,
        TargetMetric.CASH_IN_VOLUME: 0.09,
        TargetMetric.CASH_OUT_VOLUME: 0.06,
        TargetMetric.BILL_PAYMENT_COUNT: 0.05,
        TargetMetric.AIRTIME_SALES: 0.04,
    }
    growth = growth_rates.get(request.metric, 0.05)

    projections = []
    current = base
    today = date.today()
    for i in range(1, request.months_ahead + 1):
        month = today.month + i
        year = today.year + (month - 1) // 12
        month = ((month - 1) % 12) + 1
        current = current * (1 + growth)
        projections.append({
            "month": f"{year}-{month:02d}",
            "projected_value": round(current, 2),
            "lower_bound": round(current * 0.85, 2),
            "upper_bound": round(current * 1.15, 2),
        })

    return ProjectionResponse(
        entity_type=request.entity_type,
        entity_id=request.entity_id,
        metric=request.metric,
        projections=projections,
        confidence=0.82,
        generated_at=datetime.utcnow().isoformat(),
    )


@router.get("/dashboard/bank/{bank_id}")
async def bank_dashboard(bank_id: str):
    bank_targets = [t for t in _targets.values() if t.bank_id == bank_id and t.level == TargetLevel.BANK]
    agent_targets = [t for t in _targets.values() if t.bank_id == bank_id and t.level == TargetLevel.BANK_TO_AGENT]

    agent_summary = {}
    for t in agent_targets:
        aid = t.agent_id or "unknown"
        if aid not in agent_summary:
            agent_summary[aid] = {"agent_id": aid, "targets": 0, "completed": 0, "avg_achievement": 0.0}
        agent_summary[aid]["targets"] += 1
        if t.status == "completed":
            agent_summary[aid]["completed"] += 1
        agent_summary[aid]["avg_achievement"] += t.achievement_pct

    for aid in agent_summary:
        if agent_summary[aid]["targets"] > 0:
            agent_summary[aid]["avg_achievement"] = round(
                agent_summary[aid]["avg_achievement"] / agent_summary[aid]["targets"], 1
            )

    return {
        "bank_id": bank_id,
        "bank_targets": [t.dict() for t in bank_targets],
        "total_bank_targets": len(bank_targets),
        "agent_performance": list(agent_summary.values()),
        "total_agents_with_targets": len(agent_summary),
    }


@router.get("/dashboard/agent/{agent_id}")
async def agent_dashboard(agent_id: str):
    bank_assigned = [t for t in _targets.values() if t.agent_id == agent_id and t.level == TargetLevel.BANK_TO_AGENT]
    personal = [t for t in _targets.values() if t.agent_id == agent_id and t.level == TargetLevel.AGENT_PERSONAL]

    return {
        "agent_id": agent_id,
        "bank_assigned_targets": [t.dict() for t in bank_assigned],
        "personal_targets": [t.dict() for t in personal],
        "overall_achievement": round(
            sum(t.achievement_pct for t in bank_assigned + personal) / max(len(bank_assigned + personal), 1), 1
        ),
        "targets_completed": len([t for t in bank_assigned + personal if t.status == "completed"]),
        "targets_active": len([t for t in bank_assigned + personal if t.status == "active"]),
    }


@router.get("/leaderboard")
async def agent_leaderboard(
    bank_id: Optional[str] = None,
    metric: Optional[TargetMetric] = None,
    limit: int = Query(default=20, le=100),
):
    agent_scores: Dict[str, Dict[str, Any]] = {}
    for t in _targets.values():
        if not t.agent_id:
            continue
        if bank_id and t.bank_id != bank_id:
            continue
        if metric and t.metric != metric:
            continue
        aid = t.agent_id
        if aid not in agent_scores:
            agent_scores[aid] = {"agent_id": aid, "total_achievement": 0.0, "targets": 0, "completed": 0}
        agent_scores[aid]["total_achievement"] += t.achievement_pct
        agent_scores[aid]["targets"] += 1
        if t.status == "completed":
            agent_scores[aid]["completed"] += 1

    for aid in agent_scores:
        if agent_scores[aid]["targets"] > 0:
            agent_scores[aid]["avg_achievement"] = round(
                agent_scores[aid]["total_achievement"] / agent_scores[aid]["targets"], 1
            )
        else:
            agent_scores[aid]["avg_achievement"] = 0.0

    leaderboard = sorted(agent_scores.values(), key=lambda x: x["avg_achievement"], reverse=True)
    for i, entry in enumerate(leaderboard):
        entry["rank"] = i + 1

    return {"leaderboard": leaderboard[:limit], "total_agents": len(leaderboard)}


@router.post("/propagate/{bank_id}")
async def propagate_bank_targets(bank_id: str):
    agents = _bank_agents.get(bank_id, [])
    if not agents:
        raise HTTPException(status_code=400, detail=f"No agents registered for bank {bank_id}")
    bank_targets = [t for t in _targets.values() if t.bank_id == bank_id and t.level == TargetLevel.BANK]
    if not bank_targets:
        raise HTTPException(status_code=404, detail=f"No bank-level targets found for {bank_id}")
    created = 0
    now = datetime.utcnow().isoformat()
    for bt in bank_targets:
        existing_agents = {t.agent_id for t in _targets.values() if t.bank_id == bank_id and t.level == TargetLevel.BANK_TO_AGENT and t.metric == bt.metric and t.period == bt.period}
        missing_agents = [a for a in agents if a not in existing_agents]
        if not missing_agents:
            continue
        per_agent = round(bt.target_value / len(agents), 2)
        for aid in missing_agents:
            child_id = str(uuid.uuid4())
            child = TargetResponse(
                id=child_id, level=TargetLevel.BANK_TO_AGENT, metric=bt.metric,
                period=bt.period, target_value=per_agent, currency=bt.currency,
                bank_id=bank_id, agent_id=aid, territory_id=bt.territory_id,
                start_date=bt.start_date, end_date=bt.end_date,
                notes=f"Propagated from bank target {bt.id}",
                created_at=now, updated_at=now,
            )
            _targets[child_id] = child
            created += 1
    return {"bank_id": bank_id, "targets_propagated": created, "agents": len(agents)}
