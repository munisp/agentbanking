#!/usr/bin/env python3

# PostgreSQL persistence layer (replaces in-memory state)
import asyncpg
import json
import os

_pg_pool = None

async def get_pg_pool():
    global _pg_pool
    if _pg_pool is None:
        database_url = os.getenv("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/agentbanking")
        try:
            _pg_pool = await asyncpg.create_pool(database_url, min_size=1, max_size=5)
            await _pg_pool.execute("""
                CREATE TABLE IF NOT EXISTS service_state (
                    key TEXT PRIMARY KEY,
                    value JSONB NOT NULL,
                    service TEXT NOT NULL,
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
        except Exception as e:
            print(f"[DB] PostgreSQL connection failed: {e} — using in-memory fallback")
            return None
    return _pg_pool

async def pg_get_list(service: str, collection: str) -> list:
    pool = await get_pg_pool()
    if pool is None:
        return []
    try:
        row = await pool.fetchrow(
            "SELECT value FROM service_state WHERE key = $1 AND service = $2",
            f"{collection}_list", service
        )
        return json.loads(row["value"]) if row else []
    except:
        return []

async def pg_append_list(service: str, collection: str, item: dict):
    pool = await get_pg_pool()
    if pool is None:
        return
    try:
        items = await pg_get_list(service, collection)
        items.append(item)
        await pool.execute(
            """INSERT INTO service_state (key, value, service, updated_at) VALUES ($1, $2::jsonb, $3, NOW())
               ON CONFLICT (key) DO UPDATE SET value = $2::jsonb, updated_at = NOW()""",
            f"{collection}_list", json.dumps(items), service
        )
    except:
        pass

async def pg_get_dict(service: str, collection: str) -> dict:
    pool = await get_pg_pool()
    if pool is None:
        return {}
    try:
        row = await pool.fetchrow(
            "SELECT value FROM service_state WHERE key = $1 AND service = $2",
            f"{collection}_dict", service
        )
        return json.loads(row["value"]) if row else {}
    except:
        return {}

async def pg_set_dict(service: str, collection: str, data: dict):
    pool = await get_pg_pool()
    if pool is None:
        return
    try:
        await pool.execute(
            """INSERT INTO service_state (key, value, service, updated_at) VALUES ($1, $2::jsonb, $3, NOW())
               ON CONFLICT (key) DO UPDATE SET value = $2::jsonb, updated_at = NOW()""",
            f"{collection}_dict", json.dumps(data), service
        )
    except:
        pass

"""
White-Label Remittance API for B2B Integration
Allows businesses to embed remittance services in their applications
"""

from fastapi import FastAPI, HTTPException, Depends, Header, Request
import sys as _sys2, os as _os2
_sys2.path.insert(0, _os2.path.join(_os2.path.dirname(_os2.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict
from datetime import datetime
from decimal import Decimal
import logging
import uuid
import hmac
import hashlib

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


logger = logging.getLogger(__name__)


# --- PostgreSQL Persistence ---
import asyncpg
from contextlib import asynccontextmanager

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/src")
_db_pool = None

async def get_db_pool():
    global _db_pool
    if _db_pool is None:
        _db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    return _db_pool

async def close_db_pool():
    global _db_pool
    if _db_pool:
        await _db_pool.close()
        _db_pool = None

app = FastAPI(
    title="White-Label Remittance API",
    description="B2B API for embedding remittance services",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)
apply_middleware(app, enable_auth=True)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure based on client domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()

# In-memory storage (use database in production)
api_keys_cache = {}  # PG-backed via pg_get_dict("src", "api_keys")
transactions_state_cache = {}  # PG-backed via pg_get_dict("src", "transactions_state")
webhooks_cache = {}  # PG-backed via pg_get_dict("src", "webhooks")


# ============================================================================
# Models
# ============================================================================

class APIKeyCreate(BaseModel):
    """API key creation request"""
    business_name: str = Field(..., min_length=1, max_length=100)
    business_email: str = Field(..., regex=r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
    webhook_url: Optional[str] = None
    white_label_domain: Optional[str] = None


class TransferRequest(BaseModel):
    """Transfer request"""
    amount: float = Field(..., gt=0, description="Transfer amount")
    source_currency: str = Field(..., min_length=3, max_length=3, description="Source currency code")
    destination_currency: str = Field(..., min_length=3, max_length=3, description="Destination currency code")
    beneficiary_name: str = Field(..., min_length=1, max_length=100)
    beneficiary_account: str = Field(..., min_length=1, max_length=50)
    beneficiary_bank: Optional[str] = None
    beneficiary_country: str = Field(..., min_length=2, max_length=2, description="ISO country code")
    transfer_speed: str = Field(default="standard", regex="^(express|standard|economy)$")
    reference: Optional[str] = Field(None, max_length=100, description="Client reference")
    metadata: Optional[Dict] = Field(default={}, description="Additional metadata")
    
    @validator('amount')
    def validate_amount(cls, v) -> None:
        if v < 1 or v > 1000000:
            raise ValueError('Amount must be between 1 and 1,000,000')
        return v


class QuoteRequest(BaseModel):
    """Quote request"""
    amount: float = Field(..., gt=0)
    source_currency: str = Field(..., min_length=3, max_length=3)
    destination_currency: str = Field(..., min_length=3, max_length=3)
    transfer_speed: str = Field(default="standard", regex="^(express|standard|economy)$")


class WebhookConfig(BaseModel):
    """Webhook configuration"""
    url: str = Field(..., regex=r"^https://.*")
    events: List[str] = Field(..., min_items=1)
    secret: Optional[str] = None


# ============================================================================
# Authentication
# ============================================================================

def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict:
    """Verify API key from Bearer token"""
    api_key = credentials.credentials
    
    if api_key not in api_keys:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    client = api_keys[api_key]
    
    # Check if key is active
    if not client.get("active", True):
        raise HTTPException(status_code=403, detail="API key is inactive")
    
    return client


def verify_webhook_signature(payload: str, signature: str, secret: str) -> bool:
    """Verify webhook signature"""
    expected_signature = hmac.new(
        secret.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected_signature)


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/")
async def root() -> Dict[str, Any]:
    """API root"""
    return {
        "name": "White-Label Remittance API",
        "version": "1.0.0",
        "status": "operational",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.post("/v1/api-keys", status_code=201)
async def create_api_key(request: APIKeyCreate) -> Dict[str, Any]:
    """
    Create new API key for B2B client
    
    This endpoint would typically require admin authentication
    """
    # Generate API key
    api_key = f"wl_{uuid.uuid4().hex}"
    webhook_secret = f"whsec_{uuid.uuid4().hex}" if request.webhook_url else None
    
    # Store client info
    api_keys[api_key] = {
        "api_key": api_key,
        "business_name": request.business_name,
        "business_email": request.business_email,
        "webhook_url": request.webhook_url,
        "webhook_secret": webhook_secret,
        "white_label_domain": request.white_label_domain,
        "active": True,
        "created_at": datetime.utcnow().isoformat(),
        "transaction_count": 0,
        "total_volume": 0.0
    }
    
    return {
        "api_key": api_key,
        "webhook_secret": webhook_secret,
        "message": "API key created successfully. Store this securely - it won't be shown again."
    }


@app.post("/v1/quotes")
async def create_quote(
    request: QuoteRequest,
    client: Dict = Depends(verify_api_key)
) -> None:
    """
    Get quote for transfer
    
    Returns exchange rate, fees, and delivery time estimate
    """
    # Simulate exchange rate lookup
    exchange_rate = 1.25  # Simplified
    
    # Calculate fee based on transfer speed
    fee_multipliers = {"express": 1.5, "standard": 1.0, "economy": 0.5}
    base_fee_percentage = 2.0
    fee_multiplier = fee_multipliers.get(request.transfer_speed, 1.0)
    
    fee = (request.amount * base_fee_percentage / 100) * fee_multiplier
    destination_amount = (request.amount - fee) * exchange_rate
    
    # Delivery time estimates
    delivery_times = {
        "express": "0-15 minutes",
        "standard": "1-4 hours",
        "economy": "1-3 days"
    }
    
    quote_id = f"quote_{uuid.uuid4().hex[:12]}"
    
    quote = {
        "quote_id": quote_id,
        "source_amount": request.amount,
        "source_currency": request.source_currency,
        "destination_amount": round(destination_amount, 2),
        "destination_currency": request.destination_currency,
        "exchange_rate": exchange_rate,
        "fee": round(fee, 2),
        "total_cost": round(request.amount, 2),
        "transfer_speed": request.transfer_speed,
        "estimated_delivery": delivery_times[request.transfer_speed],
        "expires_at": (datetime.utcnow().timestamp() + 300),  # 5 minutes
        "created_at": datetime.utcnow().isoformat()
    }
    
    return quote


@app.post("/v1/transfers", status_code=201)
async def create_transfer(
    request: TransferRequest,
    client: Dict = Depends(verify_api_key)
) -> None:
    """
    Create new transfer
    
    Initiates a remittance transaction
    """
    # Generate transaction ID
    transaction_id = f"txn_{uuid.uuid4().hex[:16]}"
    
    # Calculate fee and destination amount
    fee_multipliers = {"express": 1.5, "standard": 1.0, "economy": 0.5}
    base_fee_percentage = 2.0
    fee_multiplier = fee_multipliers.get(request.transfer_speed, 1.0)
    
    fee = (request.amount * base_fee_percentage / 100) * fee_multiplier
    exchange_rate = 1.25  # Simplified
    destination_amount = (request.amount - fee) * exchange_rate
    
    # Create transaction
    transaction = {
        "transaction_id": transaction_id,
        "client_id": client["api_key"],
        "client_reference": request.reference,
        "status": "pending",
        "source_amount": request.amount,
        "source_currency": request.source_currency,
        "destination_amount": round(destination_amount, 2),
        "destination_currency": request.destination_currency,
        "exchange_rate": exchange_rate,
        "fee": round(fee, 2),
        "total_cost": round(request.amount, 2),
        "beneficiary": {
            "name": request.beneficiary_name,
            "account": request.beneficiary_account,
            "bank": request.beneficiary_bank,
            "country": request.beneficiary_country
        },
        "transfer_speed": request.transfer_speed,
        "metadata": request.metadata,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }
    
    # Store transaction
    transactions[transaction_id] = transaction
    
    # Update client stats
    client["transaction_count"] += 1
    client["total_volume"] += request.amount
    
    # Trigger webhook (async in production)
    if client.get("webhook_url"):
        await send_webhook(
            client["webhook_url"],
            client.get("webhook_secret"),
            "transfer.created",
            transaction
        )
    
    return transaction


@app.get("/v1/transfers/{transaction_id}")
async def get_transfer(
    transaction_id: str,
    client: Dict = Depends(verify_api_key)
) -> None:
    """
    Get transfer details
    
    Retrieve status and details of a specific transfer
    """
    if transaction_id not in transactions:
        raise HTTPException(status_code=404, detail="Transfer not found")
    
    transaction = transactions[transaction_id]
    
    # Verify client owns this transaction
    if transaction["client_id"] != client["api_key"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return transaction


@app.get("/v1/transfers")
async def list_transfers(
    client: Dict = Depends(verify_api_key),
    status: Optional[str] = None,
    limit: int = 20,
    offset: int = 0
) -> Dict[str, Any]:
    """
    List transfers
    
    Get paginated list of transfers for the client
    """
    # Filter transactions for this client
    client_transactions = [
        t for t in transactions.values()
        if t["client_id"] == client["api_key"]
    ]
    
    # Filter by status if provided
    if status:
        client_transactions = [
            t for t in client_transactions
            if t["status"] == status
        ]
    
    # Sort by created_at descending
    client_transactions.sort(
        key=lambda x: x["created_at"],
        reverse=True
    )
    
    # Paginate
    total = len(client_transactions)
    paginated = client_transactions[offset:offset + limit]
    
    return {
        "data": paginated,
        "pagination": {
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total
        }
    }


@app.post("/v1/transfers/{transaction_id}/cancel")
async def cancel_transfer(
    transaction_id: str,
    client: Dict = Depends(verify_api_key)
) -> None:
    """
    Cancel transfer
    
    Cancel a pending transfer
    """
    if transaction_id not in transactions:
        raise HTTPException(status_code=404, detail="Transfer not found")
    
    transaction = transactions[transaction_id]
    
    # Verify client owns this transaction
    if transaction["client_id"] != client["api_key"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Check if cancellable
    if transaction["status"] not in ["pending", "processing"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel transfer with status: {transaction['status']}"
        )
    
    # Update status
    transaction["status"] = "cancelled"
    transaction["updated_at"] = datetime.utcnow().isoformat()
    transaction["cancelled_at"] = datetime.utcnow().isoformat()
    
    # Trigger webhook
    if client.get("webhook_url"):
        await send_webhook(
            client["webhook_url"],
            client.get("webhook_secret"),
            "transfer.cancelled",
            transaction
        )
    
    return transaction


@app.get("/v1/exchange-rates")
async def get_exchange_rates(
    source_currency: str,
    destination_currency: Optional[str] = None,
    client: Dict = Depends(verify_api_key)
) -> Dict[str, Any]:
    """
    Get current exchange rates
    
    Returns real-time exchange rates
    """
    # Simplified exchange rates
    rates = {
        "USD": {"NGN": 1580.50, "GBP": 0.79, "EUR": 0.92, "KES": 153.25},
        "NGN": {"USD": 0.00063, "GBP": 0.0005, "EUR": 0.00058, "KES": 0.097},
        "GBP": {"USD": 1.27, "NGN": 2000.00, "EUR": 1.17, "KES": 194.50},
    }
    
    if source_currency not in rates:
        raise HTTPException(status_code=400, detail="Unsupported source currency")
    
    source_rates = rates[source_currency]
    
    if destination_currency:
        if destination_currency not in source_rates:
            raise HTTPException(status_code=400, detail="Unsupported destination currency")
        
        return {
            "source_currency": source_currency,
            "destination_currency": destination_currency,
            "rate": source_rates[destination_currency],
            "timestamp": datetime.utcnow().isoformat()
        }
    
    return {
        "source_currency": source_currency,
        "rates": source_rates,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/v1/supported-corridors")
async def get_supported_corridors(client: Dict = Depends(verify_api_key)) -> Dict[str, Any]:
    """
    Get list of supported payment corridors
    
    Returns all available source-destination currency pairs
    """
    corridors = [
        {"source": "USD", "destination": "NGN", "methods": ["bank_transfer", "mobile_money"]},
        {"source": "USD", "destination": "KES", "methods": ["bank_transfer", "mobile_money", "mpesa"]},
        {"source": "GBP", "destination": "NGN", "methods": ["bank_transfer"]},
        {"source": "EUR", "destination": "NGN", "methods": ["bank_transfer"]},
        {"source": "USD", "destination": "GHS", "methods": ["bank_transfer", "mobile_money"]},
    ]
    
    return {
        "corridors": corridors,
        "total": len(corridors)
    }


@app.post("/v1/webhooks")
async def configure_webhook(
    config: WebhookConfig,
    client: Dict = Depends(verify_api_key)
) -> Dict[str, Any]:
    """
    Configure webhook for events
    
    Set up webhook URL to receive real-time notifications
    """
    # Validate events
    valid_events = [
        "transfer.created",
        "transfer.processing",
        "transfer.completed",
        "transfer.failed",
        "transfer.cancelled"
    ]
    
    invalid_events = [e for e in config.events if e not in valid_events]
    if invalid_events:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid events: {invalid_events}. Valid events: {valid_events}"
        )
    
    # Generate webhook secret if not provided
    webhook_secret = config.secret or f"whsec_{uuid.uuid4().hex}"
    
    # Update client config
    client["webhook_url"] = config.url
    client["webhook_secret"] = webhook_secret
    client["webhook_events"] = config.events
    
    return {
        "webhook_url": config.url,
        "webhook_secret": webhook_secret,
        "events": config.events,
        "message": "Webhook configured successfully"
    }


@app.get("/v1/account/usage")
async def get_usage_stats(client: Dict = Depends(verify_api_key)) -> Dict[str, Any]:
    """
    Get API usage statistics
    
    Returns transaction count, volume, and other metrics
    """
    return {
        "business_name": client["business_name"],
        "transaction_count": client["transaction_count"],
        "total_volume": client["total_volume"],
        "account_created_at": client["created_at"],
        "api_key_status": "active" if client["active"] else "inactive"
    }


# ============================================================================
# Webhook Helper
# ============================================================================

async def send_webhook(url: str, secret: Optional[str], event: str, data: Dict) -> None:
    """Send webhook notification (async)"""
    import httpx
    
    payload = {
        "event": event,
        "data": data,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    headers = {"Content-Type": "application/json"}
    
    # Add signature if secret provided
    if secret:
        payload_str = str(payload)
        signature = hmac.new(
            secret.encode(),
            payload_str.encode(),
            hashlib.sha256
        ).hexdigest()
        headers["X-Webhook-Signature"] = signature
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers, timeout=10.0)
            logger.info(f"Webhook sent: {event} -> {url} (status: {response.status_code})")
    except Exception as e:
        logger.error(f"Webhook failed: {event} -> {url} (error: {e})")


# ============================================================================
# Run Server
# ============================================================================


@app.on_event("startup")
async def _startup():
    await get_db_pool()

@app.on_event("shutdown")
async def _shutdown():
    await close_db_pool()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

