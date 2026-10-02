"""Investment Service - Production Implementation"""
from datetime import datetime
from typing import Dict, Any, List, Optional
import uuid, os, logging

logger = logging.getLogger(__name__)
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
portfolios_db = _PgDictStore("investment_portfolios", "INVESTMENT_DATABASE_URL")
async def create(data: Dict[str, Any]) -> Dict[str, Any]:
    pid = str(uuid.uuid4())
    portfolios_db[pid] = {**data, "id": pid, "created_at": datetime.utcnow().isoformat()}
    return portfolios_db[pid]

async def get_by_id(item_id: str) -> Optional[Dict[str, Any]]:
    return portfolios_db.get(item_id)

async def get_all() -> List[Dict[str, Any]]:
    return list(portfolios_db.values())

async def update(item_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if item_id in portfolios_db:
        portfolios_db[item_id].update(data)
        return portfolios_db[item_id]
    return None

async def delete(item_id: str) -> bool:
    return portfolios_db.pop(item_id, None) is not None

async def list_products() -> List[Dict]:
    return [
        {"id": "tbills", "name": "Treasury Bills", "type": "fixed_income", "min_amount": 100000, "tenor_days": 91, "rate": 0.14},
        {"id": "bonds", "name": "FGN Bonds", "type": "fixed_income", "min_amount": 50000, "tenor_days": 365, "rate": 0.155},
        {"id": "money_market", "name": "Money Market Fund", "type": "mutual_fund", "min_amount": 5000, "rate": 0.12},
    ]

async def invest_from_savings(user_id: str, product_id: str, amount: float, source_goal: str) -> Dict:
    investment = {"id": str(uuid.uuid4()), "user_id": user_id, "product_id": product_id, "amount": amount, "source": source_goal, "status": "active", "invested_at": datetime.utcnow().isoformat()}
    portfolios_db[investment["id"]] = investment
    return investment

async def get_portfolio(user_id: str) -> Dict:
    user_inv = [v for v in portfolios_db.values() if v.get("user_id") == user_id]
    total = sum(i.get("amount", 0) for i in user_inv)
    return {"user_id": user_id, "investments": user_inv, "total_invested": total, "total_value": total * 1.02}

async def calculate_returns(investment_id: str) -> Dict:
    inv = portfolios_db.get(investment_id)
    if not inv:
        return {"error": "Not found"}
    rate = 0.14
    returns = inv.get("amount", 0) * rate * (30 / 365)
    return {"investment_id": investment_id, "principal": inv["amount"], "rate": rate, "returns": round(returns, 2)}
