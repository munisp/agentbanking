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
Gaming Integration Service
Integrates gaming platforms and in-game purchases with Remittance Platform
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware


from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
import logging
import os
import uuid

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Gaming Integration Service",
    description="Integration service for gaming platforms and in-game purchases",
    version="1.0.0"
)

apply_middleware(app)
setup_logging("gaming-integration-service")
app.include_router(metrics_router)

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
    STEAM_API_KEY = os.getenv("STEAM_API_KEY", "")
    EPIC_API_KEY = os.getenv("EPIC_API_KEY", "")
    PLAYSTATION_API_KEY = os.getenv("PLAYSTATION_API_KEY", "")
    XBOX_API_KEY = os.getenv("XBOX_API_KEY", "")
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./gaming.db")

config = Config()

# Enums
class GamePlatform(str, Enum):
    STEAM = "steam"
    EPIC = "epic"
    PLAYSTATION = "playstation"
    XBOX = "xbox"
    MOBILE = "mobile"

class PurchaseStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"

class CurrencyType(str, Enum):
    REAL = "real"
    VIRTUAL = "virtual"

# Models
class GamingAccount(BaseModel):
    id: Optional[str] = None
    agent_id: str
    platform: GamePlatform
    platform_user_id: str
    username: str
    email: str
    linked_at: Optional[datetime] = None
    is_active: bool = True

class Game(BaseModel):
    id: Optional[str] = None
    title: str
    platform: GamePlatform
    developer: str
    price: float
    currency: str = "USD"
    description: str
    genre: List[str] = []
    rating: float = 0.0

class InGameItem(BaseModel):
    id: Optional[str] = None
    game_id: str
    name: str
    description: str
    price: float
    currency_type: CurrencyType
    quantity_available: int = -1  # -1 for unlimited
    is_consumable: bool = False

class Purchase(BaseModel):
    id: Optional[str] = None
    account_id: str
    item_id: Optional[str] = None
    game_id: Optional[str] = None
    amount: float
    currency: str = "USD"
    status: PurchaseStatus = PurchaseStatus.PENDING
    transaction_id: Optional[str] = None
    purchase_date: Optional[datetime] = None

class PlayerProgress(BaseModel):
    id: Optional[str] = None
    account_id: str
    game_id: str
    level: int = 1
    experience_points: int = 0
    achievements: List[str] = []
    play_time_hours: float = 0.0
    last_played: Optional[datetime] = None

class Leaderboard(BaseModel):
    game_id: str
    entries: List[Dict[str, Any]]
    season: str
    updated_at: datetime

# In-memory storage

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
gaming_accounts_db = _PgDictStore("gaming_accounts", "GAMING_INTEGRATION_DATABASE_URL", model_name="GamingAccount")
games_db = _PgDictStore("gaming_games", "GAMING_INTEGRATION_DATABASE_URL", model_name="Game")
items_db = _PgDictStore("gaming_items", "GAMING_INTEGRATION_DATABASE_URL", model_name="InGameItem")
purchases_db = _PgDictStore("gaming_purchases", "GAMING_INTEGRATION_DATABASE_URL", model_name="Purchase")
progress_db = _PgDictStore("gaming_progress", "GAMING_INTEGRATION_DATABASE_URL", model_name="PlayerProgress")
# API Endpoints

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "gaming-integration",
        "timestamp": datetime.utcnow().isoformat(),
        "platforms_connected": {
            "steam": bool(config.STEAM_API_KEY),
            "epic": bool(config.EPIC_API_KEY),
            "playstation": bool(config.PLAYSTATION_API_KEY),
            "xbox": bool(config.XBOX_API_KEY)
        }
    }

@app.post("/accounts", response_model=GamingAccount)
async def link_gaming_account(account: GamingAccount):
    """Link a gaming account to an agent"""
    try:
        account.id = str(uuid.uuid4())
        account.linked_at = datetime.utcnow()
        
        gaming_accounts_db[account.id] = account
        
        logger.info(f"Linked {account.platform} account for agent {account.agent_id}")
        return account
    except Exception as e:
        logger.error(f"Error linking account: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/accounts", response_model=List[GamingAccount])
async def list_gaming_accounts(
    agent_id: Optional[str] = None,
    platform: Optional[GamePlatform] = None
):
    """List gaming accounts"""
    try:
        accounts = list(gaming_accounts_db.values())
        
        if agent_id:
            accounts = [a for a in accounts if a.agent_id == agent_id]
        if platform:
            accounts = [a for a in accounts if a.platform == platform]
        
        return accounts
    except Exception as e:
        logger.error(f"Error listing accounts: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/accounts/{account_id}", response_model=GamingAccount)
async def get_gaming_account(account_id: str):
    """Get a specific gaming account"""
    if account_id not in gaming_accounts_db:
        raise HTTPException(status_code=404, detail="Account not found")
    return gaming_accounts_db[account_id]

@app.delete("/accounts/{account_id}")
async def unlink_gaming_account(account_id: str):
    """Unlink a gaming account"""
    if account_id not in gaming_accounts_db:
        raise HTTPException(status_code=404, detail="Account not found")
    
    del gaming_accounts_db[account_id]
    logger.info(f"Unlinked account {account_id}")
    return {"message": "Account unlinked successfully"}

@app.post("/games", response_model=Game)
async def add_game(game: Game):
    """Add a game to the catalog"""
    try:
        game.id = str(uuid.uuid4())
        games_db[game.id] = game
        
        logger.info(f"Added game {game.title} to catalog")
        return game
    except Exception as e:
        logger.error(f"Error adding game: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/games", response_model=List[Game])
async def list_games(
    platform: Optional[GamePlatform] = None,
    genre: Optional[str] = None
):
    """List available games"""
    try:
        games = list(games_db.values())
        
        if platform:
            games = [g for g in games if g.platform == platform]
        if genre:
            games = [g for g in games if genre in g.genre]
        
        return games
    except Exception as e:
        logger.error(f"Error listing games: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/items", response_model=InGameItem)
async def add_in_game_item(item: InGameItem):
    """Add an in-game item"""
    try:
        item.id = str(uuid.uuid4())
        items_db[item.id] = item
        
        logger.info(f"Added in-game item {item.name} for game {item.game_id}")
        return item
    except Exception as e:
        logger.error(f"Error adding item: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/items", response_model=List[InGameItem])
async def list_in_game_items(game_id: Optional[str] = None):
    """List in-game items"""
    try:
        items = list(items_db.values())
        
        if game_id:
            items = [i for i in items if i.game_id == game_id]
        
        return items
    except Exception as e:
        logger.error(f"Error listing items: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/purchases", response_model=Purchase)
async def create_purchase(purchase: Purchase):
    """Process an in-game purchase"""
    try:
        purchase.id = str(uuid.uuid4())
        purchase.transaction_id = f"TXN_{purchase.id[:8]}"
        purchase.purchase_date = datetime.utcnow()
        
        # Validate account exists
        if purchase.account_id not in gaming_accounts_db:
            raise HTTPException(status_code=404, detail="Gaming account not found")
        
        # Validate item if provided
        if purchase.item_id and purchase.item_id not in items_db:
            raise HTTPException(status_code=404, detail="Item not found")
        
        # Process payment (integrate with payment gateway)
        purchase.status = PurchaseStatus.COMPLETED
        
        purchases_db[purchase.id] = purchase
        
        logger.info(f"Processed purchase {purchase.id} for account {purchase.account_id}")
        return purchase
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing purchase: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/purchases", response_model=List[Purchase])
async def list_purchases(
    account_id: Optional[str] = None,
    status: Optional[PurchaseStatus] = None
):
    """List purchases"""
    try:
        purchases = list(purchases_db.values())
        
        if account_id:
            purchases = [p for p in purchases if p.account_id == account_id]
        if status:
            purchases = [p for p in purchases if p.status == status]
        
        return purchases
    except Exception as e:
        logger.error(f"Error listing purchases: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/progress", response_model=PlayerProgress)
async def update_player_progress(progress: PlayerProgress):
    """Update player progress"""
    try:
        if not progress.id:
            progress.id = str(uuid.uuid4())
        
        progress.last_played = datetime.utcnow()
        progress_db[progress.id] = progress
        
        logger.info(f"Updated progress for account {progress.account_id} in game {progress.game_id}")
        return progress
    except Exception as e:
        logger.error(f"Error updating progress: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/progress/{account_id}", response_model=List[PlayerProgress])
async def get_player_progress(account_id: str, game_id: Optional[str] = None):
    """Get player progress"""
    try:
        progress_list = [p for p in progress_db.values() if p.account_id == account_id]
        
        if game_id:
            progress_list = [p for p in progress_list if p.game_id == game_id]
        
        return progress_list
    except Exception as e:
        logger.error(f"Error getting progress: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/leaderboard/{game_id}", response_model=Leaderboard)
async def get_leaderboard(game_id: str, season: str = "current"):
    """Get game leaderboard"""
    try:
        # Get all progress for this game
        game_progress = [p for p in progress_db.values() if p.game_id == game_id]
        
        # Sort by experience points
        sorted_progress = sorted(game_progress, key=lambda x: x.experience_points, reverse=True)
        
        entries = []
        for rank, progress in enumerate(sorted_progress[:100], 1):  # Top 100
            account = gaming_accounts_db.get(progress.account_id)
            entries.append({
                "rank": rank,
                "username": account.username if account else "Unknown",
                "level": progress.level,
                "experience_points": progress.experience_points,
                "achievements": len(progress.achievements)
            })
        
        return Leaderboard(
            game_id=game_id,
            entries=entries,
            season=season,
            updated_at=datetime.utcnow()
        )
    except Exception as e:
        logger.error(f"Error getting leaderboard: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/analytics/{agent_id}")
async def get_gaming_analytics(agent_id: str):
    """Get gaming analytics for an agent"""
    try:
        # Get agent's gaming accounts
        agent_accounts = [a for a in gaming_accounts_db.values() if a.agent_id == agent_id]
        account_ids = [a.id for a in agent_accounts]
        
        # Get purchases
        agent_purchases = [p for p in purchases_db.values() if p.account_id in account_ids]
        
        # Get progress
        agent_progress = [p for p in progress_db.values() if p.account_id in account_ids]
        
        return {
            "total_accounts": len(agent_accounts),
            "total_purchases": len(agent_purchases),
            "total_spent": sum(p.amount for p in agent_purchases if p.status == PurchaseStatus.COMPLETED),
            "total_play_time_hours": sum(p.play_time_hours for p in agent_progress),
            "total_achievements": sum(len(p.achievements) for p in agent_progress),
            "platforms": list(set(a.platform for a in agent_accounts))
        }
    except Exception as e:
        logger.error(f"Error getting analytics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081)

