import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
"""
Production-Ready Inventory Management Platform
Complete API with async SQLAlchemy, middleware integration
Integrates with: Kafka, Dapr, Fluvio, Temporal, Redis, TigerBeetle, Lakehouse
"""

import os
import uuid
import logging
import json
import hashlib
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, AsyncGenerator
from decimal import Decimal
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import Enum

import asyncpg
import redis.asyncio as redis
from fastapi import FastAPI, HTTPException, Depends, Query, Path, Body, Header, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app)
setup_logging("inventory-management-platform-(production)")
app.include_router(metrics_router)

from pydantic import BaseModel, Field
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OrderStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class CreditStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DEFAULTED = "defaulted"


class ShipmentStatus(str, Enum):
    PREPARING = "preparing"
    IN_TRANSIT = "in_transit"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    FAILED = "failed"


class PaymentTerms(str, Enum):
    IMMEDIATE = "immediate"
    NET_7 = "net_7"
    NET_15 = "net_15"
    NET_30 = "net_30"
    NET_60 = "net_60"
    NET_90 = "net_90"


class InventoryStatus(str, Enum):
    AVAILABLE = "available"
    RESERVED = "reserved"
    IN_TRANSIT = "in_transit"
    DAMAGED = "damaged"
    EXPIRED = "expired"
    QUARANTINE = "quarantine"


class StockMovementType(str, Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    TRANSFER = "transfer"
    ADJUSTMENT = "adjustment"
    RETURN = "return"
    DAMAGE = "damage"
    EXPIRY = "expiry"


@dataclass
class ServiceConfig:
    database_url: str = field(default_factory=lambda: os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/remittance"
    ))
    redis_url: str = field(default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379"))
    kafka_bootstrap_servers: str = field(default_factory=lambda: os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"))
    fluvio_endpoint: str = field(default_factory=lambda: os.getenv("FLUVIO_ENDPOINT", "localhost:9003"))
    temporal_host: str = field(default_factory=lambda: os.getenv("TEMPORAL_HOST", "localhost:7233"))
    dapr_http_port: int = field(default_factory=lambda: int(os.getenv("DAPR_HTTP_PORT", "3500")))
    tigerbeetle_addresses: str = field(default_factory=lambda: os.getenv("TIGERBEETLE_ADDRESSES", "localhost:3000"))
    lakehouse_url: str = field(default_factory=lambda: os.getenv("LAKEHOUSE_URL", "http://localhost:8181"))


class DatabasePool:
    """Production-ready async database connection pool"""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self._pool: Optional[asyncpg.Pool] = None
    
    async def initialize(self):
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                self.database_url,
                min_size=5,
                max_size=20,
                max_inactive_connection_lifetime=300,
                command_timeout=60
            )
            logger.info("Database pool initialized")
    
    async def close(self):
        if self._pool:
            await self._pool.close()
            self._pool = None
            logger.info("Database pool closed")
    
    @asynccontextmanager
    async def acquire(self) -> AsyncGenerator[asyncpg.Connection, None]:
        if self._pool is None:
            raise RuntimeError("Database pool not initialized")
        async with self._pool.acquire() as connection:
            yield connection
    
    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[asyncpg.Connection, None]:
        async with self.acquire() as connection:
            async with connection.transaction():
                yield connection


class RedisClient:
    """Production-ready Redis client"""
    
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self._client: Optional[redis.Redis] = None
    
    async def initialize(self):
        if self._client is None:
            self._client = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=20
            )
            await self._client.ping()
            logger.info("Redis client initialized")
    
    async def close(self):
        if self._client:
            await self._client.close()
            self._client = None
            logger.info("Redis client closed")
    
    @property
    def client(self) -> redis.Redis:
        if self._client is None:
            raise RuntimeError("Redis client not initialized")
        return self._client


class KafkaProducer:
    """Kafka producer for event streaming"""
    
    def __init__(self, bootstrap_servers: str):
        self.bootstrap_servers = bootstrap_servers
        self._producer = None
    
    async def initialize(self):
        try:
            from aiokafka import AIOKafkaProducer
            self._producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None,
                acks='all'
            )
            await self._producer.start()
            logger.info("Kafka producer initialized")
        except ImportError:
            logger.warning("aiokafka not installed, Kafka integration disabled")
        except Exception as e:
            logger.warning(f"Kafka connection failed: {e}")
    
    async def close(self):
        if self._producer:
            await self._producer.stop()
            self._producer = None
    
    async def send_event(self, topic: str, key: str, value: Dict[str, Any]):
        if self._producer:
            try:
                await self._producer.send_and_wait(topic, value=value, key=key)
            except Exception as e:
                logger.error(f"Failed to send Kafka event: {e}")


class DaprClient:
    """Dapr sidecar client"""
    
    def __init__(self, http_port: int):
        self.base_url = f"http://localhost:{http_port}"
        self._client: Optional[httpx.AsyncClient] = None
    
    async def initialize(self):
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=30.0)
        logger.info("Dapr client initialized")
    
    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def publish_event(self, pubsub_name: str, topic: str, data: Dict[str, Any]):
        if not self._client:
            return
        try:
            await self._client.post(f"/v1.0/publish/{pubsub_name}/{topic}", json=data)
        except Exception as e:
            logger.error(f"Failed to publish Dapr event: {e}")
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def invoke_service(self, app_id: str, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if not self._client:
            raise RuntimeError("Dapr client not initialized")
        response = await self._client.post(f"/v1.0/invoke/{app_id}/method/{method}", json=data)
        response.raise_for_status()
        return response.json()


class TigerBeetleClient:
    """TigerBeetle client for financial operations"""
    
    def __init__(self, addresses: str):
        self.addresses = addresses.split(",")
        self._client = None
    
    async def initialize(self):
        try:
            import tigerbeetle
            self._client = tigerbeetle.Client(cluster_id=0, addresses=self.addresses)
            logger.info("TigerBeetle client initialized")
        except ImportError:
            logger.warning("tigerbeetle not installed")
        except Exception as e:
            logger.warning(f"TigerBeetle connection failed: {e}")
    
    async def close(self):
        self._client = None
    
    async def create_transfer(self, transfer_id: int, debit_id: int, credit_id: int, amount: int, ledger: int, code: int) -> bool:
        if not self._client:
            return True
        try:
            import tigerbeetle
            transfer = tigerbeetle.Transfer(
                id=transfer_id,
                debit_account_id=debit_id,
                credit_account_id=credit_id,
                amount=amount,
                ledger=ledger,
                code=code,
                flags=0
            )
            errors = self._client.create_transfers([transfer])
            return len(errors) == 0
        except Exception as e:
            logger.error(f"Transfer failed: {e}")
            return False


class LakehouseClient:
    """Lakehouse client for analytics"""
    
    def __init__(self, url: str):
        self.url = url
        self._client: Optional[httpx.AsyncClient] = None
    
    async def initialize(self):
        self._client = httpx.AsyncClient(base_url=self.url, timeout=60.0)
        logger.info("Lakehouse client initialized")
    
    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def write_event(self, table: str, data: Dict[str, Any]) -> bool:
        if not self._client:
            return True
        try:
            response = await self._client.post(f"/v1/tables/{table}/records", json=data)
            return response.status_code in (200, 201)
        except Exception as e:
            logger.error(f"Lakehouse write failed: {e}")
            return False


class ManufacturerCreate(BaseModel):
    name: str
    business_registration: str
    contact_person: str
    email: str
    phone: str
    address: str
    product_categories: List[str]
    minimum_order_value: float
    payment_terms: PaymentTerms
    lead_time_days: int


class ManufacturerResponse(BaseModel):
    id: str
    name: str
    business_registration: str
    contact_person: str
    email: str
    phone: str
    address: str
    product_categories: List[str]
    minimum_order_value: float
    payment_terms: str
    lead_time_days: int
    rating: float
    verified: bool
    created_at: datetime


class ProductCreate(BaseModel):
    manufacturer_id: str
    sku: str
    name: str
    description: str
    category: str
    unit_price: float
    wholesale_price: float
    minimum_order_quantity: int
    available_quantity: int
    reorder_level: int
    unit_of_measure: str
    specifications: Optional[Dict[str, Any]] = {}
    images: List[str] = []


class ProductResponse(BaseModel):
    id: str
    manufacturer_id: str
    sku: str
    name: str
    description: str
    category: str
    unit_price: float
    wholesale_price: float
    minimum_order_quantity: int
    available_quantity: int
    reorder_level: int
    unit_of_measure: str
    specifications: Dict[str, Any]
    images: List[str]
    created_at: datetime
    updated_at: datetime


class PurchaseOrderCreate(BaseModel):
    agent_id: str
    manufacturer_id: str
    items: List[Dict[str, Any]]
    payment_method: str
    payment_terms: PaymentTerms
    notes: Optional[str] = None


class PurchaseOrderResponse(BaseModel):
    id: str
    order_number: str
    agent_id: str
    manufacturer_id: str
    items: List[Dict[str, Any]]
    subtotal: float
    tax: float
    shipping_cost: float
    total_amount: float
    payment_method: str
    payment_terms: str
    due_date: Optional[datetime]
    status: str
    notes: Optional[str]
    created_at: datetime


class CreditApplicationCreate(BaseModel):
    agent_id: str
    requested_amount: float
    purpose: str
    business_revenue: float
    years_in_business: int
    existing_loans: float
    collateral: Optional[str] = None
    guarantor_info: Optional[Dict[str, Any]] = None


class CreditFacilityResponse(BaseModel):
    id: str
    agent_id: str
    credit_limit: float
    available_credit: float
    utilized_credit: float
    interest_rate: float
    payment_terms: str
    status: str
    approval_date: Optional[datetime]
    credit_score: Optional[int]
    created_at: datetime


class ShipmentCreate(BaseModel):
    purchase_order_id: str
    carrier: str
    origin_address: str
    destination_address: str
    estimated_delivery: datetime


class ShipmentResponse(BaseModel):
    id: str
    tracking_number: str
    purchase_order_id: str
    agent_id: str
    manufacturer_id: str
    carrier: str
    origin_address: str
    destination_address: str
    estimated_delivery: datetime
    actual_delivery: Optional[datetime]
    status: str
    current_location: Optional[str]
    tracking_history: List[Dict[str, Any]]
    created_at: datetime


class InventoryCreate(BaseModel):
    warehouse_id: str
    product_id: str
    quantity_available: int = 0
    reorder_point: int = 10
    reorder_quantity: int = 50
    min_stock_level: int = 5
    max_stock_level: Optional[int] = None


class InventoryResponse(BaseModel):
    id: str
    warehouse_id: str
    product_id: str
    quantity_available: int
    quantity_reserved: int
    quantity_in_transit: int
    quantity_damaged: int
    reorder_point: int
    reorder_quantity: int
    min_stock_level: int
    max_stock_level: Optional[int]
    status: str
    is_low_stock: bool
    created_at: datetime
    updated_at: datetime


class StockMovementCreate(BaseModel):
    warehouse_id: str
    product_id: str
    movement_type: StockMovementType
    quantity: int
    unit_cost: Optional[float] = None
    reference_type: Optional[str] = None
    reference_id: Optional[str] = None
    reason: Optional[str] = None
    notes: Optional[str] = None
    performed_by: Optional[str] = None


class ServiceContainer:
    """Container for all service dependencies"""
    
    def __init__(self, config: ServiceConfig):
        self.config = config
        self.db = DatabasePool(config.database_url)
        self.redis = RedisClient(config.redis_url)
        self.kafka = KafkaProducer(config.kafka_bootstrap_servers)
        self.dapr = DaprClient(config.dapr_http_port)
        self.tigerbeetle = TigerBeetleClient(config.tigerbeetle_addresses)
        self.lakehouse = LakehouseClient(config.lakehouse_url)
    
    async def initialize(self):
        await self.db.initialize()
        await self.redis.initialize()
        await self.kafka.initialize()
        await self.dapr.initialize()
        await self.tigerbeetle.initialize()
        await self.lakehouse.initialize()
        await self._ensure_tables()
        logger.info("All services initialized")
    
    async def close(self):
        await self.lakehouse.close()
        await self.tigerbeetle.close()
        await self.dapr.close()
        await self.kafka.close()
        await self.redis.close()
        await self.db.close()
        logger.info("All services closed")
    
    async def _ensure_tables(self):
        """Ensure all required tables exist"""
        async with self.db.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS manufacturers (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    name VARCHAR(255) NOT NULL,
                    business_registration VARCHAR(100) UNIQUE NOT NULL,
                    contact_person VARCHAR(255),
                    email VARCHAR(255),
                    phone VARCHAR(50),
                    address TEXT,
                    product_categories JSONB,
                    minimum_order_value DECIMAL(15,2),
                    payment_terms VARCHAR(50),
                    lead_time_days INTEGER,
                    rating DECIMAL(3,2) DEFAULT 4.0,
                    verified BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS inventory_products (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    manufacturer_id UUID REFERENCES manufacturers(id),
                    sku VARCHAR(100) UNIQUE NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    description TEXT,
                    category VARCHAR(100),
                    unit_price DECIMAL(15,2),
                    wholesale_price DECIMAL(15,2),
                    minimum_order_quantity INTEGER,
                    available_quantity INTEGER,
                    reorder_level INTEGER,
                    unit_of_measure VARCHAR(50),
                    specifications JSONB,
                    images JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS purchase_orders (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    order_number VARCHAR(50) UNIQUE NOT NULL,
                    agent_id VARCHAR(50) NOT NULL,
                    manufacturer_id UUID REFERENCES manufacturers(id),
                    items JSONB NOT NULL,
                    subtotal DECIMAL(15,2),
                    tax DECIMAL(15,2),
                    shipping_cost DECIMAL(15,2),
                    total_amount DECIMAL(15,2),
                    payment_method VARCHAR(50),
                    payment_terms VARCHAR(50),
                    due_date TIMESTAMP,
                    status VARCHAR(50) DEFAULT 'pending',
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS credit_facilities (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    agent_id VARCHAR(50) UNIQUE NOT NULL,
                    credit_limit DECIMAL(15,2),
                    available_credit DECIMAL(15,2),
                    utilized_credit DECIMAL(15,2) DEFAULT 0,
                    interest_rate DECIMAL(5,2),
                    payment_terms VARCHAR(50),
                    status VARCHAR(50) DEFAULT 'pending',
                    approval_date TIMESTAMP,
                    last_review_date TIMESTAMP,
                    credit_score INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS shipments (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    tracking_number VARCHAR(100) UNIQUE NOT NULL,
                    purchase_order_id UUID REFERENCES purchase_orders(id),
                    agent_id VARCHAR(50) NOT NULL,
                    manufacturer_id UUID,
                    carrier VARCHAR(255),
                    origin_address TEXT,
                    destination_address TEXT,
                    estimated_delivery TIMESTAMP,
                    actual_delivery TIMESTAMP,
                    status VARCHAR(50) DEFAULT 'preparing',
                    current_location VARCHAR(255),
                    tracking_history JSONB DEFAULT '[]',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS warehouses (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    name VARCHAR(255) NOT NULL,
                    code VARCHAR(50) UNIQUE NOT NULL,
                    address TEXT,
                    city VARCHAR(100),
                    country VARCHAR(100),
                    capacity INTEGER,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS inventory (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    warehouse_id UUID REFERENCES warehouses(id),
                    product_id UUID REFERENCES inventory_products(id),
                    quantity_available INTEGER DEFAULT 0,
                    quantity_reserved INTEGER DEFAULT 0,
                    quantity_in_transit INTEGER DEFAULT 0,
                    quantity_damaged INTEGER DEFAULT 0,
                    reorder_point INTEGER DEFAULT 10,
                    reorder_quantity INTEGER DEFAULT 50,
                    min_stock_level INTEGER DEFAULT 5,
                    max_stock_level INTEGER,
                    status VARCHAR(50) DEFAULT 'available',
                    last_count_date TIMESTAMP,
                    last_movement_date TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(warehouse_id, product_id)
                )
            """)
            
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS stock_movements (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    warehouse_id UUID REFERENCES warehouses(id),
                    product_id UUID REFERENCES inventory_products(id),
                    movement_type VARCHAR(50) NOT NULL,
                    quantity INTEGER NOT NULL,
                    unit_cost DECIMAL(15,2),
                    total_cost DECIMAL(15,2),
                    reference_type VARCHAR(50),
                    reference_id UUID,
                    from_warehouse_id UUID REFERENCES warehouses(id),
                    to_warehouse_id UUID REFERENCES warehouses(id),
                    reason TEXT,
                    notes TEXT,
                    performed_by VARCHAR(50),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS credit_transactions (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    credit_facility_id UUID REFERENCES credit_facilities(id),
                    transaction_type VARCHAR(50),
                    amount DECIMAL(15,2),
                    balance_before DECIMAL(15,2),
                    balance_after DECIMAL(15,2),
                    reference VARCHAR(100),
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            logger.info("Database tables ensured")


services: Optional[ServiceContainer] = None


def get_services() -> ServiceContainer:
    if services is None:
        raise RuntimeError("Services not initialized")
    return services


def generate_order_number() -> str:
    """Generate unique order number"""
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    random_suffix = str(uuid.uuid4())[:8].upper()
    return f"PO-{timestamp}-{random_suffix}"


def generate_tracking_number() -> str:
    """Generate unique tracking number"""
    return f"TRK{uuid.uuid4().hex[:12].upper()}"


def generate_idempotency_key(data: Dict[str, Any]) -> str:
    """Generate idempotency key"""
    content = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(content.encode()).hexdigest()[:32]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global services
    
    try:
        config = ServiceConfig()
        services = ServiceContainer(config)
        await services.initialize()
        yield
    finally:
        if services:
            await services.close()


app = FastAPI(
    title="Inventory Management Platform (Production)",
    description="Production-ready inventory management with full middleware integration",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/manufacturers", response_model=ManufacturerResponse)
async def create_manufacturer(
    data: ManufacturerCreate,
    idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    svc: ServiceContainer = Depends(get_services)
):
    """Create a new manufacturer"""
    
    if not idempotency_key:
        idempotency_key = generate_idempotency_key(data.dict())
    
    cached = await svc.redis.client.get(f"idempotency:manufacturer:{idempotency_key}")
    if cached:
        return ManufacturerResponse(**json.loads(cached))
    
    async with svc.db.transaction() as conn:
        existing = await conn.fetchrow(
            "SELECT id FROM manufacturers WHERE business_registration = $1",
            data.business_registration
        )
        if existing:
            raise HTTPException(status_code=400, detail="Manufacturer with this registration already exists")
        
        result = await conn.fetchrow(
            """
            INSERT INTO manufacturers (
                name, business_registration, contact_person, email, phone, address,
                product_categories, minimum_order_value, payment_terms, lead_time_days
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            RETURNING *
            """,
            data.name, data.business_registration, data.contact_person, data.email,
            data.phone, data.address, json.dumps(data.product_categories),
            data.minimum_order_value, data.payment_terms.value, data.lead_time_days
        )
    
    response = ManufacturerResponse(
        id=str(result['id']),
        name=result['name'],
        business_registration=result['business_registration'],
        contact_person=result['contact_person'],
        email=result['email'],
        phone=result['phone'],
        address=result['address'],
        product_categories=json.loads(result['product_categories']) if result['product_categories'] else [],
        minimum_order_value=float(result['minimum_order_value']),
        payment_terms=result['payment_terms'],
        lead_time_days=result['lead_time_days'],
        rating=float(result['rating']),
        verified=result['verified'],
        created_at=result['created_at']
    )
    
    await svc.redis.client.setex(
        f"idempotency:manufacturer:{idempotency_key}",
        3600,
        json.dumps(response.dict(), default=str)
    )
    
    event_data = {
        "event_type": "manufacturer.created",
        "manufacturer_id": str(result['id']),
        "name": data.name,
        "timestamp": datetime.utcnow().isoformat()
    }
    await svc.kafka.send_event("inventory-events", str(result['id']), event_data)
    await svc.dapr.publish_event("pubsub", "inventory-events", event_data)
    await svc.lakehouse.write_event("manufacturer_events", event_data)
    
    return response


@app.get("/manufacturers", response_model=List[ManufacturerResponse])
async def list_manufacturers(
    verified: Optional[bool] = Query(None),
    category: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    svc: ServiceContainer = Depends(get_services)
):
    """List manufacturers with filtering"""
    
    async with svc.db.acquire() as conn:
        where_conditions = []
        params = []
        param_count = 0
        
        if verified is not None:
            param_count += 1
            where_conditions.append(f"verified = ${param_count}")
            params.append(verified)
        
        if category:
            param_count += 1
            where_conditions.append(f"product_categories ? ${param_count}")
            params.append(category)
        
        where_clause = " WHERE " + " AND ".join(where_conditions) if where_conditions else ""
        
        param_count += 1
        params.append(limit)
        param_count += 1
        params.append(offset)
        
        query = f"""
        SELECT * FROM manufacturers
        {where_clause}
        ORDER BY created_at DESC
        LIMIT ${param_count - 1} OFFSET ${param_count}
        """
        
        results = await conn.fetch(query, *params)
        
        return [
            ManufacturerResponse(
                id=str(r['id']),
                name=r['name'],
                business_registration=r['business_registration'],
                contact_person=r['contact_person'],
                email=r['email'],
                phone=r['phone'],
                address=r['address'],
                product_categories=json.loads(r['product_categories']) if r['product_categories'] else [],
                minimum_order_value=float(r['minimum_order_value']),
                payment_terms=r['payment_terms'],
                lead_time_days=r['lead_time_days'],
                rating=float(r['rating']),
                verified=r['verified'],
                created_at=r['created_at']
            )
            for r in results
        ]


@app.get("/manufacturers/{manufacturer_id}", response_model=ManufacturerResponse)
async def get_manufacturer(
    manufacturer_id: str,
    svc: ServiceContainer = Depends(get_services)
):
    """Get manufacturer by ID"""
    
    async with svc.db.acquire() as conn:
        result = await conn.fetchrow(
            "SELECT * FROM manufacturers WHERE id = $1",
            uuid.UUID(manufacturer_id)
        )
        if not result:
            raise HTTPException(status_code=404, detail="Manufacturer not found")
        
        return ManufacturerResponse(
            id=str(result['id']),
            name=result['name'],
            business_registration=result['business_registration'],
            contact_person=result['contact_person'],
            email=result['email'],
            phone=result['phone'],
            address=result['address'],
            product_categories=json.loads(result['product_categories']) if result['product_categories'] else [],
            minimum_order_value=float(result['minimum_order_value']),
            payment_terms=result['payment_terms'],
            lead_time_days=result['lead_time_days'],
            rating=float(result['rating']),
            verified=result['verified'],
            created_at=result['created_at']
        )


@app.post("/products", response_model=ProductResponse)
async def create_product(
    data: ProductCreate,
    svc: ServiceContainer = Depends(get_services)
):
    """Create a new product"""
    
    async with svc.db.transaction() as conn:
        manufacturer = await conn.fetchrow(
            "SELECT id FROM manufacturers WHERE id = $1",
            uuid.UUID(data.manufacturer_id)
        )
        if not manufacturer:
            raise HTTPException(status_code=404, detail="Manufacturer not found")
        
        existing = await conn.fetchrow(
            "SELECT id FROM inventory_products WHERE sku = $1",
            data.sku
        )
        if existing:
            raise HTTPException(status_code=400, detail="Product with this SKU already exists")
        
        result = await conn.fetchrow(
            """
            INSERT INTO inventory_products (
                manufacturer_id, sku, name, description, category, unit_price,
                wholesale_price, minimum_order_quantity, available_quantity,
                reorder_level, unit_of_measure, specifications, images
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            RETURNING *
            """,
            uuid.UUID(data.manufacturer_id), data.sku, data.name, data.description,
            data.category, data.unit_price, data.wholesale_price,
            data.minimum_order_quantity, data.available_quantity, data.reorder_level,
            data.unit_of_measure, json.dumps(data.specifications), json.dumps(data.images)
        )
    
    response = ProductResponse(
        id=str(result['id']),
        manufacturer_id=str(result['manufacturer_id']),
        sku=result['sku'],
        name=result['name'],
        description=result['description'],
        category=result['category'],
        unit_price=float(result['unit_price']),
        wholesale_price=float(result['wholesale_price']),
        minimum_order_quantity=result['minimum_order_quantity'],
        available_quantity=result['available_quantity'],
        reorder_level=result['reorder_level'],
        unit_of_measure=result['unit_of_measure'],
        specifications=json.loads(result['specifications']) if result['specifications'] else {},
        images=json.loads(result['images']) if result['images'] else [],
        created_at=result['created_at'],
        updated_at=result['updated_at']
    )
    
    event_data = {
        "event_type": "product.created",
        "product_id": str(result['id']),
        "sku": data.sku,
        "timestamp": datetime.utcnow().isoformat()
    }
    await svc.kafka.send_event("inventory-events", str(result['id']), event_data)
    await svc.lakehouse.write_event("product_events", event_data)
    
    return response


@app.get("/products", response_model=List[ProductResponse])
async def list_products(
    manufacturer_id: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    low_stock: Optional[bool] = Query(None),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    svc: ServiceContainer = Depends(get_services)
):
    """List products with filtering"""
    
    async with svc.db.acquire() as conn:
        where_conditions = []
        params = []
        param_count = 0
        
        if manufacturer_id:
            param_count += 1
            where_conditions.append(f"manufacturer_id = ${param_count}")
            params.append(uuid.UUID(manufacturer_id))
        
        if category:
            param_count += 1
            where_conditions.append(f"category = ${param_count}")
            params.append(category)
        
        if low_stock:
            where_conditions.append("available_quantity <= reorder_level")
        
        where_clause = " WHERE " + " AND ".join(where_conditions) if where_conditions else ""
        
        param_count += 1
        params.append(limit)
        param_count += 1
        params.append(offset)
        
        query = f"""
        SELECT * FROM inventory_products
        {where_clause}
        ORDER BY created_at DESC
        LIMIT ${param_count - 1} OFFSET ${param_count}
        """
        
        results = await conn.fetch(query, *params)
        
        return [
            ProductResponse(
                id=str(r['id']),
                manufacturer_id=str(r['manufacturer_id']),
                sku=r['sku'],
                name=r['name'],
                description=r['description'],
                category=r['category'],
                unit_price=float(r['unit_price']),
                wholesale_price=float(r['wholesale_price']),
                minimum_order_quantity=r['minimum_order_quantity'],
                available_quantity=r['available_quantity'],
                reorder_level=r['reorder_level'],
                unit_of_measure=r['unit_of_measure'],
                specifications=json.loads(r['specifications']) if r['specifications'] else {},
                images=json.loads(r['images']) if r['images'] else [],
                created_at=r['created_at'],
                updated_at=r['updated_at']
            )
            for r in results
        ]


@app.post("/purchase-orders", response_model=PurchaseOrderResponse)
async def create_purchase_order(
    data: PurchaseOrderCreate,
    background_tasks: BackgroundTasks,
    idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    svc: ServiceContainer = Depends(get_services)
):
    """Create a new purchase order"""
    
    if not idempotency_key:
        idempotency_key = generate_idempotency_key(data.dict())
    
    cached = await svc.redis.client.get(f"idempotency:order:{idempotency_key}")
    if cached:
        return PurchaseOrderResponse(**json.loads(cached))
    
    async with svc.db.transaction() as conn:
        manufacturer = await conn.fetchrow(
            "SELECT * FROM manufacturers WHERE id = $1",
            uuid.UUID(data.manufacturer_id)
        )
        if not manufacturer:
            raise HTTPException(status_code=404, detail="Manufacturer not found")
        
        subtotal = 0.0
        for item in data.items:
            product = await conn.fetchrow(
                "SELECT * FROM inventory_products WHERE id = $1",
                uuid.UUID(item['product_id'])
            )
            if not product:
                raise HTTPException(status_code=404, detail=f"Product {item['product_id']} not found")
            
            if item['quantity'] < product['minimum_order_quantity']:
                raise HTTPException(
                    status_code=400,
                    detail=f"Quantity for {product['name']} below minimum order quantity"
                )
            
            subtotal += float(product['wholesale_price']) * item['quantity']
        
        if subtotal < float(manufacturer['minimum_order_value']):
            raise HTTPException(
                status_code=400,
                detail=f"Order value below manufacturer minimum of {manufacturer['minimum_order_value']}"
            )
        
        tax = subtotal * 0.075
        shipping_cost = 50.0
        total_amount = subtotal + tax + shipping_cost
        
        payment_terms_days = {
            PaymentTerms.IMMEDIATE: 0,
            PaymentTerms.NET_7: 7,
            PaymentTerms.NET_15: 15,
            PaymentTerms.NET_30: 30,
            PaymentTerms.NET_60: 60,
            PaymentTerms.NET_90: 90
        }
        due_date = datetime.utcnow() + timedelta(days=payment_terms_days.get(data.payment_terms, 30))
        
        order_number = generate_order_number()
        
        result = await conn.fetchrow(
            """
            INSERT INTO purchase_orders (
                order_number, agent_id, manufacturer_id, items, subtotal, tax,
                shipping_cost, total_amount, payment_method, payment_terms, due_date, notes
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            RETURNING *
            """,
            order_number, data.agent_id, uuid.UUID(data.manufacturer_id),
            json.dumps(data.items), subtotal, tax, shipping_cost, total_amount,
            data.payment_method, data.payment_terms.value, due_date, data.notes
        )
    
    response = PurchaseOrderResponse(
        id=str(result['id']),
        order_number=result['order_number'],
        agent_id=result['agent_id'],
        manufacturer_id=str(result['manufacturer_id']),
        items=json.loads(result['items']),
        subtotal=float(result['subtotal']),
        tax=float(result['tax']),
        shipping_cost=float(result['shipping_cost']),
        total_amount=float(result['total_amount']),
        payment_method=result['payment_method'],
        payment_terms=result['payment_terms'],
        due_date=result['due_date'],
        status=result['status'],
        notes=result['notes'],
        created_at=result['created_at']
    )
    
    await svc.redis.client.setex(
        f"idempotency:order:{idempotency_key}",
        3600,
        json.dumps(response.dict(), default=str)
    )
    
    transfer_id = int(hashlib.sha256(order_number.encode()).hexdigest()[:15], 16)
    agent_account = int(hashlib.sha256(data.agent_id.encode()).hexdigest()[:15], 16)
    manufacturer_account = int(hashlib.sha256(data.manufacturer_id.encode()).hexdigest()[:15], 16)
    await svc.tigerbeetle.create_transfer(
        transfer_id=transfer_id,
        debit_id=agent_account,
        credit_id=manufacturer_account,
        amount=int(total_amount * 100),
        ledger=1,
        code=1
    )
    
    event_data = {
        "event_type": "purchase_order.created",
        "order_id": str(result['id']),
        "order_number": order_number,
        "agent_id": data.agent_id,
        "manufacturer_id": data.manufacturer_id,
        "total_amount": total_amount,
        "timestamp": datetime.utcnow().isoformat()
    }
    await svc.kafka.send_event("inventory-events", order_number, event_data)
    await svc.dapr.publish_event("pubsub", "inventory-events", event_data)
    await svc.lakehouse.write_event("purchase_order_events", event_data)
    
    return response


@app.get("/purchase-orders", response_model=List[PurchaseOrderResponse])
async def list_purchase_orders(
    agent_id: Optional[str] = Query(None),
    manufacturer_id: Optional[str] = Query(None),
    status: Optional[OrderStatus] = Query(None),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    svc: ServiceContainer = Depends(get_services)
):
    """List purchase orders with filtering"""
    
    async with svc.db.acquire() as conn:
        where_conditions = []
        params = []
        param_count = 0
        
        if agent_id:
            param_count += 1
            where_conditions.append(f"agent_id = ${param_count}")
            params.append(agent_id)
        
        if manufacturer_id:
            param_count += 1
            where_conditions.append(f"manufacturer_id = ${param_count}")
            params.append(uuid.UUID(manufacturer_id))
        
        if status:
            param_count += 1
            where_conditions.append(f"status = ${param_count}")
            params.append(status.value)
        
        where_clause = " WHERE " + " AND ".join(where_conditions) if where_conditions else ""
        
        param_count += 1
        params.append(limit)
        param_count += 1
        params.append(offset)
        
        query = f"""
        SELECT * FROM purchase_orders
        {where_clause}
        ORDER BY created_at DESC
        LIMIT ${param_count - 1} OFFSET ${param_count}
        """
        
        results = await conn.fetch(query, *params)
        
        return [
            PurchaseOrderResponse(
                id=str(r['id']),
                order_number=r['order_number'],
                agent_id=r['agent_id'],
                manufacturer_id=str(r['manufacturer_id']),
                items=json.loads(r['items']),
                subtotal=float(r['subtotal']),
                tax=float(r['tax']),
                shipping_cost=float(r['shipping_cost']),
                total_amount=float(r['total_amount']),
                payment_method=r['payment_method'],
                payment_terms=r['payment_terms'],
                due_date=r['due_date'],
                status=r['status'],
                notes=r['notes'],
                created_at=r['created_at']
            )
            for r in results
        ]


@app.put("/purchase-orders/{order_id}/status")
async def update_order_status(
    order_id: str,
    status: OrderStatus,
    svc: ServiceContainer = Depends(get_services)
):
    """Update purchase order status"""
    
    async with svc.db.transaction() as conn:
        result = await conn.fetchrow(
            "SELECT * FROM purchase_orders WHERE id = $1",
            uuid.UUID(order_id)
        )
        if not result:
            raise HTTPException(status_code=404, detail="Order not found")
        
        await conn.execute(
            "UPDATE purchase_orders SET status = $1, updated_at = $2 WHERE id = $3",
            status.value, datetime.utcnow(), uuid.UUID(order_id)
        )
    
    event_data = {
        "event_type": "purchase_order.status_updated",
        "order_id": order_id,
        "old_status": result['status'],
        "new_status": status.value,
        "timestamp": datetime.utcnow().isoformat()
    }
    await svc.kafka.send_event("inventory-events", order_id, event_data)
    await svc.dapr.publish_event("pubsub", "inventory-events", event_data)
    
    return {"success": True, "order_id": order_id, "status": status.value}


@app.post("/credit-facilities/apply", response_model=CreditFacilityResponse)
async def apply_for_credit(
    data: CreditApplicationCreate,
    svc: ServiceContainer = Depends(get_services)
):
    """Apply for credit facility"""
    
    async with svc.db.transaction() as conn:
        existing = await conn.fetchrow(
            "SELECT * FROM credit_facilities WHERE agent_id = $1",
            data.agent_id
        )
        if existing:
            raise HTTPException(status_code=400, detail="Credit facility already exists for this agent")
        
        credit_score = 500
        credit_score += min(100, data.years_in_business * 20)
        credit_score += min(100, int(data.business_revenue / 100000) * 10)
        credit_score -= min(100, int(data.existing_loans / 50000) * 10)
        if data.collateral:
            credit_score += 50
        if data.guarantor_info:
            credit_score += 30
        
        credit_score = max(300, min(850, credit_score))
        
        if credit_score >= 700:
            credit_limit = min(data.requested_amount, data.business_revenue * 0.5)
            interest_rate = 12.0
            status = CreditStatus.APPROVED
        elif credit_score >= 600:
            credit_limit = min(data.requested_amount * 0.7, data.business_revenue * 0.3)
            interest_rate = 15.0
            status = CreditStatus.APPROVED
        elif credit_score >= 500:
            credit_limit = min(data.requested_amount * 0.5, data.business_revenue * 0.2)
            interest_rate = 18.0
            status = CreditStatus.PENDING
        else:
            raise HTTPException(status_code=400, detail="Credit application rejected due to low credit score")
        
        result = await conn.fetchrow(
            """
            INSERT INTO credit_facilities (
                agent_id, credit_limit, available_credit, interest_rate,
                payment_terms, status, credit_score, approval_date
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING *
            """,
            data.agent_id, credit_limit, credit_limit, interest_rate,
            PaymentTerms.NET_30.value, status.value, credit_score,
            datetime.utcnow() if status == CreditStatus.APPROVED else None
        )
    
    response = CreditFacilityResponse(
        id=str(result['id']),
        agent_id=result['agent_id'],
        credit_limit=float(result['credit_limit']),
        available_credit=float(result['available_credit']),
        utilized_credit=float(result['utilized_credit']),
        interest_rate=float(result['interest_rate']),
        payment_terms=result['payment_terms'],
        status=result['status'],
        approval_date=result['approval_date'],
        credit_score=result['credit_score'],
        created_at=result['created_at']
    )
    
    event_data = {
        "event_type": "credit_facility.created",
        "facility_id": str(result['id']),
        "agent_id": data.agent_id,
        "credit_limit": credit_limit,
        "status": status.value,
        "timestamp": datetime.utcnow().isoformat()
    }
    await svc.kafka.send_event("inventory-events", data.agent_id, event_data)
    await svc.lakehouse.write_event("credit_events", event_data)
    
    return response


@app.get("/credit-facilities/{agent_id}", response_model=CreditFacilityResponse)
async def get_credit_facility(
    agent_id: str,
    svc: ServiceContainer = Depends(get_services)
):
    """Get credit facility for agent"""
    
    async with svc.db.acquire() as conn:
        result = await conn.fetchrow(
            "SELECT * FROM credit_facilities WHERE agent_id = $1",
            agent_id
        )
        if not result:
            raise HTTPException(status_code=404, detail="Credit facility not found")
        
        return CreditFacilityResponse(
            id=str(result['id']),
            agent_id=result['agent_id'],
            credit_limit=float(result['credit_limit']),
            available_credit=float(result['available_credit']),
            utilized_credit=float(result['utilized_credit']),
            interest_rate=float(result['interest_rate']),
            payment_terms=result['payment_terms'],
            status=result['status'],
            approval_date=result['approval_date'],
            credit_score=result['credit_score'],
            created_at=result['created_at']
        )


@app.post("/shipments", response_model=ShipmentResponse)
async def create_shipment(
    data: ShipmentCreate,
    svc: ServiceContainer = Depends(get_services)
):
    """Create a new shipment"""
    
    async with svc.db.transaction() as conn:
        order = await conn.fetchrow(
            "SELECT * FROM purchase_orders WHERE id = $1",
            uuid.UUID(data.purchase_order_id)
        )
        if not order:
            raise HTTPException(status_code=404, detail="Purchase order not found")
        
        tracking_number = generate_tracking_number()
        
        initial_tracking = [{
            "status": ShipmentStatus.PREPARING.value,
            "location": data.origin_address,
            "timestamp": datetime.utcnow().isoformat(),
            "description": "Shipment created and preparing for dispatch"
        }]
        
        result = await conn.fetchrow(
            """
            INSERT INTO shipments (
                tracking_number, purchase_order_id, agent_id, manufacturer_id,
                carrier, origin_address, destination_address, estimated_delivery,
                tracking_history
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            RETURNING *
            """,
            tracking_number, uuid.UUID(data.purchase_order_id), order['agent_id'],
            order['manufacturer_id'], data.carrier, data.origin_address,
            data.destination_address, data.estimated_delivery, json.dumps(initial_tracking)
        )
        
        await conn.execute(
            "UPDATE purchase_orders SET status = $1, updated_at = $2 WHERE id = $3",
            OrderStatus.SHIPPED.value, datetime.utcnow(), uuid.UUID(data.purchase_order_id)
        )
    
    response = ShipmentResponse(
        id=str(result['id']),
        tracking_number=result['tracking_number'],
        purchase_order_id=str(result['purchase_order_id']),
        agent_id=result['agent_id'],
        manufacturer_id=str(result['manufacturer_id']),
        carrier=result['carrier'],
        origin_address=result['origin_address'],
        destination_address=result['destination_address'],
        estimated_delivery=result['estimated_delivery'],
        actual_delivery=result['actual_delivery'],
        status=result['status'],
        current_location=result['current_location'],
        tracking_history=json.loads(result['tracking_history']),
        created_at=result['created_at']
    )
    
    event_data = {
        "event_type": "shipment.created",
        "shipment_id": str(result['id']),
        "tracking_number": tracking_number,
        "order_id": data.purchase_order_id,
        "timestamp": datetime.utcnow().isoformat()
    }
    await svc.kafka.send_event("inventory-events", tracking_number, event_data)
    await svc.dapr.publish_event("pubsub", "inventory-events", event_data)
    await svc.lakehouse.write_event("shipment_events", event_data)
    
    return response


@app.get("/shipments/{tracking_number}", response_model=ShipmentResponse)
async def get_shipment(
    tracking_number: str,
    svc: ServiceContainer = Depends(get_services)
):
    """Get shipment by tracking number"""
    
    async with svc.db.acquire() as conn:
        result = await conn.fetchrow(
            "SELECT * FROM shipments WHERE tracking_number = $1",
            tracking_number
        )
        if not result:
            raise HTTPException(status_code=404, detail="Shipment not found")
        
        return ShipmentResponse(
            id=str(result['id']),
            tracking_number=result['tracking_number'],
            purchase_order_id=str(result['purchase_order_id']),
            agent_id=result['agent_id'],
            manufacturer_id=str(result['manufacturer_id']) if result['manufacturer_id'] else None,
            carrier=result['carrier'],
            origin_address=result['origin_address'],
            destination_address=result['destination_address'],
            estimated_delivery=result['estimated_delivery'],
            actual_delivery=result['actual_delivery'],
            status=result['status'],
            current_location=result['current_location'],
            tracking_history=json.loads(result['tracking_history']) if result['tracking_history'] else [],
            created_at=result['created_at']
        )


@app.put("/shipments/{tracking_number}/status")
async def update_shipment_status(
    tracking_number: str,
    status: ShipmentStatus,
    location: Optional[str] = None,
    description: Optional[str] = None,
    svc: ServiceContainer = Depends(get_services)
):
    """Update shipment status"""
    
    async with svc.db.transaction() as conn:
        result = await conn.fetchrow(
            "SELECT * FROM shipments WHERE tracking_number = $1",
            tracking_number
        )
        if not result:
            raise HTTPException(status_code=404, detail="Shipment not found")
        
        tracking_history = json.loads(result['tracking_history']) if result['tracking_history'] else []
        tracking_history.append({
            "status": status.value,
            "location": location or result['current_location'],
            "timestamp": datetime.utcnow().isoformat(),
            "description": description or f"Status updated to {status.value}"
        })
        
        actual_delivery = datetime.utcnow() if status == ShipmentStatus.DELIVERED else None
        
        await conn.execute(
            """
            UPDATE shipments 
            SET status = $1, current_location = $2, tracking_history = $3,
                actual_delivery = COALESCE($4, actual_delivery), updated_at = $5
            WHERE tracking_number = $6
            """,
            status.value, location, json.dumps(tracking_history),
            actual_delivery, datetime.utcnow(), tracking_number
        )
        
        if status == ShipmentStatus.DELIVERED:
            await conn.execute(
                "UPDATE purchase_orders SET status = $1, updated_at = $2 WHERE id = $3",
                OrderStatus.DELIVERED.value, datetime.utcnow(), result['purchase_order_id']
            )
    
    event_data = {
        "event_type": "shipment.status_updated",
        "tracking_number": tracking_number,
        "old_status": result['status'],
        "new_status": status.value,
        "location": location,
        "timestamp": datetime.utcnow().isoformat()
    }
    await svc.kafka.send_event("inventory-events", tracking_number, event_data)
    await svc.dapr.publish_event("pubsub", "inventory-events", event_data)
    
    return {"success": True, "tracking_number": tracking_number, "status": status.value}


@app.post("/inventory", response_model=InventoryResponse)
async def create_inventory(
    data: InventoryCreate,
    svc: ServiceContainer = Depends(get_services)
):
    """Create inventory record"""
    
    async with svc.db.transaction() as conn:
        existing = await conn.fetchrow(
            "SELECT id FROM inventory WHERE warehouse_id = $1 AND product_id = $2",
            uuid.UUID(data.warehouse_id), uuid.UUID(data.product_id)
        )
        if existing:
            raise HTTPException(status_code=400, detail="Inventory record already exists")
        
        result = await conn.fetchrow(
            """
            INSERT INTO inventory (
                warehouse_id, product_id, quantity_available, reorder_point,
                reorder_quantity, min_stock_level, max_stock_level
            ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING *
            """,
            uuid.UUID(data.warehouse_id), uuid.UUID(data.product_id),
            data.quantity_available, data.reorder_point, data.reorder_quantity,
            data.min_stock_level, data.max_stock_level
        )
    
    is_low_stock = result['quantity_available'] <= result['reorder_point']
    
    return InventoryResponse(
        id=str(result['id']),
        warehouse_id=str(result['warehouse_id']),
        product_id=str(result['product_id']),
        quantity_available=result['quantity_available'],
        quantity_reserved=result['quantity_reserved'],
        quantity_in_transit=result['quantity_in_transit'],
        quantity_damaged=result['quantity_damaged'],
        reorder_point=result['reorder_point'],
        reorder_quantity=result['reorder_quantity'],
        min_stock_level=result['min_stock_level'],
        max_stock_level=result['max_stock_level'],
        status=result['status'],
        is_low_stock=is_low_stock,
        created_at=result['created_at'],
        updated_at=result['updated_at']
    )


@app.post("/inventory/reserve")
async def reserve_inventory(
    warehouse_id: str,
    product_id: str,
    quantity: int,
    order_id: str,
    svc: ServiceContainer = Depends(get_services)
):
    """Reserve inventory for an order with pessimistic locking"""
    
    async with svc.db.transaction() as conn:
        result = await conn.fetchrow(
            """
            SELECT * FROM inventory
            WHERE warehouse_id = $1 AND product_id = $2
            FOR UPDATE
            """,
            uuid.UUID(warehouse_id), uuid.UUID(product_id)
        )
        
        if not result:
            raise HTTPException(status_code=404, detail="Inventory record not found")
        
        if result['quantity_available'] < quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient inventory. Available: {result['quantity_available']}, Requested: {quantity}"
            )
        
        await conn.execute(
            """
            UPDATE inventory
            SET quantity_available = quantity_available - $1,
                quantity_reserved = quantity_reserved + $1,
                updated_at = $2
            WHERE warehouse_id = $3 AND product_id = $4
            """,
            quantity, datetime.utcnow(), uuid.UUID(warehouse_id), uuid.UUID(product_id)
        )
        
        await conn.execute(
            """
            INSERT INTO stock_movements (
                warehouse_id, product_id, movement_type, quantity,
                reference_type, reference_id, reason
            ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            uuid.UUID(warehouse_id), uuid.UUID(product_id),
            StockMovementType.OUTBOUND.value, quantity,
            "order", uuid.UUID(order_id), "Inventory reserved for order"
        )
    
    event_data = {
        "event_type": "inventory.reserved",
        "warehouse_id": warehouse_id,
        "product_id": product_id,
        "quantity": quantity,
        "order_id": order_id,
        "timestamp": datetime.utcnow().isoformat()
    }
    await svc.kafka.send_event("inventory-events", product_id, event_data)
    
    return {"success": True, "reserved_quantity": quantity}


@app.post("/inventory/release")
async def release_inventory(
    warehouse_id: str,
    product_id: str,
    quantity: int,
    reason: str,
    svc: ServiceContainer = Depends(get_services)
):
    """Release reserved inventory"""
    
    async with svc.db.transaction() as conn:
        await conn.execute(
            """
            UPDATE inventory
            SET quantity_available = quantity_available + $1,
                quantity_reserved = quantity_reserved - $1,
                updated_at = $2
            WHERE warehouse_id = $3 AND product_id = $4
            """,
            quantity, datetime.utcnow(), uuid.UUID(warehouse_id), uuid.UUID(product_id)
        )
        
        await conn.execute(
            """
            INSERT INTO stock_movements (
                warehouse_id, product_id, movement_type, quantity, reason
            ) VALUES ($1, $2, $3, $4, $5)
            """,
            uuid.UUID(warehouse_id), uuid.UUID(product_id),
            StockMovementType.ADJUSTMENT.value, quantity, reason
        )
    
    return {"success": True, "released_quantity": quantity}


@app.get("/inventory/low-stock")
async def get_low_stock_items(
    svc: ServiceContainer = Depends(get_services)
):
    """Get items that need reordering"""
    
    async with svc.db.acquire() as conn:
        results = await conn.fetch(
            """
            SELECT i.*, p.name as product_name, p.sku, w.name as warehouse_name
            FROM inventory i
            JOIN inventory_products p ON i.product_id = p.id
            JOIN warehouses w ON i.warehouse_id = w.id
            WHERE i.quantity_available <= i.reorder_point
            ORDER BY (i.reorder_point - i.quantity_available) DESC
            """
        )
        
        return [
            {
                "warehouse_id": str(r['warehouse_id']),
                "warehouse_name": r['warehouse_name'],
                "product_id": str(r['product_id']),
                "product_name": r['product_name'],
                "sku": r['sku'],
                "quantity_available": r['quantity_available'],
                "reorder_point": r['reorder_point'],
                "reorder_quantity": r['reorder_quantity'],
                "shortage": r['reorder_point'] - r['quantity_available']
            }
            for r in results
        ]


@app.get("/inventory/summary")
async def get_inventory_summary(
    svc: ServiceContainer = Depends(get_services)
):
    """Get overall inventory summary"""
    
    async with svc.db.acquire() as conn:
        results = await conn.fetch(
            """
            SELECT 
                w.id as warehouse_id,
                w.name as warehouse_name,
                w.code as warehouse_code,
                COUNT(DISTINCT i.product_id) as total_products,
                SUM(i.quantity_available + i.quantity_reserved + i.quantity_in_transit) as total_quantity,
                SUM(i.quantity_available) as total_available,
                SUM(i.quantity_reserved) as total_reserved,
                SUM(i.quantity_in_transit) as total_in_transit,
                SUM(i.quantity_damaged) as total_damaged,
                COUNT(CASE WHEN i.quantity_available <= i.reorder_point THEN 1 END) as low_stock_count
            FROM warehouses w
            LEFT JOIN inventory i ON w.id = i.warehouse_id
            WHERE w.is_active = TRUE
            GROUP BY w.id, w.name, w.code
            """
        )
        
        warehouses = [
            {
                "warehouse_id": str(r['warehouse_id']),
                "warehouse_name": r['warehouse_name'],
                "warehouse_code": r['warehouse_code'],
                "total_products": r['total_products'] or 0,
                "total_quantity": r['total_quantity'] or 0,
                "total_available": r['total_available'] or 0,
                "total_reserved": r['total_reserved'] or 0,
                "total_in_transit": r['total_in_transit'] or 0,
                "total_damaged": r['total_damaged'] or 0,
                "low_stock_count": r['low_stock_count'] or 0
            }
            for r in results
        ]
        
        return {
            "warehouses": warehouses,
            "total_warehouses": len(warehouses),
            "grand_total_quantity": sum(w["total_quantity"] for w in warehouses),
            "grand_total_available": sum(w["total_available"] for w in warehouses),
            "total_low_stock_items": sum(w["low_stock_count"] for w in warehouses)
        }


@app.get("/health")
async def health_check(svc: ServiceContainer = Depends(get_services)):
    """Health check endpoint"""
    
    health_status = {
        "status": "healthy",
        "service": "Inventory Management Platform (Production)",
        "version": "2.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "components": {}
    }
    
    try:
        async with svc.db.acquire() as conn:
            await conn.fetchval("SELECT 1")
        health_status["components"]["database"] = "healthy"
    except Exception as e:
        health_status["components"]["database"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"
    
    try:
        await svc.redis.client.ping()
        health_status["components"]["redis"] = "healthy"
    except Exception as e:
        health_status["components"]["redis"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"
    
    return health_status


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8027)
