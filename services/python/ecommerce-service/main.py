"""
E-commerce Service - Production-Ready Main Application
Comprehensive e-commerce and inventory management with:
- Circuit breakers for resilient external calls
- Inventory reservation with automatic expiry
- Idempotency keys for order creation
- Kafka event streaming
- Temporal workflows for distributed transactions
- Real carrier API integration
- Batch inventory operations
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional

import asyncpg
import redis.asyncio as redis
from fastapi import FastAPI, HTTPException, Depends, Header, BackgroundTasks
import sys as _sys2, os as _os2
_sys2.path.insert(0, _os2.path.join(_os2.path.dirname(_os2.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from service_config import get_config, ServiceConfig
from circuit_breaker import circuit_breaker_registry, ResilientHttpClient
from inventory_reservation import InventoryReservationManager, InsufficientInventoryError
from idempotency import IdempotencyService, IdempotencyConflictError, IdempotencyInProgressError
from kafka_consumer import (

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

    InventoryEventConsumer, InventoryEventProducer,
    InventoryEventType, create_default_consumer
)
from batch_inventory import BatchInventoryService, BatchItem, BatchResult
from temporal_workflows import temporal_service, OrderRequest, OrderResult
from carrier_api import (
    CarrierAggregator, create_carrier_aggregator,
    Address, Package, ShipmentRate, ShipmentLabel, TrackingEvent
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global instances
config: ServiceConfig = None
db_pool: asyncpg.Pool = None
redis_client: redis.Redis = None
reservation_manager: InventoryReservationManager = None
idempotency_service: IdempotencyService = None
event_consumer: InventoryEventConsumer = None
event_producer: InventoryEventProducer = None
batch_service: BatchInventoryService = None
carrier_aggregator: CarrierAggregator = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global config, db_pool, redis_client, reservation_manager
    global idempotency_service, event_consumer, event_producer
    global batch_service, carrier_aggregator
    
    logger.info("Starting e-commerce service...")
    
    config = get_config()
    
    # Initialize database pool
    db_pool = await asyncpg.create_pool(
        config.database.async_url,
        min_size=5,
        max_size=20
    )
    logger.info("Database pool initialized")
    
    # Initialize Redis
    redis_client = redis.from_url(config.redis.url)
    logger.info("Redis client initialized")
    
    # Initialize inventory reservation manager
    reservation_manager = InventoryReservationManager(db_pool, redis_client)
    await reservation_manager.initialize()
    logger.info("Inventory reservation manager initialized")
    
    # Initialize idempotency service
    idempotency_service = IdempotencyService(redis_client, db_pool)
    await idempotency_service.initialize()
    logger.info("Idempotency service initialized")
    
    # Initialize Kafka producer
    event_producer = InventoryEventProducer()
    await event_producer.start()
    logger.info("Kafka producer initialized")
    
    # Initialize Kafka consumer
    event_consumer = create_default_consumer()
    await event_consumer.start()
    logger.info("Kafka consumer initialized")
    
    # Initialize batch service
    batch_service = BatchInventoryService(db_pool, event_producer)
    logger.info("Batch inventory service initialized")
    
    # Initialize carrier aggregator
    carrier_aggregator = create_carrier_aggregator()
    logger.info("Carrier aggregator initialized")
    
    # Connect to Temporal (non-blocking)
    try:
        await temporal_service.connect()
        logger.info("Temporal service connected")
    except Exception as e:
        logger.warning(f"Temporal connection failed (will retry on demand): {e}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down e-commerce service...")
    
    await reservation_manager.shutdown()
    await event_consumer.stop()
    await event_producer.stop()
    await temporal_service.close()
    await redis_client.close()
    await db_pool.close()
    
    logger.info("E-commerce service shutdown complete")

app = FastAPI(

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/ecommerce_service")
apply_middleware(app, enable_auth=True)

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
    title="E-commerce Service",
    description="Production-ready e-commerce and inventory management",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic Models
class HealthResponse(BaseModel):
    status: str
    service: str
    timestamp: datetime
    components: Dict[str, str]

class OrderItemRequest(BaseModel):
    product_id: str
    variant_id: Optional[str] = None
    sku: str
    quantity: int = Field(gt=0)
    unit_price: float = Field(gt=0)
    warehouse_id: str

class CreateOrderRequest(BaseModel):
    customer_id: str
    items: List[OrderItemRequest]
    shipping_address: Dict[str, str]
    payment_method: str
    payment_details: Dict[str, Any]
    total_amount: float = Field(gt=0)
    currency: str = "NGN"

class ReservationRequest(BaseModel):
    order_id: str
    items: List[Dict[str, Any]]
    timeout_minutes: Optional[int] = None

class BatchUpdateRequest(BaseModel):
    items: List[Dict[str, Any]]
    reason: str = "bulk_update"

class BatchTransferRequest(BaseModel):
    source_warehouse_id: str
    destination_warehouse_id: str
    items: List[Dict[str, Any]]
    reason: str = "warehouse_transfer"

class ShippingRateRequest(BaseModel):
    origin: Dict[str, Any]
    destination: Dict[str, Any]
    packages: List[Dict[str, Any]]

class CreateShipmentRequest(BaseModel):
    carrier: str
    origin: Dict[str, Any]
    destination: Dict[str, Any]
    packages: List[Dict[str, Any]]
    service_type: str

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Comprehensive health check"""
    components = {}
    
    try:
        async with db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        components["database"] = "healthy"
    except Exception as e:
        components["database"] = f"unhealthy: {e}"
    
    try:
        await redis_client.ping()
        components["redis"] = "healthy"
    except Exception as e:
        components["redis"] = f"unhealthy: {e}"
    
    components["kafka_producer"] = "healthy" if event_producer else "not_initialized"
    components["kafka_consumer"] = "healthy" if event_consumer else "not_initialized"
    
    overall_status = "healthy" if all(v == "healthy" for v in components.values()) else "degraded"
    
    return HealthResponse(
        status=overall_status,
        service="ecommerce-service",
        timestamp=datetime.utcnow(),
        components=components
    )

@app.get("/")
async def root():
    return {
        "message": "E-commerce Service API",
        "version": "2.0.0",
        "features": [
            "inventory_reservation",
            "idempotency",
            "circuit_breakers",
            "kafka_events",
            "temporal_workflows",
            "carrier_integration",
            "batch_operations"
        ]
    }

@app.get("/circuit-breakers")
async def get_circuit_breaker_stats():
    """Get circuit breaker statistics"""
    return {"breakers": circuit_breaker_registry.get_all_stats()}

@app.post("/orders")
async def create_order(
    request: CreateOrderRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key")
):
    """Create order with distributed transaction workflow"""
    import uuid
    
    order_id = str(uuid.uuid4())
    request_data = request.dict()
    existing = await idempotency_service.check(idempotency_key, request_data)
    
    if existing:
        if existing.status.value == "completed":
            return existing.response
        if existing.status.value == "processing":
            raise HTTPException(status_code=409, detail="Order creation already in progress")
        if existing.status.value == "failed":
            raise HTTPException(status_code=400, detail=f"Previous order creation failed: {existing.error}")
    
    acquired = await idempotency_service.start(idempotency_key, request_data)
    if not acquired:
        raise HTTPException(status_code=409, detail="Order creation already in progress")
    
    try:
        order_request = OrderRequest(
            order_id=order_id,
            customer_id=request.customer_id,
            idempotency_key=idempotency_key,
            items=[item.dict() for item in request.items],
            shipping_address=request.shipping_address,
            payment_method=request.payment_method,
            payment_details=request.payment_details,
            total_amount=request.total_amount,
            currency=request.currency
        )
        
        result = await temporal_service.create_order(order_request)
        
        response = {
            "order_id": result.order_id,
            "status": result.status,
            "payment_id": result.payment_id,
            "reservation_ids": result.reservation_ids,
            "error": result.error
        }
        
        await idempotency_service.complete(idempotency_key, response)
        return response
        
    except Exception as e:
        await idempotency_service.fail(idempotency_key, str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/orders/{order_id}/cancel")
async def cancel_order(order_id: str, reason: str = "customer_request"):
    """Cancel order with compensation workflow"""
    async with db_pool.acquire() as conn:
        order = await conn.fetchrow("SELECT payment_id FROM orders WHERE id = $1", order_id)
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    return await temporal_service.cancel_order(order_id=order_id, payment_id=order["payment_id"], reason=reason)

@app.post("/inventory/reserve")
async def reserve_inventory(request: ReservationRequest):
    """Reserve inventory for an order"""
    try:
        reservations = await reservation_manager.reserve(
            order_id=request.order_id,
            items=request.items,
            timeout_minutes=request.timeout_minutes
        )
        return {
            "reservations": [{"id": r.id, "product_id": r.product_id, "quantity": r.quantity, "status": r.status.value} for r in reservations],
            "expires_at": reservations[0].expires_at.isoformat() if reservations else None
        }
    except InsufficientInventoryError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/inventory/reserve/{order_id}/fulfill")
async def fulfill_reservation(order_id: str):
    """Fulfill inventory reservation"""
    return {"fulfilled_count": await reservation_manager.fulfill(order_id)}

@app.post("/inventory/reserve/{order_id}/release")
async def release_reservation(order_id: str, reason: str = "cancelled"):
    """Release inventory reservation"""
    return {"released_count": await reservation_manager.release(order_id, reason)}

@app.get("/inventory/reserve/{order_id}")
async def get_reservations(order_id: str):
    """Get reservations for an order"""
    reservations = await reservation_manager.get_reservations(order_id)
    return {"reservations": [{"id": r.id, "product_id": r.product_id, "sku": r.sku, "quantity": r.quantity, "status": r.status.value, "expires_at": r.expires_at.isoformat()} for r in reservations]}

@app.post("/inventory/batch/update")
async def batch_update_stock(request: BatchUpdateRequest):
    """Bulk update stock quantities"""
    items = [BatchItem(warehouse_id=item["warehouse_id"], product_id=item["product_id"], sku=item.get("sku", ""), quantity=item["quantity"], operation=item.get("operation", "set")) for item in request.items]
    result = await batch_service.bulk_update_stock(items, request.reason)
    return {"batch_id": result.batch_id, "total_items": result.total_items, "successful_items": result.successful_items, "failed_items": result.failed_items, "errors": result.errors, "duration_ms": result.duration_ms}

@app.post("/inventory/batch/transfer")
async def batch_warehouse_transfer(request: BatchTransferRequest):
    """Transfer inventory between warehouses"""
    items = [(item["product_id"], item.get("sku", ""), item["quantity"]) for item in request.items]
    result = await batch_service.warehouse_transfer(source_warehouse_id=request.source_warehouse_id, destination_warehouse_id=request.destination_warehouse_id, items=items, reason=request.reason)
    return {"batch_id": result.batch_id, "total_items": result.total_items, "successful_items": result.successful_items, "failed_items": result.failed_items, "errors": result.errors, "duration_ms": result.duration_ms}

@app.post("/shipping/rates")
async def get_shipping_rates(request: ShippingRateRequest):
    """Get shipping rates from all carriers"""
    origin = Address(name=request.origin.get("name", ""), company=request.origin.get("company"), street1=request.origin.get("street1", ""), street2=request.origin.get("street2"), city=request.origin.get("city", ""), state=request.origin.get("state", ""), postal_code=request.origin.get("postal_code", ""), country=request.origin.get("country", "NG"), phone=request.origin.get("phone", ""), email=request.origin.get("email"))
    destination = Address(name=request.destination.get("name", ""), company=request.destination.get("company"), street1=request.destination.get("street1", ""), street2=request.destination.get("street2"), city=request.destination.get("city", ""), state=request.destination.get("state", ""), postal_code=request.destination.get("postal_code", ""), country=request.destination.get("country", "NG"), phone=request.destination.get("phone", ""), email=request.destination.get("email"))
    packages = [Package(weight=pkg.get("weight", 1.0), length=pkg.get("length", 10.0), width=pkg.get("width", 10.0), height=pkg.get("height", 10.0)) for pkg in request.packages]
    rates = await carrier_aggregator.get_all_rates(origin, destination, packages)
    return {"rates": [{"carrier": r.carrier, "service_type": r.service_type, "service_name": r.service_name, "rate": r.rate, "currency": r.currency, "estimated_days": r.estimated_days, "guaranteed": r.guaranteed} for r in rates]}

@app.post("/shipping/shipments")
async def create_shipment(request: CreateShipmentRequest):
    """Create shipment with carrier"""
    origin = Address(name=request.origin.get("name", ""), company=request.origin.get("company"), street1=request.origin.get("street1", ""), street2=request.origin.get("street2"), city=request.origin.get("city", ""), state=request.origin.get("state", ""), postal_code=request.origin.get("postal_code", ""), country=request.origin.get("country", "NG"), phone=request.origin.get("phone", ""), email=request.origin.get("email"))
    destination = Address(name=request.destination.get("name", ""), company=request.destination.get("company"), street1=request.destination.get("street1", ""), street2=request.destination.get("street2"), city=request.destination.get("city", ""), state=request.destination.get("state", ""), postal_code=request.destination.get("postal_code", ""), country=request.destination.get("country", "NG"), phone=request.destination.get("phone", ""), email=request.destination.get("email"))
    packages = [Package(weight=pkg.get("weight", 1.0), length=pkg.get("length", 10.0), width=pkg.get("width", 10.0), height=pkg.get("height", 10.0)) for pkg in request.packages]
    try:
        label = await carrier_aggregator.create_shipment(carrier_name=request.carrier, origin=origin, destination=destination, packages=packages, service_type=request.service_type)
        return {"tracking_number": label.tracking_number, "carrier": label.carrier, "label_url": label.label_url, "label_format": label.label_format, "rate": label.rate, "currency": label.currency}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/shipping/track/{carrier}/{tracking_number}")
async def track_shipment(carrier: str, tracking_number: str):
    """Track shipment"""
    try:
        events = await carrier_aggregator.track_shipment(carrier, tracking_number)
        return {"tracking_number": tracking_number, "carrier": carrier, "events": [{"timestamp": e.timestamp.isoformat(), "status": e.status.value, "location": e.location, "description": e.description} for e in events]}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/events/inventory")
async def publish_inventory_event(warehouse_id: str, product_id: str, sku: str, quantity_change: int, quantity_available: int, quantity_reserved: int = 0):
    """Manually publish inventory event"""
    await event_producer.publish_stock_update(warehouse_id=warehouse_id, product_id=product_id, sku=sku, quantity_change=quantity_change, quantity_available=quantity_available, quantity_reserved=quantity_reserved)
    return {"status": "published"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    uvicorn.run("main:app", host=host, port=port, reload=os.getenv("ENV", "production") == "development")
