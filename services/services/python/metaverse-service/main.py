import sys as _sys, os as _os

# --- Production: Graceful Shutdown ---
import signal
import sys
import atexit
import logging

_shutdown_handlers = []

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
Metaverse Service
Integration service for metaverse platforms and virtual economies
"""
import hashlib
import json as json_mod
import sys

import redis as _redis
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app, enable_auth=True)
setup_logging("metaverse-service")
app.include_router(metrics_router)

from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum
import logging
import os
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.idempotency import IdempotencyStore

_redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
try:
    _redis_client: Optional[_redis.Redis] = _redis.from_url(_redis_url, decode_responses=True)
except Exception:
    _redis_client = None

_idem_store = IdempotencyStore("metaverse-txn", _redis_client)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/metaverse_service")

def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return conn

def init_db():
    conn = get_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS audit_log (
        id SERIAL PRIMARY KEY,
        action TEXT, entity_id TEXT, data TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS state_store (
        key TEXT PRIMARY KEY, value TEXT,
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )""")
    conn.commit()
    conn.close()

init_db()

def log_audit(action: str, entity_id: str, data: str = ""):
    try:
        conn = get_db()
        conn.execute("INSERT INTO audit_log (action, entity_id, data) VALUES (?, ?, ?)", (action, entity_id, data))
        conn.commit()
        conn.close()
    except Exception:
        pass
    title="Metaverse Service",
    description="Integration service for metaverse platforms and virtual economies",
    version="1.0.0"
)

@app.on_event("startup")
async def _start_eviction():
    _idem_store.start_eviction_job()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
class Config:
    DECENTRALAND_API_KEY = os.getenv("DECENTRALAND_API_KEY", "")
    SANDBOX_API_KEY = os.getenv("SANDBOX_API_KEY", "")
    ROBLOX_API_KEY = os.getenv("ROBLOX_API_KEY", "")
    DATABASE_URL = os.getenv("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/metaverse_service")

config = Config()

# Enums
class MetaversePlatform(str, Enum):
    DECENTRALAND = "decentraland"
    SANDBOX = "sandbox"
    ROBLOX = "roblox"
    HORIZON_WORLDS = "horizon_worlds"
    VRCHAT = "vrchat"
    CUSTOM = "custom"

class AssetType(str, Enum):
    LAND = "land"
    WEARABLE = "wearable"
    BUILDING = "building"
    AVATAR = "avatar"
    NFT = "nft"
    CURRENCY = "currency"

class TransactionType(str, Enum):
    PURCHASE = "purchase"
    SALE = "sale"
    TRANSFER = "transfer"
    RENTAL = "rental"

# Models
class MetaverseAccount(BaseModel):
    id: Optional[str] = None
    agent_id: str
    platform: MetaversePlatform
    wallet_address: str
    username: str
    avatar_url: Optional[str] = None
    created_at: Optional[datetime] = None
    is_active: bool = True

class VirtualAsset(BaseModel):
    id: Optional[str] = None
    owner_account_id: str
    platform: MetaversePlatform
    asset_type: AssetType
    name: str
    description: str
    metadata: Dict[str, Any] = {}
    price: Optional[float] = None
    currency: str = "USD"
    blockchain_id: Optional[str] = None
    created_at: Optional[datetime] = None

class VirtualLand(BaseModel):
    id: Optional[str] = None
    owner_account_id: str
    platform: MetaversePlatform
    coordinates: Dict[str, int]  # x, y, z
    size: Dict[str, int]  # width, height, depth
    name: str
    description: str
    price: float
    currency: str = "USD"
    is_for_sale: bool = False
    is_for_rent: bool = False
    monthly_rent: Optional[float] = None

class MetaverseTransaction(BaseModel):
    id: Optional[str] = None
    account_id: str
    transaction_type: TransactionType
    asset_id: str
    amount: float
    currency: str = "USD"
    counterparty_id: Optional[str] = None
    blockchain_tx_hash: Optional[str] = None
    status: str = "pending"
    timestamp: Optional[datetime] = None

class VirtualEvent(BaseModel):
    id: Optional[str] = None
    organizer_account_id: str
    platform: MetaversePlatform
    title: str
    description: str
    location: str  # Virtual location
    start_time: datetime
    end_time: datetime
    max_attendees: int
    ticket_price: float = 0.0
    attendees: List[str] = []

class MetaverseStore(BaseModel):
    id: Optional[str] = None
    owner_account_id: str
    platform: MetaversePlatform
    name: str
    description: str
    location: str  # Virtual location
    products: List[str] = []  # Product IDs
    is_open: bool = True

accounts_db: Dict[str, MetaverseAccount] = {}
assets_db: Dict[str, VirtualAsset] = {}
land_db: Dict[str, VirtualLand] = {}
transactions_db: Dict[str, MetaverseTransaction] = {}
events_db: Dict[str, VirtualEvent] = {}
stores_db: Dict[str, MetaverseStore] = {}

# API Endpoints

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "metaverse-service",
        "timestamp": datetime.utcnow().isoformat(),
        "platforms_connected": {
            "decentraland": bool(config.DECENTRALAND_API_KEY),
            "sandbox": bool(config.SANDBOX_API_KEY),
            "roblox": bool(config.ROBLOX_API_KEY)
        }
    }

@app.post("/accounts", response_model=MetaverseAccount)
async def create_metaverse_account(account: MetaverseAccount):
    """Create a metaverse account"""
    try:
        account.id = str(uuid.uuid4())
        account.created_at = datetime.utcnow()
        
        accounts_db[account.id] = account
        
        logger.info(f"Created metaverse account on {account.platform} for agent {account.agent_id}")
        return account
    except Exception as e:
        logger.error(f"Error creating account: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/accounts", response_model=List[MetaverseAccount])
async def list_metaverse_accounts(
    agent_id: Optional[str] = None,
    platform: Optional[MetaversePlatform] = None
):
    """List metaverse accounts"""
    try:
        accounts = list(accounts_db.values())
        
        if agent_id:
            accounts = [a for a in accounts if a.agent_id == agent_id]
        if platform:
            accounts = [a for a in accounts if a.platform == platform]
        
        return accounts
    except Exception as e:
        logger.error(f"Error listing accounts: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/accounts/{account_id}", response_model=MetaverseAccount)
async def get_metaverse_account(account_id: str):
    """Get a specific metaverse account"""
    if account_id not in accounts_db:
        raise HTTPException(status_code=404, detail="Account not found")
    return accounts_db[account_id]

@app.post("/assets", response_model=VirtualAsset)
async def create_virtual_asset(asset: VirtualAsset):
    """Create a virtual asset"""
    try:
        asset.id = str(uuid.uuid4())
        asset.created_at = datetime.utcnow()
        
        assets_db[asset.id] = asset
        
        logger.info(f"Created virtual asset {asset.name} for account {asset.owner_account_id}")
        return asset
    except Exception as e:
        logger.error(f"Error creating asset: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/assets", response_model=List[VirtualAsset])
async def list_virtual_assets(
    owner_account_id: Optional[str] = None,
    platform: Optional[MetaversePlatform] = None,
    asset_type: Optional[AssetType] = None
):
    """List virtual assets"""
    try:
        assets = list(assets_db.values())
        
        if owner_account_id:
            assets = [a for a in assets if a.owner_account_id == owner_account_id]
        if platform:
            assets = [a for a in assets if a.platform == platform]
        if asset_type:
            assets = [a for a in assets if a.asset_type == asset_type]
        
        return assets
    except Exception as e:
        logger.error(f"Error listing assets: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/land", response_model=VirtualLand)
async def create_virtual_land(land: VirtualLand):
    """Create/register virtual land"""
    try:
        land.id = str(uuid.uuid4())
        
        land_db[land.id] = land
        
        logger.info(f"Registered virtual land {land.name} for account {land.owner_account_id}")
        return land
    except Exception as e:
        logger.error(f"Error creating land: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/land", response_model=List[VirtualLand])
async def list_virtual_land(
    owner_account_id: Optional[str] = None,
    platform: Optional[MetaversePlatform] = None,
    for_sale: Optional[bool] = None
):
    """List virtual land"""
    try:
        lands = list(land_db.values())
        
        if owner_account_id:
            lands = [l for l in lands if l.owner_account_id == owner_account_id]
        if platform:
            lands = [l for l in lands if l.platform == platform]
        if for_sale is not None:
            lands = [l for l in lands if l.is_for_sale == for_sale]
        
        return lands
    except Exception as e:
        logger.error(f"Error listing land: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/transactions", response_model=MetaverseTransaction)
async def create_transaction(
    transaction: MetaverseTransaction,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    """Create a metaverse transaction with idempotency support."""
    try:
        if idempotency_key:
            req_data = transaction.model_dump(exclude={"id", "timestamp", "status"})
            req_hash = hashlib.sha256(json_mod.dumps(req_data, sort_keys=True, default=str).encode()).hexdigest()
            cached_raw = _idem_store.check(idempotency_key, req_hash)
            if cached_raw:
                if cached_raw.get("request_hash") != req_hash:
                    raise HTTPException(status_code=422, detail="Idempotency key reused with different request payload")
                txn_id = cached_raw.get("transaction_id") or cached_raw.get("response")
                if txn_id and txn_id in transactions_db:
                    logger.info(f"Idempotency hit for key={idempotency_key}")
                    return transactions_db[txn_id]
            else:
                acquired = _idem_store.acquire(idempotency_key, req_hash)
                if not acquired:
                    raise HTTPException(status_code=409, detail="Request is already being processed")

        transaction.id = str(uuid.uuid4())
        transaction.timestamp = datetime.utcnow()
        transaction.status = "completed"

        transactions_db[transaction.id] = transaction

        if idempotency_key:
            req_data = transaction.model_dump(exclude={"id", "timestamp", "status"})
            _idem_store.complete(
                idempotency_key,
                hashlib.sha256(json_mod.dumps(req_data, sort_keys=True, default=str).encode()).hexdigest(),
                transaction.id,
            )

        logger.info(f"Created transaction {transaction.id} for account {transaction.account_id}")
        return transaction
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating transaction: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/transactions", response_model=List[MetaverseTransaction])
async def list_transactions(
    account_id: Optional[str] = None,
    transaction_type: Optional[TransactionType] = None
):
    """List metaverse transactions"""
    try:
        transactions = list(transactions_db.values())
        
        if account_id:
            transactions = [t for t in transactions if t.account_id == account_id]
        if transaction_type:
            transactions = [t for t in transactions if t.transaction_type == transaction_type]
        
        return transactions
    except Exception as e:
        logger.error(f"Error listing transactions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/events", response_model=VirtualEvent)
async def create_virtual_event(event: VirtualEvent):
    """Create a virtual event"""
    try:
        event.id = str(uuid.uuid4())
        
        events_db[event.id] = event
        
        logger.info(f"Created virtual event {event.title} by account {event.organizer_account_id}")
        return event
    except Exception as e:
        logger.error(f"Error creating event: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/events", response_model=List[VirtualEvent])
async def list_virtual_events(
    platform: Optional[MetaversePlatform] = None,
    upcoming: bool = True
):
    """List virtual events"""
    try:
        events = list(events_db.values())
        
        if platform:
            events = [e for e in events if e.platform == platform]
        if upcoming:
            now = datetime.utcnow()
            events = [e for e in events if e.start_time > now]
        
        return events
    except Exception as e:
        logger.error(f"Error listing events: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/events/{event_id}/register")
async def register_for_event(event_id: str, account_id: str):
    """Register for a virtual event"""
    try:
        if event_id not in events_db:
            raise HTTPException(status_code=404, detail="Event not found")
        
        event = events_db[event_id]
        
        if len(event.attendees) >= event.max_attendees:
            raise HTTPException(status_code=400, detail="Event is full")
        
        if account_id not in event.attendees:
            event.attendees.append(account_id)
        
        logger.info(f"Registered account {account_id} for event {event_id}")
        return {"message": "Successfully registered for event"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error registering for event: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/stores", response_model=MetaverseStore)
async def create_metaverse_store(store: MetaverseStore):
    """Create a metaverse store"""
    try:
        store.id = str(uuid.uuid4())
        
        stores_db[store.id] = store
        
        logger.info(f"Created metaverse store {store.name} for account {store.owner_account_id}")
        return store
    except Exception as e:
        logger.error(f"Error creating store: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stores", response_model=List[MetaverseStore])
async def list_metaverse_stores(
    owner_account_id: Optional[str] = None,
    platform: Optional[MetaversePlatform] = None
):
    """List metaverse stores"""
    try:
        stores = list(stores_db.values())
        
        if owner_account_id:
            stores = [s for s in stores if s.owner_account_id == owner_account_id]
        if platform:
            stores = [s for s in stores if s.platform == platform]
        
        return stores
    except Exception as e:
        logger.error(f"Error listing stores: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/analytics/{agent_id}")
async def get_metaverse_analytics(agent_id: str):
    """Get metaverse analytics for an agent"""
    try:
        agent_accounts = [a for a in accounts_db.values() if a.agent_id == agent_id]
        account_ids = [a.id for a in agent_accounts]
        
        agent_assets = [a for a in assets_db.values() if a.owner_account_id in account_ids]
        agent_land = [l for l in land_db.values() if l.owner_account_id in account_ids]
        agent_transactions = [t for t in transactions_db.values() if t.account_id in account_ids]
        agent_stores = [s for s in stores_db.values() if s.owner_account_id in account_ids]
        
        return {
            "total_accounts": len(agent_accounts),
            "total_assets": len(agent_assets),
            "total_land_parcels": len(agent_land),
            "total_transactions": len(agent_transactions),
            "total_stores": len(agent_stores),
            "total_transaction_volume": sum(t.amount for t in agent_transactions),
            "platforms": list(set(a.platform for a in agent_accounts))
        }
    except Exception as e:
        logger.error(f"Error getting analytics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8083)

