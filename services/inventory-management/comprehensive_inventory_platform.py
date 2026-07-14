import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
"""
Comprehensive Inventory Management Platform
Integrates agents with manufacturers, provides credit facilities, shipping and logistics
Port: 8027
"""

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app)
setup_logging("inventory-management-platform")
app.include_router(metrics_router)

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from enum import Enum
import asyncpg
import redis.asyncio as redis
import uuid
import json

import os
app = FastAPI(title="Inventory Management Platform", version="1.0.0")

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database connection pool
db_pool = None
redis_client = None

# ==================== ENUMS ====================

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

# ==================== MODELS ====================

class Manufacturer(BaseModel):
    id: Optional[str] = None
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
    rating: Optional[float] = 4.0
    verified: bool = False
    created_at: Optional[datetime] = None

class InventoryProduct(BaseModel):
    id: Optional[str] = None
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
    created_at: Optional[datetime] = None

class PurchaseOrder(BaseModel):
    id: Optional[str] = None
    order_number: str
    agent_id: str
    manufacturer_id: str
    items: List[Dict[str, Any]]
    subtotal: float
    tax: float
    shipping_cost: float
    total_amount: float
    payment_method: str
    payment_terms: PaymentTerms
    due_date: Optional[datetime] = None
    status: OrderStatus = OrderStatus.PENDING
    notes: Optional[str] = None
    created_at: Optional[datetime] = None

class CreditFacility(BaseModel):
    id: Optional[str] = None
    agent_id: str
    credit_limit: float
    available_credit: float
    utilized_credit: float
    interest_rate: float
    payment_terms: PaymentTerms
    status: CreditStatus = CreditStatus.PENDING
    approval_date: Optional[datetime] = None
    last_review_date: Optional[datetime] = None
    credit_score: Optional[int] = None
    created_at: Optional[datetime] = None

class CreditApplication(BaseModel):
    agent_id: str
    requested_amount: float
    purpose: str
    business_revenue: float
    years_in_business: int
    existing_loans: float
    collateral: Optional[str] = None
    guarantor_info: Optional[Dict[str, Any]] = None

class Shipment(BaseModel):
    id: Optional[str] = None
    tracking_number: str
    purchase_order_id: str
    agent_id: str
    manufacturer_id: str
    carrier: str
    origin_address: str
    destination_address: str
    estimated_delivery: datetime
    actual_delivery: Optional[datetime] = None
    status: ShipmentStatus = ShipmentStatus.PREPARING
    current_location: Optional[str] = None
    tracking_history: List[Dict[str, Any]] = []
    created_at: Optional[datetime] = None

class LogisticsProvider(BaseModel):
    id: Optional[str] = None
    name: str
    contact: str
    email: str
    phone: str
    service_areas: List[str]
    pricing_model: str
    base_rate: float
    rating: Optional[float] = 4.0
    active: bool = True

# ==================== DATABASE INITIALIZATION ====================

async def init_db():
    """Initialize database tables"""
    global db_pool, redis_client
    
    try:
        db_pool = await asyncpg.create_pool(
            host=os.getenv('DB_HOST', 'localhost'),
            port=5432,
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', ''),
            database="remittance",
            min_size=10,
            max_size=20
        )
        
        redis_client = await redis.from_url("redis://localhost:6379", decode_responses=True)
        
        async with db_pool.acquire() as conn:
            # Create all tables
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
                    agent_id UUID NOT NULL,
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
                    agent_id UUID UNIQUE NOT NULL,
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
                    agent_id UUID NOT NULL,
                    manufacturer_id UUID REFERENCES manufacturers(id),
                    carrier VARCHAR(255),
                    origin_address TEXT,
                    destination_address TEXT,
                    estimated_delivery TIMESTAMP,
                    actual_delivery TIMESTAMP,
                    status VARCHAR(50) DEFAULT 'preparing',
                    current_location VARCHAR(255),
                    tracking_history JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS logistics_providers (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    name VARCHAR(255) NOT NULL,
                    contact VARCHAR(255),
                    email VARCHAR(255),
                    phone VARCHAR(50),
                    service_areas JSONB,
                    pricing_model VARCHAR(50),
                    base_rate DECIMAL(10,2),
                    rating DECIMAL(3,2) DEFAULT 4.0,
                    active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS inventory_alerts (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    product_id UUID REFERENCES inventory_products(id),
                    alert_type VARCHAR(50),
                    current_quantity INTEGER,
                    threshold INTEGER,
                    priority VARCHAR(20),
                    resolved BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    resolved_at TIMESTAMP
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
            
            print("✅ Database tables initialized successfully")
    except Exception as e:
        print(f"❌ Database initialization error: {e}")

@app.on_event("startup")
async def startup():
    await init_db()

@app.on_event("shutdown")
async def shutdown():
    if db_pool:
        await db_pool.close()
    if redis_client:
        await redis_client.close()

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "Inventory Management Platform", "port": 8027}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8027)

