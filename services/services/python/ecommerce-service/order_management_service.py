"""
Order Management Service
Complete order lifecycle management with status tracking, fulfillment, and notifications
"""

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from enum import Enum
import asyncpg
import httpx
import json
import logging

import os
# Configuration
app = FastAPI(title="Order Management Service")
logger = logging.getLogger(__name__)

# Database connection pool
db_pool = None

# Enums
class OrderStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    FAILED = "failed"

class PaymentStatus(str, Enum):
    PENDING = "pending"
    AUTHORIZED = "authorized"
    CAPTURED = "captured"
    FAILED = "failed"
    REFUNDED = "refunded"

class FulfillmentStatus(str, Enum):
    UNFULFILLED = "unfulfilled"
    PARTIALLY_FULFILLED = "partially_fulfilled"
    FULFILLED = "fulfilled"
    CANCELLED = "cancelled"

class ShipmentStatus(str, Enum):
    PENDING = "pending"
    PICKED_UP = "picked_up"
    IN_TRANSIT = "in_transit"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETURNED = "returned"

# Models
class OrderItem(BaseModel):
    product_id: int
    product_name: str
    variant_id: Optional[int] = None
    variant_name: Optional[str] = None
    sku: str
    quantity: int
    unit_price: float
    total_price: float
    tax: float = 0.0

class Address(BaseModel):
    first_name: str
    last_name: str
    company: Optional[str] = None
    address_line1: str
    address_line2: Optional[str] = None
    city: str
    state: str
    postal_code: str
    country: str
    phone: str
    email: Optional[EmailStr] = None

class ShipmentTracking(BaseModel):
    carrier: str
    tracking_number: str
    tracking_url: Optional[str] = None
    status: ShipmentStatus
    estimated_delivery: Optional[datetime] = None
    shipped_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None

class Fulfillment(BaseModel):
    id: int
    order_id: int
    items: List[Dict[str, Any]]
    status: FulfillmentStatus
    tracking: Optional[ShipmentTracking] = None
    warehouse_id: Optional[int] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class Order(BaseModel):
    id: int
    order_number: str
    customer_id: int
    customer_email: EmailStr
    status: OrderStatus
    payment_status: PaymentStatus
    fulfillment_status: FulfillmentStatus
    items: List[OrderItem]
    subtotal: float
    shipping_cost: float
    tax: float
    discount: float
    total: float
    currency: str = "USD"
    shipping_address: Address
    billing_address: Optional[Address] = None
    payment_method: str
    shipping_method: str
    notes: Optional[str] = None
    fulfillments: List[Fulfillment] = []
    created_at: datetime
    updated_at: datetime

class OrderStatusUpdate(BaseModel):
    status: OrderStatus
    notes: Optional[str] = None

class FulfillmentCreate(BaseModel):
    order_id: int
    items: List[Dict[str, Any]]  # [{"order_item_id": 1, "quantity": 2}]
    warehouse_id: Optional[int] = None
    tracking: Optional[ShipmentTracking] = None
    notes: Optional[str] = None

# Database initialization
async def init_db():
    global db_pool
    db_pool = await asyncpg.create_pool(
        host=os.getenv('DB_HOST', 'localhost'),
        port=5432,
        database='remittance',
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', ''),
        min_size=5,
        max_size=20
    )
    
    # Create tables
    async with db_pool.acquire() as conn:
        # Orders table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                order_number VARCHAR(50) UNIQUE NOT NULL,
                customer_id INTEGER NOT NULL,
                customer_email VARCHAR(255) NOT NULL,
                status VARCHAR(50) NOT NULL DEFAULT 'pending',
                payment_status VARCHAR(50) NOT NULL DEFAULT 'pending',
                fulfillment_status VARCHAR(50) NOT NULL DEFAULT 'unfulfilled',
                items JSONB NOT NULL,
                subtotal DECIMAL(10,2) NOT NULL,
                shipping_cost DECIMAL(10,2) DEFAULT 0,
                tax DECIMAL(10,2) DEFAULT 0,
                discount DECIMAL(10,2) DEFAULT 0,
                total DECIMAL(10,2) NOT NULL,
                currency VARCHAR(3) DEFAULT 'USD',
                shipping_address JSONB NOT NULL,
                billing_address JSONB,
                payment_method VARCHAR(50) NOT NULL,
                payment_info JSONB,
                shipping_method VARCHAR(50) NOT NULL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        
        # Fulfillments table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS fulfillments (
                id SERIAL PRIMARY KEY,
                order_id INTEGER REFERENCES orders(id) ON DELETE CASCADE,
                items JSONB NOT NULL,
                status VARCHAR(50) NOT NULL DEFAULT 'unfulfilled',
                tracking JSONB,
                warehouse_id INTEGER,
                notes TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        
        # Order status history table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS order_status_history (
                id SERIAL PRIMARY KEY,
                order_id INTEGER REFERENCES orders(id) ON DELETE CASCADE,
                from_status VARCHAR(50),
                to_status VARCHAR(50) NOT NULL,
                notes TEXT,
                changed_by INTEGER,
                created_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        
        # Order events table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS order_events (
                id SERIAL PRIMARY KEY,
                order_id INTEGER REFERENCES orders(id) ON DELETE CASCADE,
                event_type VARCHAR(50) NOT NULL,
                event_data JSONB,
                created_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        
        # Create indexes
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_fulfillments_order ON fulfillments(order_id)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_order_history_order ON order_status_history(order_id)')

# Helper functions
async def generate_order_number() -> str:
    """Generate unique order number"""
    import random
    import string
    timestamp = datetime.utcnow().strftime('%Y%m%d')
    random_part = ''.join(random.choices(string.digits, k=6))
    return f"ORD-{timestamp}-{random_part}"

async def log_order_event(order_id: int, event_type: str, event_data: Dict):
    """Log order event"""
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO order_events (order_id, event_type, event_data)
            VALUES ($1, $2, $3)
            """,
            order_id, event_type, json.dumps(event_data)
        )

async def update_order_status(order_id: int, new_status: OrderStatus, notes: Optional[str] = None, changed_by: Optional[int] = None):
    """Update order status and log history"""
    async with db_pool.acquire() as conn:
        # Get current status
        current = await conn.fetchrow(
            "SELECT status FROM orders WHERE id = $1",
            order_id
        )
        
        if not current:
            raise HTTPException(status_code=404, detail="Order not found")
        
        old_status = current['status']
        
        # Update order
        await conn.execute(
            """
            UPDATE orders
            SET status = $1, updated_at = NOW()
            WHERE id = $2
            """,
            new_status.value, order_id
        )
        
        # Log status change
        await conn.execute(
            """
            INSERT INTO order_status_history (order_id, from_status, to_status, notes, changed_by)
            VALUES ($1, $2, $3, $4, $5)
            """,
            order_id, old_status, new_status.value, notes, changed_by
        )
        
        await log_order_event(order_id, "status_changed", {
            "from": old_status,
            "to": new_status.value,
            "notes": notes
        })

async def update_inventory(order_id: int, operation: str = "reserve"):
    """Update inventory when order is placed or cancelled"""
    async with db_pool.acquire() as conn:
        order = await conn.fetchrow(
            "SELECT items FROM orders WHERE id = $1",
            order_id
        )
        
        if not order:
            return
        
        items = json.loads(order['items'])
        
        # Call inventory service
        async with httpx.AsyncClient() as client:
            try:
                await client.post(
                    "http://localhost:8084/inventory/update",
                    json={
                        "order_id": order_id,
                        "operation": operation,
                        "items": items
                    },
                    timeout=10.0
                )
            except Exception as e:
                logger.error(f"Failed to update inventory: {e}")

async def send_order_notification(order_id: int, notification_type: str):
    """Send order notification to customer"""
    async with db_pool.acquire() as conn:
        order = await conn.fetchrow(
            "SELECT customer_email, order_number FROM orders WHERE id = $1",
            order_id
        )
        
        if not order:
            return
        
        # Implement email sending via email service
        try:
            import requests
            email_service_url = os.getenv('EMAIL_SERVICE_URL', 'http://localhost:8001')
            subject_map = {
                'shipped': 'Order Shipped',
                'delivered': 'Order Delivered',
                'cancelled': 'Order Cancelled'
            }
            body_map = {
                'shipped': f"Your order #{order['order_number']} has been shipped!",
                'delivered': f"Your order #{order['order_number']} has been delivered!",
                'cancelled': f"Your order #{order['order_number']} has been cancelled."
            }
            requests.post(f"{email_service_url}/api/v1/email/send", json={
                "to": order['customer_email'],
                "subject": subject_map.get(notification_type, 'Order Update'),
                "body": body_map.get(notification_type, f"Order #{order['order_number']} status updated")
            }, timeout=5)
        except Exception as e:
            logger.error(f"Failed to send {notification_type} notification: {e}")
        logger.info(f"Sending {notification_type} notification for order {order['order_number']} to {order['customer_email']}")

# API Endpoints

@app.on_event("startup")
async def startup():
    await init_db()

@app.on_event("shutdown")
async def shutdown():
    if db_pool:
        await db_pool.close()

@app.post("/orders", response_model=Order)
async def create_order(order: Order, background_tasks: BackgroundTasks):
    """Create new order"""
    async with db_pool.acquire() as conn:
        # Generate order number
        order_number = await generate_order_number()
        
        # Insert order
        order_id = await conn.fetchval(
            """
            INSERT INTO orders (
                order_number, customer_id, customer_email, status,
                payment_status, fulfillment_status, items, subtotal,
                shipping_cost, tax, discount, total, currency,
                shipping_address, billing_address, payment_method,
                shipping_method, notes
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18)
            RETURNING id
            """,
            order_number, order.customer_id, order.customer_email,
            order.status.value, order.payment_status.value,
            order.fulfillment_status.value, json.dumps([item.dict() for item in order.items]),
            order.subtotal, order.shipping_cost, order.tax, order.discount,
            order.total, order.currency, json.dumps(order.shipping_address.dict()),
            json.dumps(order.billing_address.dict()) if order.billing_address else None,
            order.payment_method, order.shipping_method, order.notes
        )
        
        await log_order_event(order_id, "order_created", {
            "order_number": order_number,
            "total": float(order.total)
        })
        
        # Reserve inventory
        background_tasks.add_task(update_inventory, order_id, "reserve")
        
        # Send confirmation email
        background_tasks.add_task(send_order_notification, order_id, "order_confirmation")
        
        # Get created order
        created_order = await conn.fetchrow(
            "SELECT * FROM orders WHERE id = $1",
            order_id
        )
        
        order_dict = dict(created_order)
        order_dict['items'] = [OrderItem(**item) for item in json.loads(order_dict['items'])]
        order_dict['shipping_address'] = Address(**json.loads(order_dict['shipping_address']))
        if order_dict['billing_address']:
            order_dict['billing_address'] = Address(**json.loads(order_dict['billing_address']))
        order_dict['fulfillments'] = []
        
        return Order(**order_dict)

@app.get("/orders/{order_id}", response_model=Order)
async def get_order(order_id: int):
    """Get order details"""
    async with db_pool.acquire() as conn:
        order = await conn.fetchrow(
            "SELECT * FROM orders WHERE id = $1",
            order_id
        )
        
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        # Get fulfillments
        fulfillments = await conn.fetch(
            "SELECT * FROM fulfillments WHERE order_id = $1",
            order_id
        )
        
        order_dict = dict(order)
        order_dict['items'] = [OrderItem(**item) for item in json.loads(order_dict['items'])]
        order_dict['shipping_address'] = Address(**json.loads(order_dict['shipping_address']))
        if order_dict['billing_address']:
            order_dict['billing_address'] = Address(**json.loads(order_dict['billing_address']))
        
        order_dict['fulfillments'] = []
        for f in fulfillments:
            f_dict = dict(f)
            f_dict['items'] = json.loads(f_dict['items'])
            if f_dict['tracking']:
                f_dict['tracking'] = ShipmentTracking(**json.loads(f_dict['tracking']))
            order_dict['fulfillments'].append(Fulfillment(**f_dict))
        
        return Order(**order_dict)

@app.get("/orders")
async def list_orders(
    customer_id: Optional[int] = None,
    status: Optional[OrderStatus] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    page: int = 1,
    page_size: int = 20
):
    """List orders with filters"""
    conditions = []
    params = []
    param_count = 1
    
    if customer_id:
        conditions.append(f"customer_id = ${param_count}")
        params.append(customer_id)
        param_count += 1
    
    if status:
        conditions.append(f"status = ${param_count}")
        params.append(status.value)
        param_count += 1
    
    if from_date:
        conditions.append(f"created_at >= ${param_count}")
        params.append(from_date)
        param_count += 1
    
    if to_date:
        conditions.append(f"created_at <= ${param_count}")
        params.append(to_date)
        param_count += 1
    
    where_clause = " AND ".join(conditions) if conditions else "TRUE"
    offset = (page - 1) * page_size
    
    async with db_pool.acquire() as conn:
        # Get total count
        total = await conn.fetchval(
            f"SELECT COUNT(*) FROM orders WHERE {where_clause}",
            *params
        )
        
        # Get orders
        orders = await conn.fetch(
            f"""
            SELECT * FROM orders
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT {page_size} OFFSET {offset}
            """,
            *params
        )
        
        return {
            "orders": [dict(o) for o in orders],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }

@app.put("/orders/{order_id}/status")
async def update_status(
    order_id: int,
    status_update: OrderStatusUpdate,
    background_tasks: BackgroundTasks
):
    """Update order status"""
    await update_order_status(order_id, status_update.status, status_update.notes)
    
    # Send notification
    background_tasks.add_task(send_order_notification, order_id, f"order_{status_update.status.value}")
    
    # Handle inventory for cancellations
    if status_update.status == OrderStatus.CANCELLED:
        background_tasks.add_task(update_inventory, order_id, "release")
    
    return {"message": "Order status updated", "status": status_update.status.value}

@app.post("/orders/{order_id}/fulfillments", response_model=Fulfillment)
async def create_fulfillment(
    order_id: int,
    fulfillment: FulfillmentCreate,
    background_tasks: BackgroundTasks
):
    """Create fulfillment for order"""
    async with db_pool.acquire() as conn:
        # Verify order exists
        order = await conn.fetchrow(
            "SELECT * FROM orders WHERE id = $1",
            order_id
        )
        
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        # Create fulfillment
        fulfillment_id = await conn.fetchval(
            """
            INSERT INTO fulfillments (
                order_id, items, status, tracking, warehouse_id, notes
            )
            VALUES ($1, $2, 'unfulfilled', $3, $4, $5)
            RETURNING id
            """,
            order_id,
            json.dumps(fulfillment.items),
            json.dumps(fulfillment.tracking.dict()) if fulfillment.tracking else None,
            fulfillment.warehouse_id,
            fulfillment.notes
        )
        
        # Update order fulfillment status
        await conn.execute(
            """
            UPDATE orders
            SET fulfillment_status = 'partially_fulfilled', updated_at = NOW()
            WHERE id = $1
            """,
            order_id
        )
        
        await log_order_event(order_id, "fulfillment_created", {
            "fulfillment_id": fulfillment_id,
            "items": fulfillment.items
        })
        
        # Send notification
        background_tasks.add_task(send_order_notification, order_id, "order_shipped")
        
        # Get created fulfillment
        created = await conn.fetchrow(
            "SELECT * FROM fulfillments WHERE id = $1",
            fulfillment_id
        )
        
        f_dict = dict(created)
        f_dict['items'] = json.loads(f_dict['items'])
        if f_dict['tracking']:
            f_dict['tracking'] = ShipmentTracking(**json.loads(f_dict['tracking']))
        
        return Fulfillment(**f_dict)

@app.get("/orders/{order_id}/history")
async def get_order_history(order_id: int):
    """Get order status history"""
    async with db_pool.acquire() as conn:
        history = await conn.fetch(
            """
            SELECT * FROM order_status_history
            WHERE order_id = $1
            ORDER BY created_at DESC
            """,
            order_id
        )
        
        return [dict(h) for h in history]

@app.get("/orders/{order_id}/events")
async def get_order_events(order_id: int):
    """Get order event log"""
    async with db_pool.acquire() as conn:
        events = await conn.fetch(
            """
            SELECT * FROM order_events
            WHERE order_id = $1
            ORDER BY created_at DESC
            """,
            order_id
        )
        
        return [dict(e) for e in events]

@app.get("/health")
async def health_check():
    """Health check"""
    return {
        "status": "healthy",
        "service": "order_management",
        "timestamp": datetime.utcnow().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8083)

