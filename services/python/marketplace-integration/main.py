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
Marketplace Integration Service
Universal integration service for various online marketplaces
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app, enable_auth=True)
setup_logging("marketplace-integration-service")
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
            "service.name": os.environ.get("OTEL_SERVICE_NAME", "marketplace-integration"),
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

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/marketplace_integration")

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
    title="Marketplace Integration Service",
    description="Universal integration service for online marketplaces",
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
    DATABASE_URL = os.getenv("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/marketplace_integration")
    WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "secret")

config = Config()

# Enums
class MarketplaceType(str, Enum):
    JUMIA = "jumia"
    KONGA = "konga"
    ALIBABA = "alibaba"
    ETSY = "etsy"
    SHOPIFY = "shopify"
    WOOCOMMERCE = "woocommerce"
    CUSTOM = "custom"

class IntegrationStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    ERROR = "error"

class SyncStatus(str, Enum):
    SYNCED = "synced"
    PENDING = "pending"
    FAILED = "failed"

# Models
class MarketplaceConnection(BaseModel):
    id: Optional[str] = None
    agent_id: str
    marketplace_type: MarketplaceType
    marketplace_name: str
    api_key: str
    api_secret: Optional[str] = None
    store_url: Optional[str] = None
    status: IntegrationStatus = IntegrationStatus.PENDING
    connected_at: Optional[datetime] = None
    last_sync: Optional[datetime] = None

class MarketplaceProduct(BaseModel):
    id: Optional[str] = None
    connection_id: str
    external_id: str
    title: str
    description: str
    price: float
    currency: str = "USD"
    quantity: int
    sku: str
    category: str
    images: List[str] = []
    sync_status: SyncStatus = SyncStatus.PENDING
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class MarketplaceOrder(BaseModel):
    id: Optional[str] = None
    connection_id: str
    external_order_id: str
    customer_name: str
    customer_email: str
    items: List[Dict[str, Any]]
    total_amount: float
    currency: str = "USD"
    status: str
    order_date: datetime
    shipping_address: Dict[str, Any]

class SyncRequest(BaseModel):
    connection_id: str
    sync_type: str = "full"  # full, incremental
    entity_types: List[str] = ["products", "orders", "inventory"]

class WebhookConfig(BaseModel):
    connection_id: str
    webhook_url: str
    events: List[str]
    is_active: bool = True

# In-memory storage
connections_db: Dict[str, MarketplaceConnection] = {}
products_db: Dict[str, MarketplaceProduct] = {}
orders_db: Dict[str, MarketplaceOrder] = {}
webhooks_db: Dict[str, WebhookConfig] = {}

# API Endpoints

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "marketplace-integration",
        "timestamp": datetime.utcnow().isoformat(),
        "active_connections": len([c for c in connections_db.values() if c.status == IntegrationStatus.ACTIVE])
    }

@app.post("/connections", response_model=MarketplaceConnection)
async def create_connection(connection: MarketplaceConnection):
    """Create a new marketplace connection"""
    try:
        connection.id = str(uuid.uuid4())
        connection.connected_at = datetime.utcnow()
        connection.status = IntegrationStatus.ACTIVE
        
        connections_db[connection.id] = connection
        
        logger.info(f"Created connection to {connection.marketplace_type} for agent {connection.agent_id}")
        return connection
    except Exception as e:
        logger.error(f"Error creating connection: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/connections", response_model=List[MarketplaceConnection])
async def list_connections(
    agent_id: Optional[str] = None,
    marketplace_type: Optional[MarketplaceType] = None,
    status: Optional[IntegrationStatus] = None
):
    """List marketplace connections"""
    try:
        connections = list(connections_db.values())
        
        if agent_id:
            connections = [c for c in connections if c.agent_id == agent_id]
        if marketplace_type:
            connections = [c for c in connections if c.marketplace_type == marketplace_type]
        if status:
            connections = [c for c in connections if c.status == status]
        
        return connections
    except Exception as e:
        logger.error(f"Error listing connections: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/connections/{connection_id}", response_model=MarketplaceConnection)
async def get_connection(connection_id: str):
    """Get a specific connection"""
    if connection_id not in connections_db:
        raise HTTPException(status_code=404, detail="Connection not found")
    return connections_db[connection_id]

@app.put("/connections/{connection_id}", response_model=MarketplaceConnection)
async def update_connection(connection_id: str, connection: MarketplaceConnection):
    """Update a marketplace connection"""
    if connection_id not in connections_db:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    connection.id = connection_id
    connections_db[connection_id] = connection
    
    logger.info(f"Updated connection {connection_id}")
    return connection

@app.delete("/connections/{connection_id}")
async def delete_connection(connection_id: str):
    """Delete a marketplace connection"""
    if connection_id not in connections_db:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    del connections_db[connection_id]
    logger.info(f"Deleted connection {connection_id}")
    return {"message": "Connection deleted successfully"}

@app.post("/products", response_model=MarketplaceProduct)
async def create_product(product: MarketplaceProduct):
    """Create a marketplace product"""
    try:
        product.id = str(uuid.uuid4())
        product.created_at = datetime.utcnow()
        product.updated_at = datetime.utcnow()
        
        products_db[product.id] = product
        
        logger.info(f"Created product {product.title} for connection {product.connection_id}")
        return product
    except Exception as e:
        logger.error(f"Error creating product: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/products", response_model=List[MarketplaceProduct])
async def list_products(
    connection_id: Optional[str] = None,
    sync_status: Optional[SyncStatus] = None
):
    """List marketplace products"""
    try:
        products = list(products_db.values())
        
        if connection_id:
            products = [p for p in products if p.connection_id == connection_id]
        if sync_status:
            products = [p for p in products if p.sync_status == sync_status]
        
        return products
    except Exception as e:
        logger.error(f"Error listing products: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/products/{product_id}", response_model=MarketplaceProduct)
async def get_product(product_id: str):
    """Get a specific product"""
    if product_id not in products_db:
        raise HTTPException(status_code=404, detail="Product not found")
    return products_db[product_id]

@app.put("/products/{product_id}", response_model=MarketplaceProduct)
async def update_product(product_id: str, product: MarketplaceProduct):
    """Update a marketplace product"""
    if product_id not in products_db:
        raise HTTPException(status_code=404, detail="Product not found")
    
    product.id = product_id
    product.updated_at = datetime.utcnow()
    products_db[product_id] = product
    
    logger.info(f"Updated product {product_id}")
    return product

@app.post("/sync")
async def sync_marketplace(sync_request: SyncRequest):
    """Sync data with marketplace"""
    try:
        if sync_request.connection_id not in connections_db:
            raise HTTPException(status_code=404, detail="Connection not found")
        
        connection = connections_db[sync_request.connection_id]
        
        synced_entities = {}
        
        # Sync each entity type via marketplace API
        for entity_type in sync_request.entity_types:
            if entity_type == "products":
                # Sync products
                synced_entities["products"] = len([p for p in products_db.values() 
                                                  if p.connection_id == sync_request.connection_id])
            elif entity_type == "orders":
                # Sync orders
                synced_entities["orders"] = len([o for o in orders_db.values() 
                                                if o.connection_id == sync_request.connection_id])
            elif entity_type == "inventory":
                # Sync inventory
                synced_entities["inventory"] = 0
        
        connection.last_sync = datetime.utcnow()
        
        logger.info(f"Synced marketplace {connection.marketplace_type} for connection {sync_request.connection_id}")
        
        return {
            "message": "Sync completed successfully",
            "sync_type": sync_request.sync_type,
            "synced_entities": synced_entities,
            "timestamp": datetime.utcnow().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error syncing marketplace: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/orders", response_model=List[MarketplaceOrder])
async def list_orders(connection_id: Optional[str] = None):
    """List marketplace orders"""
    try:
        orders = list(orders_db.values())
        
        if connection_id:
            orders = [o for o in orders if o.connection_id == connection_id]
        
        return orders
    except Exception as e:
        logger.error(f"Error listing orders: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/webhooks", response_model=WebhookConfig)
async def configure_webhook(webhook: WebhookConfig):
    """Configure webhook for marketplace events"""
    try:
        if webhook.connection_id not in connections_db:
            raise HTTPException(status_code=404, detail="Connection not found")
        
        webhook_id = f"webhook_{webhook.connection_id}"
        webhooks_db[webhook_id] = webhook
        
        logger.info(f"Configured webhook for connection {webhook.connection_id}")
        return webhook
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error configuring webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/webhooks/receive")
async def receive_webhook(data: Dict[str, Any]):
    """Receive webhook from marketplace"""
    try:
        logger.info(f"Received webhook: {data.get('event_type')}")
        
        event_type = data.get("event_type")
        
        if event_type == "order.created":
            # Handle new order
            pass
        elif event_type == "product.updated":
            # Handle product update
            pass
        elif event_type == "inventory.changed":
            # Handle inventory change
            pass
        
        return {"message": "Webhook processed successfully"}
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/analytics/{agent_id}")
async def get_marketplace_analytics(agent_id: str):
    """Get marketplace analytics for an agent"""
    try:
        agent_connections = [c for c in connections_db.values() if c.agent_id == agent_id]
        connection_ids = [c.id for c in agent_connections]
        
        agent_products = [p for p in products_db.values() if p.connection_id in connection_ids]
        agent_orders = [o for o in orders_db.values() if o.connection_id in connection_ids]
        
        return {
            "total_connections": len(agent_connections),
            "active_connections": len([c for c in agent_connections if c.status == IntegrationStatus.ACTIVE]),
            "total_products": len(agent_products),
            "synced_products": len([p for p in agent_products if p.sync_status == SyncStatus.SYNCED]),
            "total_orders": len(agent_orders),
            "total_revenue": sum(o.total_amount for o in agent_orders),
            "marketplaces": list(set(c.marketplace_type for c in agent_connections))
        }
    except Exception as e:
        logger.error(f"Error getting analytics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8082)



@app.on_event("startup")
async def startup_event():
    """Register service with Kafka on startup."""
    await publish_kafka("marketplace.integration.started", {
        "service": "marketplace-integration",
        "timestamp": datetime.utcnow().isoformat() if "datetime" in dir() else "startup",
    })
