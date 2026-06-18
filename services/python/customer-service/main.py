"""
Customer Service - Customer lifecycle management
Database-backed CRUD, KYC status tracking, preferences, and risk profiling
"""

from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum
import asyncpg
import uuid
import os
import logging

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


DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/customers")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Customer Service", version="2.0.0")

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/customer_service")

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


class KYCLevel(str, Enum):
    NONE = "none"
    BASIC = "basic"
    ENHANCED = "enhanced"
    FULL = "full"


class CustomerStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CLOSED = "closed"
    PENDING_VERIFICATION = "pending_verification"


class CreateCustomerRequest(BaseModel):
    email: str
    phone_number: str
    first_name: str
    last_name: str
    country_code: str = Field(default="NG", min_length=2, max_length=2)
    preferred_currency: str = Field(default="NGN", min_length=3, max_length=3)


class UpdateCustomerRequest(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None
    preferred_currency: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None


class CustomerResponse(BaseModel):
    id: str
    email: str
    phone_number: str
    first_name: str
    last_name: str
    country_code: str
    preferred_currency: str
    kyc_level: KYCLevel
    status: CustomerStatus
    created_at: datetime
    updated_at: datetime


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
            CREATE TABLE IF NOT EXISTS customers (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                email VARCHAR(255) UNIQUE NOT NULL,
                phone_number VARCHAR(20) NOT NULL,
                first_name VARCHAR(100) NOT NULL,
                last_name VARCHAR(100) NOT NULL,
                country_code VARCHAR(2) DEFAULT 'NG',
                preferred_currency VARCHAR(3) DEFAULT 'NGN',
                kyc_level VARCHAR(20) DEFAULT 'none',
                status VARCHAR(30) DEFAULT 'pending_verification',
                address_line1 VARCHAR(255),
                address_line2 VARCHAR(255),
                city VARCHAR(100),
                state VARCHAR(100),
                postal_code VARCHAR(20),
                risk_score INT DEFAULT 0,
                total_transactions INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_customers_email ON customers(email);
            CREATE INDEX IF NOT EXISTS idx_customers_phone ON customers(phone_number);
            CREATE INDEX IF NOT EXISTS idx_customers_status ON customers(status);
        """)
    logger.info("Customer Service started")


@app.on_event("shutdown")
async def shutdown():
    if db_pool:
        await db_pool.close()


@app.post("/api/v1/customers", response_model=CustomerResponse, status_code=201)
async def create_customer(req: CreateCustomerRequest, token: str = Depends(verify_bearer_token)):
    async with db_pool.acquire() as conn:
        existing = await conn.fetchrow("SELECT id FROM customers WHERE email = $1", req.email)
        if existing:
            raise HTTPException(status_code=409, detail="Customer with this email already exists")
        row = await conn.fetchrow(
            """INSERT INTO customers (email, phone_number, first_name, last_name, country_code, preferred_currency)
            VALUES ($1, $2, $3, $4, $5, $6) RETURNING *""",
            req.email, req.phone_number, req.first_name, req.last_name,
            req.country_code, req.preferred_currency,
        )
    logger.info(f"Customer created: {row['id']}")
    return _row_to_response(row)


@app.get("/api/v1/customers/{customer_id}", response_model=CustomerResponse)
async def get_customer(customer_id: str, token: str = Depends(verify_bearer_token)):
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM customers WHERE id = $1", uuid.UUID(customer_id))
    if not row:
        raise HTTPException(status_code=404, detail="Customer not found")
    return _row_to_response(row)


@app.get("/api/v1/customers", response_model=List[CustomerResponse])
async def list_customers(
    status: Optional[CustomerStatus] = None,
    kyc_level: Optional[KYCLevel] = None,
    limit: int = 50,
    offset: int = 0,
    token: str = Depends(verify_bearer_token),
):
    query = "SELECT * FROM customers WHERE 1=1"
    params: list = []
    idx = 1
    if status:
        query += f" AND status = ${idx}"
        params.append(status.value)
        idx += 1
    if kyc_level:
        query += f" AND kyc_level = ${idx}"
        params.append(kyc_level.value)
        idx += 1
    query += f" ORDER BY created_at DESC LIMIT ${idx} OFFSET ${idx+1}"
    params.extend([limit, offset])
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
    return [_row_to_response(r) for r in rows]


@app.put("/api/v1/customers/{customer_id}", response_model=CustomerResponse)
async def update_customer(customer_id: str, req: UpdateCustomerRequest, token: str = Depends(verify_bearer_token)):
    updates = {k: v for k, v in req.dict().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    set_clauses = []
    params: list = []
    idx = 1
    for key, val in updates.items():
        set_clauses.append(f"{key} = ${idx}")
        params.append(val)
        idx += 1
    set_clauses.append("updated_at = NOW()")
    params.append(uuid.UUID(customer_id))
    query = f"UPDATE customers SET {', '.join(set_clauses)} WHERE id = ${idx} RETURNING *"
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(query, *params)
    if not row:
        raise HTTPException(status_code=404, detail="Customer not found")
    return _row_to_response(row)


@app.patch("/api/v1/customers/{customer_id}/kyc-level")
async def update_kyc_level(customer_id: str, kyc_level: KYCLevel, token: str = Depends(verify_bearer_token)):
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "UPDATE customers SET kyc_level = $1, status = 'active', updated_at = NOW() WHERE id = $2 RETURNING id, kyc_level, status",
            kyc_level.value, uuid.UUID(customer_id),
        )
    if not row:
        raise HTTPException(status_code=404, detail="Customer not found")
    return {"id": str(row["id"]), "kyc_level": row["kyc_level"], "status": row["status"]}


@app.patch("/api/v1/customers/{customer_id}/suspend")
async def suspend_customer(customer_id: str, token: str = Depends(verify_bearer_token)):
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "UPDATE customers SET status = 'suspended', updated_at = NOW() WHERE id = $1 RETURNING id, status",
            uuid.UUID(customer_id),
        )
    if not row:
        raise HTTPException(status_code=404, detail="Customer not found")
    logger.info(f"Customer {customer_id} suspended")
    return {"id": str(row["id"]), "status": row["status"]}


@app.get("/api/v1/customers/search")
async def search_customers(q: str, token: str = Depends(verify_bearer_token)):
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT * FROM customers
            WHERE email ILIKE $1 OR phone_number ILIKE $1
            OR first_name ILIKE $1 OR last_name ILIKE $1
            LIMIT 20""",
            f"%{q}%",
        )
    return [_row_to_response(r) for r in rows]


def _row_to_response(row) -> CustomerResponse:
    return CustomerResponse(
        id=str(row["id"]),
        email=row["email"],
        phone_number=row["phone_number"],
        first_name=row["first_name"],
        last_name=row["last_name"],
        country_code=row["country_code"],
        preferred_currency=row["preferred_currency"],
        kyc_level=KYCLevel(row["kyc_level"]),
        status=CustomerStatus(row["status"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


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
    return {"status": "healthy" if db_ok else "degraded", "service": "customer-service", "database": db_ok}


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port)
