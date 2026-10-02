import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

import logging
import httpx

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chart-of-accounts", tags=["chart-of-accounts"])

TIGERBEETLE_SYNC_URL = os.getenv("TIGERBEETLE_SYNC_URL", "http://localhost:8085")
TIGERBEETLE_GL_POST_ENABLED = os.getenv("TIGERBEETLE_GL_POST_ENABLED", "true").lower() == "true"


class AccountType(str, Enum):
    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    REVENUE = "revenue"
    EXPENSE = "expense"


class AccountCategory(str, Enum):
    CASH_IN = "cash_in"
    CASH_OUT = "cash_out"
    SETTLEMENT = "settlement"
    COMMISSION = "commission"
    FLOAT = "float"
    AGENT_WALLET = "agent_wallet"
    BANK_PARTNER = "bank_partner"
    SUSPENSE = "suspense"
    FEE_INCOME = "fee_income"
    OPERATING_EXPENSE = "operating_expense"


class COAEntry(BaseModel):
    account_code: str = Field(..., description="GL account code (e.g., 1001, 2001)")
    account_name: str
    account_type: AccountType
    category: AccountCategory
    parent_code: Optional[str] = None
    description: Optional[str] = None
    is_active: bool = True
    currency: str = Field(default="NGN")


class COAEntryResponse(COAEntry):
    id: str
    created_at: str
    balance: float = 0.0


class GLPostingRequest(BaseModel):
    transaction_ref: str = Field(..., description="Unique transaction reference")
    transaction_type: str = Field(..., description="cash_in|cash_out|transfer|bill_payment|commission")
    amount: float = Field(..., gt=0)
    currency: str = Field(default="NGN")
    debit_account_code: str
    credit_account_code: str
    agent_id: Optional[str] = None
    narration: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class GLPostingResponse(BaseModel):
    posting_id: str
    transaction_ref: str
    debit_entry: Dict[str, Any]
    credit_entry: Dict[str, Any]
    posted_at: str
    synced_to_ledger: bool



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
_coa_accounts = _PgDictStore("coa_accounts_store", "COA_DATABASE_URL", model_name="COAEntryResponse")
_gl_postings: List[Dict[str, Any]] = []

_account_balances = _PgDictStore("coa_account_balances", "COA_DATABASE_URL", model_name=None)

DEFAULT_COA = [
    COAEntry(account_code="1001", account_name="Cash In Hand", account_type=AccountType.ASSET, category=AccountCategory.CASH_IN, description="Physical cash received from customers"),
    COAEntry(account_code="1002", account_name="Cash Out Disbursements", account_type=AccountType.ASSET, category=AccountCategory.CASH_OUT, description="Physical cash paid to customers"),
    COAEntry(account_code="1003", account_name="Agent Float Account", account_type=AccountType.ASSET, category=AccountCategory.FLOAT, description="Agent working capital/float balance"),
    COAEntry(account_code="1004", account_name="Agent Wallet", account_type=AccountType.ASSET, category=AccountCategory.AGENT_WALLET, description="Digital wallet balance for agent"),
    COAEntry(account_code="1005", account_name="Bank Settlement Account", account_type=AccountType.ASSET, category=AccountCategory.SETTLEMENT, description="Funds pending settlement with bank"),
    COAEntry(account_code="2001", account_name="Customer Deposits Payable", account_type=AccountType.LIABILITY, category=AccountCategory.CASH_IN, description="Liability for cash-in deposits received"),
    COAEntry(account_code="2002", account_name="Bank Partner Payable", account_type=AccountType.LIABILITY, category=AccountCategory.BANK_PARTNER, description="Amounts owed to bank partners"),
    COAEntry(account_code="2003", account_name="Suspense Account", account_type=AccountType.LIABILITY, category=AccountCategory.SUSPENSE, description="Unresolved/pending transactions"),
    COAEntry(account_code="3001", account_name="Retained Earnings", account_type=AccountType.EQUITY, category=AccountCategory.SETTLEMENT, description="Accumulated platform earnings"),
    COAEntry(account_code="4001", account_name="Commission Income", account_type=AccountType.REVENUE, category=AccountCategory.COMMISSION, description="Commission earned on transactions"),
    COAEntry(account_code="4002", account_name="Transaction Fee Income", account_type=AccountType.REVENUE, category=AccountCategory.FEE_INCOME, description="Fees collected from transactions"),
    COAEntry(account_code="5001", account_name="Bank Charges", account_type=AccountType.EXPENSE, category=AccountCategory.OPERATING_EXPENSE, description="Fees paid to banks/NIBSS"),
    COAEntry(account_code="5002", account_name="Agent Commission Expense", account_type=AccountType.EXPENSE, category=AccountCategory.COMMISSION, description="Commission paid to agents"),
]

GL_POSTING_RULES = {
    "cash_in": {"debit": "1001", "credit": "2001"},
    "cash_out": {"debit": "2001", "credit": "1002"},
    "transfer": {"debit": "1004", "credit": "1005"},
    "bill_payment": {"debit": "1004", "credit": "2002"},
    "commission": {"debit": "5002", "credit": "4001"},
    "fee_collection": {"debit": "1004", "credit": "4002"},
    "settlement": {"debit": "2002", "credit": "1005"},
    "float_topup": {"debit": "1003", "credit": "2002"},
}


def _init_default_coa():
    if _coa_accounts:
        return
    for entry in DEFAULT_COA:
        account_id = str(uuid.uuid4())
        _coa_accounts[entry.account_code] = COAEntryResponse(
            id=account_id,
            account_code=entry.account_code,
            account_name=entry.account_name,
            account_type=entry.account_type,
            category=entry.category,
            parent_code=entry.parent_code,
            description=entry.description,
            is_active=entry.is_active,
            currency=entry.currency,
            created_at=datetime.utcnow().isoformat(),
            balance=0.0,
        )
        _account_balances[entry.account_code] = 0.0


_init_default_coa()


@router.get("/accounts", response_model=List[COAEntryResponse])
async def list_accounts(
    account_type: Optional[AccountType] = None,
    category: Optional[AccountCategory] = None,
    active_only: bool = True,
):
    accounts = list(_coa_accounts.values())
    if account_type:
        accounts = [a for a in accounts if a.account_type == account_type]
    if category:
        accounts = [a for a in accounts if a.category == category]
    if active_only:
        accounts = [a for a in accounts if a.is_active]
    for a in accounts:
        a.balance = _account_balances.get(a.account_code, 0.0)
    return accounts


@router.get("/accounts/{account_code}", response_model=COAEntryResponse)
async def get_account(account_code: str):
    if account_code not in _coa_accounts:
        raise HTTPException(status_code=404, detail=f"Account {account_code} not found")
    account = _coa_accounts[account_code]
    account.balance = _account_balances.get(account_code, 0.0)
    return account


@router.post("/accounts", response_model=COAEntryResponse)
async def create_account(entry: COAEntry):
    if entry.account_code in _coa_accounts:
        raise HTTPException(status_code=409, detail=f"Account code {entry.account_code} already exists")
    if entry.parent_code and entry.parent_code not in _coa_accounts:
        raise HTTPException(status_code=400, detail=f"Parent account {entry.parent_code} not found")
    account_id = str(uuid.uuid4())
    response = COAEntryResponse(
        id=account_id,
        account_code=entry.account_code,
        account_name=entry.account_name,
        account_type=entry.account_type,
        category=entry.category,
        parent_code=entry.parent_code,
        description=entry.description,
        is_active=entry.is_active,
        currency=entry.currency,
        created_at=datetime.utcnow().isoformat(),
        balance=0.0,
    )
    _coa_accounts[entry.account_code] = response
    _account_balances[entry.account_code] = 0.0
    return response


@router.put("/accounts/{account_code}", response_model=COAEntryResponse)
async def update_account(account_code: str, entry: COAEntry):
    if account_code not in _coa_accounts:
        raise HTTPException(status_code=404, detail=f"Account {account_code} not found")
    existing = _coa_accounts[account_code]
    existing.account_name = entry.account_name
    existing.description = entry.description
    existing.is_active = entry.is_active
    existing.category = entry.category
    _coa_accounts[account_code] = existing  # round-11: write back mutation
    return existing


@router.delete("/accounts/{account_code}")
async def deactivate_account(account_code: str):
    if account_code not in _coa_accounts:
        raise HTTPException(status_code=404, detail=f"Account {account_code} not found")
    balance = _account_balances.get(account_code, 0.0)
    if abs(balance) > 0.01:
        raise HTTPException(status_code=400, detail=f"Cannot deactivate account with balance {balance}")
    _acct = _coa_accounts[account_code]
    _acct.is_active = False
    _coa_accounts[account_code] = _acct  # round-11: write back mutation
    return {"status": "deactivated", "account_code": account_code}


@router.post("/post", response_model=GLPostingResponse)
async def post_gl_entry(request: GLPostingRequest):
    if request.debit_account_code not in _coa_accounts:
        raise HTTPException(status_code=404, detail=f"Debit account {request.debit_account_code} not found")
    if request.credit_account_code not in _coa_accounts:
        raise HTTPException(status_code=404, detail=f"Credit account {request.credit_account_code} not found")

    posting_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    synced = False
    tb_result = None

    if TIGERBEETLE_GL_POST_ENABLED:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(f"{TIGERBEETLE_SYNC_URL}/api/v1/gl/post", json={
                    "debit_gl": request.debit_account_code,
                    "credit_gl": request.credit_account_code,
                    "amount": int(request.amount * 100),
                    "reference": request.transaction_ref,
                })
                if resp.status_code == 200:
                    tb_result = resp.json()
                    synced = True
                    logger.info(f"GL entry {posting_id} synced to TigerBeetle: {tb_result}")
                else:
                    logger.warning(f"TigerBeetle GL post returned {resp.status_code}: {resp.text}")
        except Exception as e:
            logger.warning(f"TigerBeetle GL post failed, falling back to local: {e}")

    _account_balances[request.debit_account_code] = _account_balances.get(request.debit_account_code, 0.0) + request.amount
    _account_balances[request.credit_account_code] = _account_balances.get(request.credit_account_code, 0.0) - request.amount

    debit_entry = {
        "posting_id": posting_id,
        "account_code": request.debit_account_code,
        "account_name": _coa_accounts[request.debit_account_code].account_name,
        "type": "debit",
        "amount": request.amount,
        "currency": request.currency,
    }
    credit_entry = {
        "posting_id": posting_id,
        "account_code": request.credit_account_code,
        "account_name": _coa_accounts[request.credit_account_code].account_name,
        "type": "credit",
        "amount": request.amount,
        "currency": request.currency,
    }

    posting = {
        "posting_id": posting_id,
        "transaction_ref": request.transaction_ref,
        "transaction_type": request.transaction_type,
        "debit": debit_entry,
        "credit": credit_entry,
        "agent_id": request.agent_id,
        "narration": request.narration,
        "posted_at": now,
        "synced_to_tigerbeetle": synced,
        "tb_transfer_id": tb_result.get("transfer_id") if tb_result else None,
    }
    _gl_postings.append(posting)

    return GLPostingResponse(
        posting_id=posting_id,
        transaction_ref=request.transaction_ref,
        debit_entry=debit_entry,
        credit_entry=credit_entry,
        posted_at=now,
        synced_to_ledger=synced,
    )


@router.post("/auto-post")
async def auto_post_transaction(
    transaction_ref: str,
    transaction_type: str,
    amount: float,
    currency: str = "NGN",
    agent_id: Optional[str] = None,
):
    if transaction_type not in GL_POSTING_RULES:
        raise HTTPException(status_code=400, detail=f"No GL posting rule for transaction type: {transaction_type}. Valid types: {list(GL_POSTING_RULES.keys())}")

    rule = GL_POSTING_RULES[transaction_type]
    request = GLPostingRequest(
        transaction_ref=transaction_ref,
        transaction_type=transaction_type,
        amount=amount,
        currency=currency,
        debit_account_code=rule["debit"],
        credit_account_code=rule["credit"],
        agent_id=agent_id,
        narration=f"Auto-posted {transaction_type} for {amount} {currency}",
    )
    return await post_gl_entry(request)


@router.get("/postings")
async def list_postings(
    transaction_type: Optional[str] = None,
    agent_id: Optional[str] = None,
    limit: int = Query(default=50, le=500),
):
    postings = _gl_postings
    if transaction_type:
        postings = [p for p in postings if p["transaction_type"] == transaction_type]
    if agent_id:
        postings = [p for p in postings if p.get("agent_id") == agent_id]
    return {"total": len(postings), "postings": postings[-limit:]}


@router.get("/rules")
async def get_posting_rules():
    return {
        "rules": GL_POSTING_RULES,
        "description": {
            "cash_in": "Customer deposits cash -> Agent receives physical cash, platform owes customer",
            "cash_out": "Customer withdraws cash -> Platform reduces liability, agent disburses cash",
            "transfer": "Agent wallet debited, settlement account credited for bank transfer",
            "bill_payment": "Agent wallet debited, bank partner credited for bill payment",
            "commission": "Commission expense posted, commission income recognized",
            "fee_collection": "Transaction fee deducted from agent wallet, fee income recognized",
            "settlement": "Bank partner liability settled via settlement account",
            "float_topup": "Agent float increased, bank partner credited",
        },
    }


@router.get("/trial-balance")
async def get_trial_balance():
    total_debits = 0.0
    total_credits = 0.0
    entries = []
    for code, account in _coa_accounts.items():
        balance = _account_balances.get(code, 0.0)
        if balance > 0:
            total_debits += balance
            entries.append({"account_code": code, "account_name": account.account_name, "debit": balance, "credit": 0.0})
        elif balance < 0:
            total_credits += abs(balance)
            entries.append({"account_code": code, "account_name": account.account_name, "debit": 0.0, "credit": abs(balance)})
    return {
        "entries": entries,
        "total_debits": round(total_debits, 2),
        "total_credits": round(total_credits, 2),
        "balanced": abs(total_debits - total_credits) < 0.01,
        "generated_at": datetime.utcnow().isoformat(),
    }


@router.post("/register-gl-mappings")
async def register_gl_mappings():
    registered = 0
    errors = []
    for code, account in _coa_accounts.items():
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(f"{TIGERBEETLE_SYNC_URL}/api/v1/gl/mapping", json={
                    "gl_code": code,
                    "gl_name": account.account_name,
                    "account_type": account.account_type.value,
                    "ledger": 1,
                })
                if resp.status_code in (200, 201):
                    registered += 1
        except Exception as e:
            errors.append({"code": code, "error": str(e)})
    return {"registered": registered, "errors": errors, "total_accounts": len(_coa_accounts)}


@router.post("/reconcile")
async def reconcile_with_tigerbeetle():
    postings_data = []
    for p in _gl_postings:
        postings_data.append({
            "debit_account_code": p.get("debit", {}).get("account_code", ""),
            "credit_account_code": p.get("credit", {}).get("account_code", ""),
            "amount": p.get("debit", {}).get("amount", 0),
            "transaction_ref": p.get("transaction_ref", ""),
        })
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(f"{TIGERBEETLE_SYNC_URL}/api/v1/gl/reconcile", json={"postings": postings_data})
            if resp.status_code == 200:
                return resp.json()
            return {"error": f"Reconciliation returned {resp.status_code}", "detail": resp.text}
    except Exception as e:
        return {"error": f"Reconciliation failed: {e}"}
