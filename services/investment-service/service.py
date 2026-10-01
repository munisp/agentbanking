"""Investment Service - Production Implementation"""
from datetime import datetime
from typing import Dict, Any, List, Optional
import uuid, os, logging

logger = logging.getLogger(__name__)
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
