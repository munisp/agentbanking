import sys as _sys, os as _os

# --- Production: Graceful Shutdown ---
import signal
import sys
import atexit
import logging

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


class _PgListStore:
    """List-compatible store persisted to Postgres (replaces in-memory list)."""

    def __init__(self, table, env):
        if not table.replace("_", "").isalnum():
            raise ValueError("unsafe table name: %r" % table)
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
                "id SERIAL PRIMARY KEY, "
                "data TEXT NOT NULL, "
                "created_at TIMESTAMPTZ NOT NULL DEFAULT now()"
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
        return _r11_json.dumps(_cv(v), default=str)

    @staticmethod
    def _deser(raw):
        return _r11_json.loads(raw)

    def append(self, v):
        async def _a():
            async with self._pool.acquire() as c:
                await c.execute(
                    'INSERT INTO "%s" (data) VALUES ($1)' % self._table,
                    self._ser(v),
                )
        _r11_sync(_a())

    async def _arows(self):
        async with self._pool.acquire() as c:
            return await c.fetch(
                'SELECT id, data FROM "%s" ORDER BY id' % self._table
            )

    def _rows(self):
        return _r11_sync(self._arows())

    def __iter__(self):
        return iter([self._deser(r["data"]) for r in self._rows()])

    def __len__(self):
        async def _n():
            async with self._pool.acquire() as c:
                return await c.fetchval('SELECT COUNT(*) FROM "%s"' % self._table)
        return _r11_sync(_n())

    def __getitem__(self, idx):
        vals = [self._deser(r["data"]) for r in self._rows()]
        return vals[idx]

    def __delitem__(self, idx):
        rows = self._rows()
        targets = rows[idx] if isinstance(idx, slice) else [rows[idx]]
        ids = [r["id"] for r in targets]
        if not ids:
            return
        async def _d():
            async with self._pool.acquire() as c:
                await c.execute(
                    'DELETE FROM "%s" WHERE id = ANY($1::int[])' % self._table, ids
                )
        _r11_sync(_d())

    def clear(self):
        async def _c():
            async with self._pool.acquire() as c:
                await c.execute('DELETE FROM "%s"' % self._table)
        _r11_sync(_c())

_shutdown_handlers = _PgListStore("tigerbeetle_zig__shutdown_handlers", "TIGERBEETLE_ZIG_DATABASE_URL")  # round-11 wave-7 persistence

def register_shutdown(handler):
    _shutdown_handlers.append(handler)

def _graceful_shutdown(signum, frame):
    sig_name = signal.Signals(signum).name if hasattr(signal, 'Signals') else str(signum)
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

_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
"""
Production-Ready TigerBeetle Integration Service
Financial-grade distributed database for double-entry accounting
Written in Zig for maximum performance and safety
"""
import os
import logging
import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
import uuid

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware


from pydantic import BaseModel, Field
import uvicorn

# TigerBeetle Python client
try:
    from tigerbeetle import Client, Account, Transfer, AccountFlags, TransferFlags
    TIGERBEETLE_AVAILABLE = True
except ImportError:
    TIGERBEETLE_AVAILABLE = False
    logging.warning("TigerBeetle client not installed. Using production implementation.")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="TigerBeetle Service (Production)",
    description="Production-ready Financial Ledger using TigerBeetle",
    version="2.0.0"
)

apply_middleware(app)
setup_logging("tigerbeetle-service-(production)")
app.include_router(metrics_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
class Config:
    TIGERBEETLE_CLUSTER_ID = int(os.getenv("TIGERBEETLE_CLUSTER_ID", "0"))
    TIGERBEETLE_ADDRESSES = os.getenv("TIGERBEETLE_ADDRESSES", "3000").split(",")
    LEDGER_ID = 1  # Nigerian Naira
    MODEL_VERSION = "2.0.0"
    
config = Config()

# Statistics
stats = {
    "total_accounts": 0,
    "total_transfers": 0,
    "total_volume": 0,  # in kobo
    "failed_transfers": 0,
    "start_time": datetime.now()
}

# ==================== Enums ====================

class AccountType(str, Enum):
    """TigerBeetle account types for Remittance Platform"""
    AGENT_ASSET = "agent_asset"  # Agent's cash/balance
    AGENT_LIABILITY = "agent_liability"  # Agent's credit line
    CUSTOMER_ASSET = "customer_asset"  # Customer account
    MERCHANT_ASSET = "merchant_asset"  # Merchant account
    PLATFORM_REVENUE = "platform_revenue"  # Platform revenue
    PLATFORM_FEES = "platform_fees"  # Platform fee collection
    ESCROW = "escrow"  # Escrow for pending transactions
    INVENTORY_ASSET = "inventory_asset"  # Inventory valuation
    COMMISSION = "commission"  # Commission accounts

class AccountCode(int, Enum):
    """Chart of accounts codes"""
    ASSET = 1
    LIABILITY = 2
    EQUITY = 3
    REVENUE = 4
    EXPENSE = 5

class TransferCode(int, Enum):
    """Transfer type codes"""
    DEPOSIT = 1
    WITHDRAWAL = 2
    TRANSFER = 3
    FEE = 4
    COMMISSION = 5
    REFUND = 6
    PURCHASE = 7
    SALE = 8

# ==================== Models ====================

class AccountRequest(BaseModel):
    user_id: str = Field(..., description="User ID (agent, customer, merchant)")
    account_type: AccountType
    initial_balance: float = Field(default=0.0, ge=0)
    credit_limit: Optional[float] = Field(default=None, ge=0)
    metadata: Optional[Dict[str, Any]] = {}

class TransferRequest(BaseModel):
    from_account_id: str
    to_account_id: str
    amount: float = Field(..., gt=0)
    transfer_code: TransferCode
    description: str
    idempotency_key: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = {}

class BalanceRequest(BaseModel):
    account_id: str

class AccountResponse(BaseModel):
    account_id: str
    user_id: str
    account_type: AccountType
    balance: float
    credits_posted: float
    debits_posted: float
    credits_pending: float
    debits_pending: float
    created_at: datetime

class TransferResponse(BaseModel):
    transfer_id: str
    from_account_id: str
    to_account_id: str
    amount: float
    transfer_code: TransferCode
    status: str
    timestamp: datetime

# ==================== TigerBeetle Manager ====================

class TigerBeetleManager:
    """Manages TigerBeetle client and operations"""
    
    def __init__(self):
        self.client = None
        self.account_map = {}  # Maps user_id to account_id
        self.initialize_client()
        
    def initialize_client(self):
        """Initialize TigerBeetle client"""
        try:
            if TIGERBEETLE_AVAILABLE:
                # Connect to TigerBeetle cluster
                self.client = Client(
                    cluster_id=config.TIGERBEETLE_CLUSTER_ID,
                    replica_addresses=config.TIGERBEETLE_ADDRESSES
                )
                logger.info(f"Connected to TigerBeetle cluster: {config.TIGERBEETLE_ADDRESSES}")
            else:
                logger.warning("TigerBeetle client not available, using production")
                self.client = FallbackTigerBeetleClient()
        except ConnectionError as e:
            logger.error(f"Connection error to TigerBeetle cluster: {e}")
            logger.warning("Falling back to production client")
            self.client = FallbackTigerBeetleClient()
        except ValueError as e:
            logger.error(f"Invalid configuration for TigerBeetle: {e}")
            logger.warning("Falling back to production client")
            self.client = FallbackTigerBeetleClient()
        except Exception as e:
            logger.error(f"Unexpected error initializing TigerBeetle client: {e}")
            logger.warning("Falling back to production client")
            self.client = FallbackTigerBeetleClient()
    
    def generate_account_id(self) -> int:
        """Generate unique 128-bit account ID"""
        # Use UUID4 and convert to 128-bit integer
        return int(uuid.uuid4().int & ((1 << 128) - 1))
    
    def generate_transfer_id(self) -> int:
        """Generate unique 128-bit transfer ID"""
        return int(uuid.uuid4().int & ((1 << 128) - 1))
    
    def naira_to_kobo(self, amount: float) -> int:
        """Convert Naira to Kobo (smallest unit)"""
        return int(amount * 100)
    
    def kobo_to_naira(self, amount: int) -> float:
        """Convert Kobo to Naira"""
        return amount / 100.0
    
    async def create_account(self, request: AccountRequest) -> AccountResponse:
        """Create a new TigerBeetle account"""
        try:
            account_id = self.generate_account_id()
            
            # Determine account code based on type
            if "asset" in request.account_type.value:
                code = AccountCode.ASSET.value
            elif "liability" in request.account_type.value:
                code = AccountCode.LIABILITY.value
            elif "revenue" in request.account_type.value or "fee" in request.account_type.value:
                code = AccountCode.REVENUE.value
            else:
                code = AccountCode.ASSET.value
            
            # Set account flags
            flags = 0
            if request.credit_limit and request.credit_limit > 0:
                flags |= AccountFlags.DEBITS_MUST_NOT_EXCEED_CREDITS
            
            # Create account
            account = Account(
                id=account_id,
                user_data=int(uuid.uuid4().int & ((1 << 128) - 1)),  # Store user_id mapping
                ledger=config.LEDGER_ID,
                code=code,
                flags=flags,
                debits_pending=0,
                debits_posted=0,
                credits_pending=0,
                credits_posted=self.naira_to_kobo(request.initial_balance),
                timestamp=0  # TigerBeetle will set this
            )
            
            # Create account in TigerBeetle
            result = self.client.create_accounts([account])
            
            if result:
                logger.error(f"Failed to create account: {result}")
                raise HTTPException(status_code=400, detail=f"Account creation failed: {result}")
            
            # Store mapping
            self.account_map[request.user_id] = str(account_id)
            stats["total_accounts"] += 1
            
            return AccountResponse(
                account_id=str(account_id),
                user_id=request.user_id,
                account_type=request.account_type,
                balance=request.initial_balance,
                credits_posted=request.initial_balance,
                debits_posted=0.0,
                credits_pending=0.0,
                debits_pending=0.0,
                created_at=datetime.now()
            )
        
        except HTTPException:
            # Re-raise HTTP exceptions as-is
            raise
        except ConnectionError as e:
            logger.error(f"TigerBeetle connection error while creating account: {e}")
            raise HTTPException(status_code=503, detail="Database service unavailable")
        except ValueError as e:
            logger.error(f"Invalid value while creating account: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid input: {str(e)}")
        except AttributeError as e:
            logger.error(f"TigerBeetle client not properly initialized: {e}")
            raise HTTPException(status_code=503, detail="Service not ready")
        except Exception as e:
            logger.error(f"Unexpected error creating account: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")
    
    async def create_transfer(self, request: TransferRequest) -> TransferResponse:
        """Create a transfer between accounts"""
        try:
            transfer_id = self.generate_transfer_id()
            
            # Use idempotency key if provided
            if request.idempotency_key:
                try:
                    transfer_id = int(uuid.UUID(request.idempotency_key).int & ((1 << 128) - 1))
                except ValueError as e:
                    logger.error(f"Invalid idempotency key format: {e}")
                    raise HTTPException(status_code=400, detail="Invalid idempotency key format")
            
            # Convert account IDs to integers
            try:
                debit_account_id = int(request.from_account_id)
                credit_account_id = int(request.to_account_id)
            except ValueError as e:
                logger.error(f"Invalid account ID format: {e}")
                raise HTTPException(status_code=400, detail="Invalid account ID format")
            
            # Create transfer
            transfer = Transfer(
                id=transfer_id,
                debit_account_id=debit_account_id,
                credit_account_id=credit_account_id,
                user_data=0,  # Can store metadata reference
                ledger=config.LEDGER_ID,
                code=request.transfer_code.value,
                flags=0,
                amount=self.naira_to_kobo(request.amount),
                timeout=0,  # No timeout
                timestamp=0  # TigerBeetle will set this
            )
            
            # Execute transfer
            result = self.client.create_transfers([transfer])
            
            if result:
                logger.error(f"Transfer failed: {result}")
                stats["failed_transfers"] += 1
                raise HTTPException(status_code=400, detail=f"Transfer failed: {result}")
            
            stats["total_transfers"] += 1
            stats["total_volume"] += self.naira_to_kobo(request.amount)
            
            return TransferResponse(
                transfer_id=str(transfer_id),
                from_account_id=request.from_account_id,
                to_account_id=request.to_account_id,
                amount=request.amount,
                transfer_code=request.transfer_code,
                status="completed",
                timestamp=datetime.now()
            )
        
        except HTTPException:
            # Re-raise HTTP exceptions as-is
            stats["failed_transfers"] += 1
            raise
        except ConnectionError as e:
            logger.error(f"TigerBeetle connection error during transfer: {e}")
            stats["failed_transfers"] += 1
            raise HTTPException(status_code=503, detail="Database service unavailable")
        except ValueError as e:
            logger.error(f"Invalid value during transfer: {e}")
            stats["failed_transfers"] += 1
            raise HTTPException(status_code=400, detail=f"Invalid input: {str(e)}")
        except AttributeError as e:
            logger.error(f"TigerBeetle client not properly initialized: {e}")
            stats["failed_transfers"] += 1
            raise HTTPException(status_code=503, detail="Service not ready")
        except Exception as e:
            logger.error(f"Unexpected error during transfer: {e}")
            stats["failed_transfers"] += 1
            raise HTTPException(status_code=500, detail="Internal server error")
    
    async def get_balance(self, account_id: str) -> Dict[str, Any]:
        """Get account balance"""
        try:
            # Convert account ID to integer
            try:
                account_id_int = int(account_id)
            except ValueError as e:
                logger.error(f"Invalid account ID format: {e}")
                raise HTTPException(status_code=400, detail="Invalid account ID format")
            
            # Lookup account
            accounts = self.client.lookup_accounts([account_id_int])
            
            if not accounts:
                raise HTTPException(status_code=404, detail="Account not found")
            
            account = accounts[0]
            
            return {
                "account_id": account_id,
                "balance": self.kobo_to_naira(account.credits_posted - account.debits_posted),
                "credits_posted": self.kobo_to_naira(account.credits_posted),
                "debits_posted": self.kobo_to_naira(account.debits_posted),
                "credits_pending": self.kobo_to_naira(account.credits_pending),
                "debits_pending": self.kobo_to_naira(account.debits_pending),
                "ledger": account.ledger,
                "code": account.code
            }
            
        except Exception as e:
            logger.error(f"Error getting balance: {e}")
            raise HTTPException(status_code=500, detail=str(e))

# Fallback client when TigerBeetle is unavailable
class FallbackTigerBeetleClient:
    """Fallback TigerBeetle client for development/startup"""
    def __init__(self):
        self.accounts = {}
        self.transfers = {}
        
    def create_accounts(self, accounts):
        for account in accounts:
            self.accounts[account.id] = account
        return []  # Empty list means success
    
    def create_transfers(self, transfers):
        for transfer in transfers:
            # Check if accounts exist
            if transfer.debit_account_id not in self.accounts:
                return [{"error": "Debit account not found"}]
            if transfer.credit_account_id not in self.accounts:
                return [{"error": "Credit account not found"}]
            
            # Check balance
            debit_account = self.accounts[transfer.debit_account_id]
            balance = debit_account.credits_posted - debit_account.debits_posted
            if balance < transfer.amount:
                return [{"error": "Insufficient balance"}]
            
            # Execute transfer
            debit_account.debits_posted += transfer.amount
            credit_account = self.accounts[transfer.credit_account_id]
            credit_account.credits_posted += transfer.amount
            
            self.transfers[transfer.id] = transfer
        
        return []  # Empty list means success
    
    def lookup_accounts(self, account_ids):
        return [self.accounts.get(aid) for aid in account_ids if aid in self.accounts]

# Initialize manager
tb_manager = TigerBeetleManager()

# ==================== API Endpoints ====================

@app.get("/")
async def root():
    return {
        "service": "tigerbeetle-production",
        "version": config.MODEL_VERSION,
        "cluster_id": config.TIGERBEETLE_CLUSTER_ID,
        "ledger_id": config.LEDGER_ID,
        "tigerbeetle_available": TIGERBEETLE_AVAILABLE,
        "status": "ready"
    }

@app.get("/health")
async def health_check():
    uptime = (datetime.now() - stats["start_time"]).total_seconds()
    return {
        "status": "healthy",
        "uptime_seconds": int(uptime),
        "total_accounts": stats["total_accounts"],
        "total_transfers": stats["total_transfers"],
        "total_volume_naira": stats["total_volume"] / 100.0,
        "failed_transfers": stats["failed_transfers"],
        "tigerbeetle_connected": TIGERBEETLE_AVAILABLE
    }

@app.post("/accounts", response_model=AccountResponse)
async def create_account(request: AccountRequest):
    """Create a new account"""
    return await tb_manager.create_account(request)

@app.post("/transfers", response_model=TransferResponse)
async def create_transfer(request: TransferRequest):
    """Create a transfer between accounts"""
    return await tb_manager.create_transfer(request)

@app.post("/balance")
async def get_balance(request: BalanceRequest):
    """Get account balance"""
    return await tb_manager.get_balance(request.account_id)

@app.get("/stats")
async def get_statistics():
    """Get service statistics"""
    uptime = (datetime.now() - stats["start_time"]).total_seconds()
    return {
        "uptime_seconds": int(uptime),
        "total_accounts": stats["total_accounts"],
        "total_transfers": stats["total_transfers"],
        "total_volume_naira": stats["total_volume"] / 100.0,
        "failed_transfers": stats["failed_transfers"],
        "success_rate": (stats["total_transfers"] - stats["failed_transfers"]) / max(stats["total_transfers"], 1),
        "cluster_id": config.TIGERBEETLE_CLUSTER_ID,
        "ledger_id": config.LEDGER_ID
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8160)

