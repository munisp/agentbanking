"""
E-commerce Checkout Flow Service
Complete checkout workflow with payment integration
"""

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, EmailStr, validator
from typing import Optional, List, Dict
from datetime import datetime
from enum import Enum
import asyncpg
import httpx
import logging
import json

import os
# Configuration
app = FastAPI(title="E-commerce Checkout Service")
logger = logging.getLogger(__name__)

# Database connection pool
db_pool = None

# Models
class CheckoutStatus(str, Enum):
    CART = "cart"
    SHIPPING = "shipping"
    PAYMENT = "payment"
    CONFIRMED = "confirmed"
    FAILED = "failed"

class PaymentMethod(str, Enum):
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    PAYPAL = "paypal"
    STRIPE = "stripe"
    BANK_TRANSFER = "bank_transfer"
    MOBILE_MONEY = "mobile_money"

class ShippingMethod(str, Enum):
    STANDARD = "standard"
    EXPRESS = "express"
    OVERNIGHT = "overnight"
    PICKUP = "pickup"

class Address(BaseModel):
    first_name: str
    last_name: str
    address_line1: str
    address_line2: Optional[str] = None
    city: str
    state: str
    postal_code: str
    country: str
    phone: str

class CartItem(BaseModel):
    product_id: int
    variant_id: Optional[int] = None
    quantity: int
    price: float

class ShippingInfo(BaseModel):
    method: ShippingMethod
    address: Address
    estimated_delivery: Optional[str] = None

class PaymentInfo(BaseModel):
    method: PaymentMethod
    card_token: Optional[str] = None  # Tokenized card
    billing_address: Optional[Address] = None

class CheckoutCreate(BaseModel):
    customer_id: int
    items: List[CartItem]
    
    @validator('items')
    def validate_items(cls, v):
        if not v:
            raise ValueError('Cart cannot be empty')
        return v

class CheckoutUpdate(BaseModel):
    shipping_info: Optional[ShippingInfo] = None
    payment_info: Optional[PaymentInfo] = None
    coupon_code: Optional[str] = None

class CheckoutResponse(BaseModel):
    checkout_id: int
    status: CheckoutStatus
    customer_id: int
    items: List[Dict]
    subtotal: float
    shipping_cost: float
    tax: float
    discount: float
    total: float
    shipping_info: Optional[Dict] = None
    payment_info: Optional[Dict] = None
    created_at: datetime
    updated_at: datetime

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
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS checkouts (
                id SERIAL PRIMARY KEY,
                customer_id INTEGER NOT NULL,
                status VARCHAR(50) NOT NULL DEFAULT 'cart',
                items JSONB NOT NULL,
                subtotal DECIMAL(10,2) NOT NULL,
                shipping_cost DECIMAL(10,2) DEFAULT 0,
                tax DECIMAL(10,2) DEFAULT 0,
                discount DECIMAL(10,2) DEFAULT 0,
                total DECIMAL(10,2) NOT NULL,
                shipping_info JSONB,
                payment_info JSONB,
                order_id INTEGER,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS checkout_events (
                id SERIAL PRIMARY KEY,
                checkout_id INTEGER REFERENCES checkouts(id),
                event_type VARCHAR(50) NOT NULL,
                event_data JSONB,
                created_at TIMESTAMP DEFAULT NOW()
            )
        ''')

# Helper functions
async def calculate_subtotal(items: List[CartItem]) -> float:
    """Calculate subtotal from cart items"""
    subtotal = 0.0
    for item in items:
        subtotal += item.price * item.quantity
    return subtotal

async def calculate_shipping(method: ShippingMethod, subtotal: float) -> float:
    """Calculate shipping cost"""
    shipping_rates = {
        ShippingMethod.STANDARD: 5.99,
        ShippingMethod.EXPRESS: 12.99,
        ShippingMethod.OVERNIGHT: 24.99,
        ShippingMethod.PICKUP: 0.00
    }
    
    # Free shipping for orders over $50
    if subtotal >= 50:
        return 0.00
    
    return shipping_rates.get(method, 5.99)

async def calculate_tax(subtotal: float, state: str) -> float:
    """Calculate tax based on state"""
    # Simplified tax calculation
    tax_rates = {
        "CA": 0.0725,
        "NY": 0.08,
        "TX": 0.0625,
        "FL": 0.06
    }
    
    rate = tax_rates.get(state, 0.07)  # Default 7%
    return subtotal * rate

async def apply_coupon(code: str, subtotal: float) -> float:
    """Apply coupon code"""
    async with db_pool.acquire() as conn:
        coupon = await conn.fetchrow(
            """
            SELECT * FROM coupons
            WHERE code = $1 AND is_active = TRUE
            AND (expires_at IS NULL OR expires_at > NOW())
            """,
            code
        )
        
        if not coupon:
            return 0.0
        
        if coupon['type'] == 'percentage':
            return subtotal * (coupon['value'] / 100)
        elif coupon['type'] == 'fixed':
            return min(coupon['value'], subtotal)
    
    return 0.0

async def process_payment(payment_info: PaymentInfo, amount: float) -> Dict:
    """Process payment through payment gateway"""
    # Call payment service
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "http://localhost:8000/payments/process",
                json={
                    "method": payment_info.method.value,
                    "amount": amount,
                    "card_token": payment_info.card_token,
                    "currency": "USD"
                },
                timeout=30.0
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                raise HTTPException(status_code=400, detail="Payment failed")
        except httpx.RequestError as e:
            logger.error(f"Payment service error: {e}")
            raise HTTPException(status_code=503, detail="Payment service unavailable")

async def create_order(checkout_id: int) -> int:
    """Create order from checkout"""
    async with db_pool.acquire() as conn:
        checkout = await conn.fetchrow(
            "SELECT * FROM checkouts WHERE id = $1",
            checkout_id
        )
        
        if not checkout:
            raise HTTPException(status_code=404, detail="Checkout not found")
        
        # Create order
        order_id = await conn.fetchval(
            """
            INSERT INTO orders (
                customer_id, items, subtotal, shipping_cost,
                tax, discount, total, shipping_info, payment_info,
                status, created_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'pending', NOW())
            RETURNING id
            """,
            checkout['customer_id'],
            checkout['items'],
            checkout['subtotal'],
            checkout['shipping_cost'],
            checkout['tax'],
            checkout['discount'],
            checkout['total'],
            checkout['shipping_info'],
            checkout['payment_info']
        )
        
        # Update checkout with order_id
        await conn.execute(
            "UPDATE checkouts SET order_id = $1 WHERE id = $2",
            order_id, checkout_id
        )
        
        return order_id

async def log_checkout_event(checkout_id: int, event_type: str, event_data: Dict):
    """Log checkout event"""
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO checkout_events (checkout_id, event_type, event_data)
            VALUES ($1, $2, $3)
            """,
            checkout_id, event_type, json.dumps(event_data)
        )

async def send_confirmation_email(customer_id: int, order_id: int):
    """Send order confirmation email"""
    # Implement email sending via email service
    try:
        import requests
        # Get customer email from database
        customer = await db_pool.fetchrow("SELECT email FROM customers WHERE id = $1", customer_id)
        if customer:
            email_service_url = os.getenv('EMAIL_SERVICE_URL', 'http://localhost:8001')
            requests.post(f"{email_service_url}/api/v1/email/send", json={
                "to": customer['email'],
                "subject": f"Order Confirmation - #{order_id}",
                "body": f"Thank you for your order! Your order #{order_id} has been confirmed and is being processed."
            }, timeout=5)
    except Exception as e:
        logger.error(f"Failed to send confirmation email: {e}")
    logger.info(f"Sending confirmation email for order {order_id} to customer {customer_id}")

# API Endpoints

@app.on_event("startup")
async def startup():
    await init_db()

@app.on_event("shutdown")
async def shutdown():
    if db_pool:
        await db_pool.close()

@app.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(checkout: CheckoutCreate):
    """Create new checkout session"""
    # Calculate totals
    subtotal = await calculate_subtotal(checkout.items)
    
    async with db_pool.acquire() as conn:
        checkout_id = await conn.fetchval(
            """
            INSERT INTO checkouts (customer_id, items, subtotal, total, status)
            VALUES ($1, $2, $3, $4, 'cart')
            RETURNING id
            """,
            checkout.customer_id,
            json.dumps([item.dict() for item in checkout.items]),
            subtotal,
            subtotal
        )
        
        await log_checkout_event(checkout_id, "created", {
            "customer_id": checkout.customer_id,
            "item_count": len(checkout.items)
        })
        
        # Get created checkout
        checkout_record = await conn.fetchrow(
            "SELECT * FROM checkouts WHERE id = $1",
            checkout_id
        )
        
        return CheckoutResponse(
            checkout_id=checkout_record['id'],
            status=checkout_record['status'],
            customer_id=checkout_record['customer_id'],
            items=json.loads(checkout_record['items']),
            subtotal=float(checkout_record['subtotal']),
            shipping_cost=float(checkout_record['shipping_cost']),
            tax=float(checkout_record['tax']),
            discount=float(checkout_record['discount']),
            total=float(checkout_record['total']),
            shipping_info=checkout_record['shipping_info'],
            payment_info=checkout_record['payment_info'],
            created_at=checkout_record['created_at'],
            updated_at=checkout_record['updated_at']
        )

@app.get("/checkout/{checkout_id}", response_model=CheckoutResponse)
async def get_checkout(checkout_id: int):
    """Get checkout details"""
    async with db_pool.acquire() as conn:
        checkout = await conn.fetchrow(
            "SELECT * FROM checkouts WHERE id = $1",
            checkout_id
        )
        
        if not checkout:
            raise HTTPException(status_code=404, detail="Checkout not found")
        
        return CheckoutResponse(
            checkout_id=checkout['id'],
            status=checkout['status'],
            customer_id=checkout['customer_id'],
            items=json.loads(checkout['items']),
            subtotal=float(checkout['subtotal']),
            shipping_cost=float(checkout['shipping_cost']),
            tax=float(checkout['tax']),
            discount=float(checkout['discount']),
            total=float(checkout['total']),
            shipping_info=checkout['shipping_info'],
            payment_info=checkout['payment_info'],
            created_at=checkout['created_at'],
            updated_at=checkout['updated_at']
        )

@app.put("/checkout/{checkout_id}/shipping", response_model=CheckoutResponse)
async def update_shipping(checkout_id: int, shipping: ShippingInfo):
    """Update shipping information"""
    async with db_pool.acquire() as conn:
        checkout = await conn.fetchrow(
            "SELECT * FROM checkouts WHERE id = $1",
            checkout_id
        )
        
        if not checkout:
            raise HTTPException(status_code=404, detail="Checkout not found")
        
        # Calculate shipping cost
        shipping_cost = await calculate_shipping(
            shipping.method,
            float(checkout['subtotal'])
        )
        
        # Calculate tax
        tax = await calculate_tax(
            float(checkout['subtotal']),
            shipping.address.state
        )
        
        # Calculate new total
        total = float(checkout['subtotal']) + shipping_cost + tax - float(checkout['discount'])
        
        # Update checkout
        await conn.execute(
            """
            UPDATE checkouts
            SET shipping_info = $1, shipping_cost = $2, tax = $3,
                total = $4, status = 'shipping', updated_at = NOW()
            WHERE id = $5
            """,
            json.dumps(shipping.dict()),
            shipping_cost,
            tax,
            total,
            checkout_id
        )
        
        await log_checkout_event(checkout_id, "shipping_updated", {
            "method": shipping.method.value,
            "cost": shipping_cost
        })
        
        # Get updated checkout
        updated_checkout = await conn.fetchrow(
            "SELECT * FROM checkouts WHERE id = $1",
            checkout_id
        )
        
        return CheckoutResponse(
            checkout_id=updated_checkout['id'],
            status=updated_checkout['status'],
            customer_id=updated_checkout['customer_id'],
            items=json.loads(updated_checkout['items']),
            subtotal=float(updated_checkout['subtotal']),
            shipping_cost=float(updated_checkout['shipping_cost']),
            tax=float(updated_checkout['tax']),
            discount=float(updated_checkout['discount']),
            total=float(updated_checkout['total']),
            shipping_info=updated_checkout['shipping_info'],
            payment_info=updated_checkout['payment_info'],
            created_at=updated_checkout['created_at'],
            updated_at=updated_checkout['updated_at']
        )

@app.put("/checkout/{checkout_id}/coupon")
async def apply_coupon_code(checkout_id: int, coupon_code: str):
    """Apply coupon code"""
    async with db_pool.acquire() as conn:
        checkout = await conn.fetchrow(
            "SELECT * FROM checkouts WHERE id = $1",
            checkout_id
        )
        
        if not checkout:
            raise HTTPException(status_code=404, detail="Checkout not found")
        
        # Calculate discount
        discount = await apply_coupon(coupon_code, float(checkout['subtotal']))
        
        if discount == 0:
            raise HTTPException(status_code=400, detail="Invalid coupon code")
        
        # Calculate new total
        total = (float(checkout['subtotal']) + 
                float(checkout['shipping_cost']) + 
                float(checkout['tax']) - 
                discount)
        
        # Update checkout
        await conn.execute(
            """
            UPDATE checkouts
            SET discount = $1, total = $2, updated_at = NOW()
            WHERE id = $3
            """,
            discount, total, checkout_id
        )
        
        await log_checkout_event(checkout_id, "coupon_applied", {
            "code": coupon_code,
            "discount": discount
        })
        
        return {"message": "Coupon applied", "discount": discount}

@app.post("/checkout/{checkout_id}/payment")
async def process_checkout_payment(
    checkout_id: int,
    payment: PaymentInfo,
    background_tasks: BackgroundTasks
):
    """Process payment and complete checkout"""
    async with db_pool.acquire() as conn:
        checkout = await conn.fetchrow(
            "SELECT * FROM checkouts WHERE id = $1",
            checkout_id
        )
        
        if not checkout:
            raise HTTPException(status_code=404, detail="Checkout not found")
        
        if checkout['status'] == 'confirmed':
            raise HTTPException(status_code=400, detail="Checkout already completed")
        
        # Process payment
        try:
            payment_result = await process_payment(payment, float(checkout['total']))
            
            # Update checkout with payment info
            await conn.execute(
                """
                UPDATE checkouts
                SET payment_info = $1, status = 'payment', updated_at = NOW()
                WHERE id = $2
                """,
                json.dumps(payment.dict(exclude={'card_token'})),  # Don't store card token
                checkout_id
            )
            
            await log_checkout_event(checkout_id, "payment_processed", {
                "method": payment.method.value,
                "amount": float(checkout['total']),
                "transaction_id": payment_result.get('transaction_id')
            })
            
            # Create order
            order_id = await create_order(checkout_id)
            
            # Update checkout status
            await conn.execute(
                """
                UPDATE checkouts
                SET status = 'confirmed', updated_at = NOW()
                WHERE id = $1
                """,
                checkout_id
            )
            
            await log_checkout_event(checkout_id, "checkout_completed", {
                "order_id": order_id
            })
            
            # Send confirmation email in background
            background_tasks.add_task(
                send_confirmation_email,
                checkout['customer_id'],
                order_id
            )
            
            return {
                "message": "Checkout completed successfully",
                "order_id": order_id,
                "payment_result": payment_result
            }
            
        except Exception as e:
            # Update checkout status to failed
            await conn.execute(
                """
                UPDATE checkouts
                SET status = 'failed', updated_at = NOW()
                WHERE id = $1
                """,
                checkout_id
            )
            
            await log_checkout_event(checkout_id, "payment_failed", {
                "error": str(e)
            })
            
            raise HTTPException(status_code=400, detail=f"Payment failed: {str(e)}")

@app.get("/checkout/{checkout_id}/events")
async def get_checkout_events(checkout_id: int):
    """Get checkout event history"""
    async with db_pool.acquire() as conn:
        events = await conn.fetch(
            """
            SELECT * FROM checkout_events
            WHERE checkout_id = $1
            ORDER BY created_at DESC
            """,
            checkout_id
        )
        
        return [dict(event) for event in events]

@app.delete("/checkout/{checkout_id}")
async def cancel_checkout(checkout_id: int):
    """Cancel checkout"""
    async with db_pool.acquire() as conn:
        checkout = await conn.fetchrow(
            "SELECT * FROM checkouts WHERE id = $1",
            checkout_id
        )
        
        if not checkout:
            raise HTTPException(status_code=404, detail="Checkout not found")
        
        if checkout['status'] == 'confirmed':
            raise HTTPException(status_code=400, detail="Cannot cancel completed checkout")
        
        await conn.execute(
            "UPDATE checkouts SET status = 'cancelled', updated_at = NOW() WHERE id = $1",
            checkout_id
        )
        
        await log_checkout_event(checkout_id, "checkout_cancelled", {})
        
        return {"message": "Checkout cancelled"}

@app.get("/health")
async def health_check():
    """Health check"""
    return {
        "status": "healthy",
        "service": "checkout",
        "timestamp": datetime.utcnow().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081)

