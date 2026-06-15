import httpx
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

apply_middleware(app, enable_auth=True)
setup_logging("gaming-integration-service")
app.include_router(metrics_router)

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


# ── OpenTelemetry Tracing ────────────────────────────────────────────────────
_otel_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
if _otel_endpoint:
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        _resource = Resource.create({
            "service.name": os.environ.get("OTEL_SERVICE_NAME", "gaming-integration"),
            "service.version": os.environ.get("OTEL_SERVICE_VERSION", "1.0.0"),
            "deployment.environment": os.environ.get("ENVIRONMENT", "production"),
        })
        _provider = TracerProvider(resource=_resource)
        _exporter = OTLPSpanExporter(endpoint=f"{_otel_endpoint}/v1/traces")
        _provider.add_span_processor(BatchSpanProcessor(_exporter))
        trace.set_tracer_provider(_provider)
        logging.getLogger(__name__).info(f"[OTel] Tracing enabled → {_otel_endpoint}")
    except ImportError:
        logging.getLogger(__name__).warning("[OTel] opentelemetry packages not installed — tracing disabled")


# ── Middleware: Kafka via Dapr ─────────────────────────────────────────────────

DAPR_HTTP_PORT = os.environ.get("DAPR_HTTP_PORT", "3500")

async def publish_kafka(topic: str, data: dict):
    """Publish domain event to Kafka via Dapr sidecar."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            url = f"http://localhost:{DAPR_HTTP_PORT}/v1.0/publish/kafka-pubsub/{topic}"
            resp = await client.post(url, json=data)
            if resp.status_code < 300:
                logger.info(f"Published to {topic}")
            else:
                logger.warning(f"Dapr publish to {topic} returned {resp.status_code}")
    except Exception as e:
        logger.warning(f"Failed to publish to {topic}: {e}")

app = FastAPI(
# Instrument FastAPI with OpenTelemetry
if _otel_endpoint:
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
    except (ImportError, Exception):
        pass


import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/gaming_integration")

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
        conn.execute("INSERT INTO audit_log (action, entity_id, data) VALUES (%s, %s, %s)", (action, entity_id, data))
        conn.commit()
        conn.close()
    except Exception:
        pass
    title="Gaming Integration Service",
    description="Integration service for gaming platforms and in-game purchases",
    version="1.0.0"
)

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
    DATABASE_URL = os.getenv("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/gaming_integration")

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
gaming_accounts_db: Dict[str, GamingAccount] = {}
games_db: Dict[str, Game] = {}
items_db: Dict[str, InGameItem] = {}
purchases_db: Dict[str, Purchase] = {}
progress_db: Dict[str, PlayerProgress] = {}

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



@app.on_event("startup")
async def startup_event():
    """Register service with Kafka on startup."""
    await publish_kafka("gaming.integration.started", {
        "service": "gaming-integration",
        "timestamp": datetime.utcnow().isoformat() if "datetime" in dir() else "startup",
    })
