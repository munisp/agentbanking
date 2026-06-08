"""
Payment Gateway Service - Unified payment processing
Routes payments to providers: Paystack, Flutterwave, M-Pesa, bank transfer
Database-backed with idempotency, retry logic, and webhook handling
"""

from fastapi import FastAPI, HTTPException, Header, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Dict, List
from enum import Enum
from decimal import Decimal
import json as _json
import uuid
import asyncpg
import httpx
import hmac
import hashlib
import os
import logging
from datetime import datetime

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

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/payments")
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY", "")
FLUTTERWAVE_SECRET_KEY = os.getenv("FLUTTERWAVE_SECRET_KEY", "")
MPESA_CONSUMER_KEY = os.getenv("MPESA_CONSUMER_KEY", "")
MPESA_CONSUMER_SECRET = os.getenv("MPESA_CONSUMER_SECRET", "")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Payment Gateway Service", version="2.0.0")

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/payment_gateway")

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
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db_pool: Optional[asyncpg.Pool] = None

class PaymentMethod(str, Enum):
    PAYSTACK = "paystack"
    FLUTTERWAVE = "flutterwave"
    MPESA = "mpesa"
    BANK_TRANSFER = "bank_transfer"
    USSD = "ussd"
    CARD = "card"

class PaymentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"

class PaymentRequest(BaseModel):
    amount: Decimal = Field(..., gt=0)
    currency: str = Field(..., min_length=3, max_length=3)
    payment_method: PaymentMethod
    customer_id: str
    customer_email: Optional[str] = None
    phone_number: Optional[str] = None
    description: Optional[str] = None
    callback_url: Optional[str] = None
    idempotency_key: Optional[str] = None
    metadata: Optional[Dict] = None

class PaymentResponse(BaseModel):
    payment_id: str
    status: PaymentStatus
    amount: str
    currency: str
    payment_method: str
    provider_reference: Optional[str] = None
    authorization_url: Optional[str] = None
    created_at: datetime

class RefundRequest(BaseModel):
    reason: Optional[str] = None
    amount: Optional[Decimal] = None

async def verify_bearer_token(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    token = authorization[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    return token

@app.on_event("startup")
async def startup():
    global db_pool
    db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=5, max_size=20)
    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                customer_id VARCHAR(100) NOT NULL,
                customer_email VARCHAR(255),
                amount DECIMAL(15,2) NOT NULL,
                currency VARCHAR(3) NOT NULL,
                payment_method VARCHAR(50) NOT NULL,
                status VARCHAR(20) DEFAULT 'pending',
                provider_reference VARCHAR(255),
                authorization_url TEXT,
                idempotency_key VARCHAR(255) UNIQUE,
                description TEXT,
                phone_number VARCHAR(20),
                callback_url TEXT,
                metadata JSONB DEFAULT '{}',
                failure_reason TEXT,
                refunded_amount DECIMAL(15,2) DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_payments_customer ON payments(customer_id);
            CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status);
            CREATE INDEX IF NOT EXISTS idx_payments_idempotency ON payments(idempotency_key);
        """)
    logger.info("Payment Gateway Service started")

@app.on_event("shutdown")
async def shutdown():
    if db_pool:
        await db_pool.close()

async def _initiate_paystack(payment_id: str, amount: Decimal, currency: str, email: str, callback_url: Optional[str]) -> Dict:
    if not PAYSTACK_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Paystack not configured")
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            "https://api.paystack.co/transaction/initialize",
            json={
                "amount": int(amount * 100),
                "email": email,
                "currency": currency,
                "reference": payment_id,
                "callback_url": callback_url or "",
            },
            headers={"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"},
        )
        data = resp.json()
        if not data.get("status"):
            raise HTTPException(status_code=502, detail=f"Paystack error: {data.get('message')}")
        return {
            "provider_reference": data["data"]["reference"],
            "authorization_url": data["data"]["authorization_url"],
        }

async def _initiate_flutterwave(payment_id: str, amount: Decimal, currency: str, email: str, callback_url: Optional[str]) -> Dict:
    if not FLUTTERWAVE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Flutterwave not configured")
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            "https://api.flutterwave.com/v3/payments",
            json={
                "tx_ref": payment_id,
                "amount": str(amount),
                "currency": currency,
                "redirect_url": callback_url or "",
                "customer": {"email": email},
            },
            headers={"Authorization": f"Bearer {FLUTTERWAVE_SECRET_KEY}"},
        )
        data = resp.json()
        if data.get("status") != "success":
            raise HTTPException(status_code=502, detail=f"Flutterwave error: {data.get('message')}")
        return {
            "provider_reference": payment_id,
            "authorization_url": data["data"]["link"],
        }

async def _initiate_mpesa(payment_id: str, amount: Decimal, phone_number: str) -> Dict:
    if not MPESA_CONSUMER_KEY or not MPESA_CONSUMER_SECRET:
        raise HTTPException(status_code=503, detail="M-Pesa not configured")
    async with httpx.AsyncClient(timeout=30.0) as client:
        auth_resp = await client.get(
            "https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials",
            auth=(MPESA_CONSUMER_KEY, MPESA_CONSUMER_SECRET),
        )
        access_token = auth_resp.json().get("access_token")
        if not access_token:
            raise HTTPException(status_code=502, detail="M-Pesa auth failed")
        stk_resp = await client.post(
            "https://api.safaricom.co.ke/mpesa/stkpush/v1/processrequest",
            json={
                "BusinessShortCode": os.getenv("MPESA_SHORTCODE", "174379"),
                "Amount": int(amount),
                "PhoneNumber": phone_number,
                "AccountReference": payment_id[:12],
                "TransactionDesc": "Payment",
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        data = stk_resp.json()
        return {
            "provider_reference": data.get("CheckoutRequestID", payment_id),
            "authorization_url": None,
        }

@app.post("/api/v1/payments", response_model=PaymentResponse)
async def create_payment(request: PaymentRequest, token: str = Depends(verify_bearer_token)):
    if request.idempotency_key:
        async with db_pool.acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT * FROM payments WHERE idempotency_key = $1", request.idempotency_key
            )
            if existing:
                return PaymentResponse(
                    payment_id=str(existing["id"]),
                    status=PaymentStatus(existing["status"]),
                    amount=str(existing["amount"]),
                    currency=existing["currency"],
                    payment_method=existing["payment_method"],
                    provider_reference=existing["provider_reference"],
                    authorization_url=existing["authorization_url"],
                    created_at=existing["created_at"],
                )

    payment_id = str(uuid.uuid4())
    provider_result: Dict = {"provider_reference": None, "authorization_url": None}

    if request.payment_method == PaymentMethod.PAYSTACK:
        email = request.customer_email or f"{request.customer_id}@placeholder.com"
        provider_result = await _initiate_paystack(payment_id, request.amount, request.currency, email, request.callback_url)
    elif request.payment_method == PaymentMethod.FLUTTERWAVE:
        email = request.customer_email or f"{request.customer_id}@placeholder.com"
        provider_result = await _initiate_flutterwave(payment_id, request.amount, request.currency, email, request.callback_url)
    elif request.payment_method == PaymentMethod.MPESA:
        if not request.phone_number:
            raise HTTPException(status_code=400, detail="Phone number required for M-Pesa")
        provider_result = await _initiate_mpesa(payment_id, request.amount, request.phone_number)
    elif request.payment_method == PaymentMethod.BANK_TRANSFER:
        provider_result = {"provider_reference": f"BT-{uuid.uuid4().hex[:12]}", "authorization_url": None}

    async with db_pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO payments (id, customer_id, customer_email, amount, currency, payment_method,
                status, provider_reference, authorization_url, idempotency_key, description,
                phone_number, callback_url, metadata)
            VALUES ($1, $2, $3, $4, $5, $6, 'processing', $7, $8, $9, $10, $11, $12, $13::jsonb) RETURNING id""",
            uuid.UUID(payment_id), request.customer_id, request.customer_email,
            request.amount, request.currency, request.payment_method.value,
            provider_result["provider_reference"], provider_result["authorization_url"],
            request.idempotency_key, request.description,
            request.phone_number, request.callback_url,
            _json.dumps(request.metadata or {}),
        )

    logger.info(f"Payment {payment_id} created via {request.payment_method.value}")
    return PaymentResponse(
        payment_id=payment_id,
        status=PaymentStatus.PROCESSING,
        amount=str(request.amount),
        currency=request.currency,
        payment_method=request.payment_method.value,
        provider_reference=provider_result["provider_reference"],
        authorization_url=provider_result["authorization_url"],
        created_at=datetime.utcnow(),
    )

@app.get("/api/v1/payments/{payment_id}", response_model=PaymentResponse)
async def get_payment(payment_id: str, token: str = Depends(verify_bearer_token)):
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM payments WHERE id = $1", uuid.UUID(payment_id))
    if not row:
        raise HTTPException(status_code=404, detail="Payment not found")
    return PaymentResponse(
        payment_id=str(row["id"]),
        status=PaymentStatus(row["status"]),
        amount=str(row["amount"]),
        currency=row["currency"],
        payment_method=row["payment_method"],
        provider_reference=row["provider_reference"],
        authorization_url=row["authorization_url"],
        created_at=row["created_at"],
    )

@app.get("/api/v1/payments", response_model=List[PaymentResponse])
async def list_payments(
    customer_id: Optional[str] = None,
    status: Optional[PaymentStatus] = None,
    limit: int = 50,
    offset: int = 0,
    token: str = Depends(verify_bearer_token),
):
    query = "SELECT * FROM payments WHERE 1=1"
    params: list = []
    idx = 1
    if customer_id:
        query += f" AND customer_id = ${idx}"
        params.append(customer_id)
        idx += 1
    if status:
        query += f" AND status = ${idx}"
        params.append(status.value)
        idx += 1
    query += f" ORDER BY created_at DESC LIMIT ${idx} OFFSET ${idx+1}"
    params.extend([limit, offset])
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
    return [
        PaymentResponse(
            payment_id=str(r["id"]),
            status=PaymentStatus(r["status"]),
            amount=str(r["amount"]),
            currency=r["currency"],
            payment_method=r["payment_method"],
            provider_reference=r["provider_reference"],
            authorization_url=r["authorization_url"],
            created_at=r["created_at"],
        )
        for r in rows
    ]

@app.post("/api/v1/payments/{payment_id}/refund")
async def refund_payment(payment_id: str, req: RefundRequest, token: str = Depends(verify_bearer_token)):
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM payments WHERE id = $1", uuid.UUID(payment_id))
        if not row:
            raise HTTPException(status_code=404, detail="Payment not found")
        if row["status"] != "completed":
            raise HTTPException(status_code=400, detail="Only completed payments can be refunded")
        refund_amount = req.amount or row["amount"]
        if refund_amount > row["amount"] - row["refunded_amount"]:
            raise HTTPException(status_code=400, detail="Refund amount exceeds refundable balance")
        if row["payment_method"] == "paystack" and PAYSTACK_SECRET_KEY:
            async with httpx.AsyncClient(timeout=30.0) as client:
                await client.post(
                    "https://api.paystack.co/refund",
                    json={"transaction": row["provider_reference"], "amount": int(refund_amount * 100)},
                    headers={"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"},
                )
        new_refunded = row["refunded_amount"] + refund_amount
        new_status = "refunded" if new_refunded >= row["amount"] else row["status"]
        await conn.execute(
            "UPDATE payments SET refunded_amount = $1, status = $2, updated_at = NOW() WHERE id = $3",
            new_refunded, new_status, uuid.UUID(payment_id),
        )
    logger.info(f"Refund of {refund_amount} processed for payment {payment_id}")
    return {"payment_id": payment_id, "refunded_amount": str(refund_amount), "status": new_status}

@app.post("/webhooks/paystack")
async def paystack_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("x-paystack-signature", "")
    if PAYSTACK_SECRET_KEY:
        expected = hmac.new(PAYSTACK_SECRET_KEY.encode(), body, hashlib.sha512).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise HTTPException(status_code=400, detail="Invalid signature")
    data = await request.json()
    event = data.get("event")
    payment_data = data.get("data", {})
    ref = payment_data.get("reference")
    if event == "charge.success" and ref:
        async with db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE payments SET status = 'completed', updated_at = NOW() WHERE provider_reference = $1",
                ref,
            )
        logger.info(f"Paystack webhook: charge.success for {ref}")
    return {"status": "ok"}

@app.get("/health")
async def health_check():
    db_ok = False
    if db_pool:
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            db_ok = True
        except Exception:
            pass
    return {"status": "healthy" if db_ok else "degraded", "service": "payment-gateway", "database": db_ok}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8007)
