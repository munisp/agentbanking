"""
Biller Integration Service
Utility bill payment integration for Remittance Platform

Features:
- Electricity (PHCN/prepaid meters: AEDC, IKEDC, EKEDC, BEDC, KEDCO, etc.)
- Cable TV (DSTV, GOtv, Startimes)
- Water bill payments
- Government and service bills
- Multi-provider support (Baxi primary, VTpass fallback)
- Retry with exponential backoff
- Agent commission tracking
- Transaction verification and requery
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import asyncpg
import httpx
import os
import logging
import uuid
import asyncio
from decimal import Decimal

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

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is required")

BAXI_API_KEY = os.getenv("BAXI_API_KEY", "")
BAXI_API_URL = os.getenv("BAXI_API_URL", "https://api.baxipay.com.ng/api/baxipay")
VTPASS_API_KEY = os.getenv("VTPASS_API_KEY", "")
VTPASS_SECRET_KEY = os.getenv("VTPASS_SECRET_KEY", "")
VTPASS_API_URL = os.getenv("VTPASS_API_URL", "https://vtpass.com/api")
COMMISSION_SERVICE_URL = os.getenv("COMMISSION_SERVICE_URL", "http://localhost:8010")

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Biller Integration Service", version="2.0.0")

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/biller_integration")

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
    allow_origins=[o.strip() for o in ALLOWED_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db_pool = None

class BillerCategory(str, Enum):
    ELECTRICITY_PREPAID = "electricity_prepaid"
    ELECTRICITY_POSTPAID = "electricity_postpaid"
    CABLE_TV = "cable_tv"
    WATER = "water"
    INTERNET = "internet"
    GOVERNMENT = "government"

class PaymentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESSFUL = "successful"
    FAILED = "failed"

BILLER_SERVICE_MAP = {
    "ikeja-electric-prepaid": {"baxi": "ikeja_electric_prepaid", "vtpass": "ikeja-electric"},
    "ikeja-electric-postpaid": {"baxi": "ikeja_electric_postpaid", "vtpass": "ikeja-electric-postpaid"},
    "eko-electric-prepaid": {"baxi": "eko_electric_prepaid", "vtpass": "eko-electric"},
    "eko-electric-postpaid": {"baxi": "eko_electric_postpaid", "vtpass": "eko-electric-postpaid"},
    "abuja-electric-prepaid": {"baxi": "abuja_electric_prepaid", "vtpass": "abuja-electric"},
    "abuja-electric-postpaid": {"baxi": "abuja_electric_postpaid", "vtpass": "abuja-electric-postpaid"},
    "kano-electric-prepaid": {"baxi": "kano_electric_prepaid", "vtpass": "kano-electric"},
    "ph-electric-prepaid": {"baxi": "portharcourt_electric_prepaid", "vtpass": "portharcourt-electric"},
    "benin-electric-prepaid": {"baxi": "benin_electric_prepaid", "vtpass": "benin-electric"},
    "jos-electric-prepaid": {"baxi": "jos_electric_prepaid", "vtpass": "jos-electric"},
    "kaduna-electric-prepaid": {"baxi": "kaduna_electric_prepaid", "vtpass": "kaduna-electric"},
    "enugu-electric-prepaid": {"baxi": "enugu_electric_prepaid", "vtpass": "enugu-electric"},
    "ibadan-electric-prepaid": {"baxi": "ibadan_electric_prepaid", "vtpass": "ibadan-electric"},
    "dstv": {"baxi": "dstv", "vtpass": "dstv"},
    "gotv": {"baxi": "gotv", "vtpass": "gotv"},
    "startimes": {"baxi": "startimes", "vtpass": "startimes"},
    "showmax": {"baxi": "showmax", "vtpass": "showmax"},
    "waec": {"baxi": "waec", "vtpass": "waec"},
    "jamb": {"baxi": "jamb", "vtpass": "jamb"},
}

COMMISSION_RATES = {
    BillerCategory.ELECTRICITY_PREPAID: Decimal("0.005"),
    BillerCategory.ELECTRICITY_POSTPAID: Decimal("0.005"),
    BillerCategory.CABLE_TV: Decimal("0.02"),
    BillerCategory.WATER: Decimal("0.005"),
    BillerCategory.INTERNET: Decimal("0.015"),
    BillerCategory.GOVERNMENT: Decimal("0.01"),
}

class BillerPayment(BaseModel):
    customer_id: str = Field(..., min_length=1, description="Meter/smartcard/account number")
    biller_code: str = Field(..., min_length=1, description="Biller service code")
    category: BillerCategory
    amount: Decimal = Field(..., gt=0)
    customer_phone: str = Field(..., min_length=11, max_length=14)
    customer_email: Optional[str] = None
    agent_id: Optional[str] = None
    variation_code: Optional[str] = None
    request_id: Optional[str] = None

class PaymentResponse(BaseModel):
    transaction_id: str
    transaction_ref: str
    status: str
    amount: str
    customer_id: str
    biller_code: str
    category: str
    commission: Optional[str] = None
    token: Optional[str] = None
    provider_reference: Optional[str] = None
    customer_name: Optional[str] = None
    created_at: datetime

class BillerInfo(BaseModel):
    code: str
    name: str
    category: str

class VariationOption(BaseModel):
    code: str
    name: str
    amount: Decimal
    fixed_price: bool

@app.on_event("startup")
async def startup():
    global db_pool
    db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=5, max_size=20)
    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS biller_payments (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                request_id VARCHAR(50) UNIQUE,
                transaction_ref VARCHAR(100) UNIQUE NOT NULL,
                customer_id VARCHAR(100) NOT NULL,
                biller_code VARCHAR(50) NOT NULL,
                category VARCHAR(30) NOT NULL,
                amount DECIMAL(15,2) NOT NULL,
                commission DECIMAL(10,2) DEFAULT 0,
                agent_id VARCHAR(50),
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                customer_phone VARCHAR(20) NOT NULL,
                customer_email VARCHAR(100),
                customer_name VARCHAR(200),
                token TEXT,
                provider VARCHAR(20),
                provider_reference VARCHAR(100),
                error_message TEXT,
                retry_count INTEGER DEFAULT 0,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                completed_at TIMESTAMP,
                metadata JSONB DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_bp_status ON biller_payments(status);
            CREATE INDEX IF NOT EXISTS idx_bp_customer ON biller_payments(customer_id);
            CREATE INDEX IF NOT EXISTS idx_bp_agent ON biller_payments(agent_id);
            CREATE INDEX IF NOT EXISTS idx_bp_created ON biller_payments(created_at);
        """)
    logger.info("Biller Integration Service started")

@app.on_event("shutdown")
async def shutdown():
    if db_pool:
        await db_pool.close()

async def _call_baxi_api(endpoint: str, payload: dict, max_retries: int = 3) -> dict:
    headers = {"x-api-key": BAXI_API_KEY, "Content-Type": "application/json"}
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{BAXI_API_URL}/{endpoint}",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                if data.get("status") == "success":
                    return data
                if data.get("code") in ("EXC00103", "EXC00114"):
                    logger.warning(f"Baxi retryable error attempt {attempt + 1}: {data}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** attempt)
                        continue
                return data
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            logger.error(f"Baxi connection error attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
                continue
            raise
        except httpx.HTTPStatusError as e:
            logger.error(f"Baxi HTTP error attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
                continue
            raise
    raise HTTPException(status_code=502, detail="Baxi API unavailable after retries")

async def _call_vtpass_api(endpoint: str, payload: dict, max_retries: int = 3) -> dict:
    headers = {
        "api-key": VTPASS_API_KEY,
        "secret-key": VTPASS_SECRET_KEY,
        "Content-Type": "application/json",
    }
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{VTPASS_API_URL}/{endpoint}",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                if data.get("code") == "000" or data.get("response_description") == "TRANSACTION SUCCESSFUL":
                    return data
                if data.get("code") in ("016", "099"):
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** attempt)
                        continue
                return data
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            logger.error(f"VTpass connection error attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
                continue
            raise
        except httpx.HTTPStatusError as e:
            logger.error(f"VTpass HTTP error attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
                continue
            raise
    raise HTTPException(status_code=502, detail="VTpass API unavailable after retries")

async def _verify_via_baxi(customer_id: str, biller_code: str) -> Dict[str, Any]:
    service_type = BILLER_SERVICE_MAP.get(biller_code, {}).get("baxi", biller_code)
    result = await _call_baxi_api("superagent/transaction/verify", {
        "service_type": service_type,
        "account_number": customer_id,
    })
    if result.get("status") == "success":
        return {
            "provider": "baxi",
            "customer_name": result.get("data", {}).get("user", {}).get("name", ""),
            "address": result.get("data", {}).get("user", {}).get("address", ""),
            "raw": result.get("data", {}),
        }
    return {}

async def _verify_via_vtpass(customer_id: str, biller_code: str) -> Dict[str, Any]:
    service_id = BILLER_SERVICE_MAP.get(biller_code, {}).get("vtpass", biller_code)
    result = await _call_vtpass_api("merchant-verify", {
        "serviceID": service_id,
        "billersCode": customer_id,
    })
    content = result.get("content", {})
    if content.get("Customer_Name") or content.get("Customer Name"):
        return {
            "provider": "vtpass",
            "customer_name": content.get("Customer_Name") or content.get("Customer Name", ""),
            "address": content.get("Address", ""),
            "raw": content,
        }
    return {}

async def _pay_via_baxi(payment: BillerPayment, transaction_ref: str) -> Dict[str, Any]:
    service_type = BILLER_SERVICE_MAP.get(payment.biller_code, {}).get("baxi", payment.biller_code)
    payload = {
        "service_type": service_type,
        "account_number": payment.customer_id,
        "amount": float(payment.amount),
        "phone": payment.customer_phone,
        "agentReference": transaction_ref,
    }
    if payment.variation_code:
        payload["plan"] = payment.variation_code
    result = await _call_baxi_api("superagent/transaction/process", payload)
    if result.get("status") == "success":
        return {
            "provider": "baxi",
            "status": "successful",
            "token": result.get("data", {}).get("token") or result.get("data", {}).get("pins", [{}])[0].get("pin", ""),
            "provider_reference": result.get("data", {}).get("transactionReference", ""),
        }
    return {
        "provider": "baxi",
        "status": "failed",
        "error": result.get("message", "Payment failed via Baxi"),
    }

async def _pay_via_vtpass(payment: BillerPayment, transaction_ref: str) -> Dict[str, Any]:
    service_id = BILLER_SERVICE_MAP.get(payment.biller_code, {}).get("vtpass", payment.biller_code)
    payload = {
        "request_id": transaction_ref,
        "serviceID": service_id,
        "billersCode": payment.customer_id,
        "amount": int(payment.amount),
        "phone": payment.customer_phone,
    }
    if payment.variation_code:
        payload["variation_code"] = payment.variation_code
    result = await _call_vtpass_api("pay", payload)
    code = result.get("code")
    if code == "000" or result.get("response_description") == "TRANSACTION SUCCESSFUL":
        content = result.get("content", {})
        txn = content.get("transactions", {})
        return {
            "provider": "vtpass",
            "status": "successful",
            "token": txn.get("product_name", "") or content.get("token", ""),
            "provider_reference": txn.get("transactionId") or result.get("requestId", ""),
        }
    return {
        "provider": "vtpass",
        "status": "failed",
        "error": result.get("response_description", "Payment failed via VTpass"),
    }

@app.post("/verify")
async def verify_customer_endpoint(customer_id: str, biller_code: str):
    if BAXI_API_KEY:
        try:
            result = await _verify_via_baxi(customer_id, biller_code)
            if result:
                return result
        except Exception as e:
            logger.warning(f"Baxi verification failed, trying VTpass: {e}")

    if VTPASS_API_KEY:
        try:
            result = await _verify_via_vtpass(customer_id, biller_code)
            if result:
                return result
        except Exception as e:
            logger.warning(f"VTpass verification also failed: {e}")

    raise HTTPException(status_code=400, detail="Customer verification failed with all providers")

@app.post("/payments", response_model=PaymentResponse)
async def create_payment(payment: BillerPayment):
    request_id = payment.request_id or str(uuid.uuid4())
    transaction_ref = f"BILL{uuid.uuid4().hex[:12].upper()}"

    async with db_pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT * FROM biller_payments WHERE request_id = $1", request_id
        )
        if existing:
            return PaymentResponse(
                transaction_id=str(existing["id"]),
                transaction_ref=existing["transaction_ref"],
                status=existing["status"],
                amount=str(existing["amount"]),
                customer_id=existing["customer_id"],
                biller_code=existing["biller_code"],
                category=existing["category"],
                commission=str(existing["commission"]) if existing["commission"] else None,
                token=existing["token"],
                provider_reference=existing["provider_reference"],
                customer_name=existing["customer_name"],
                created_at=existing["created_at"],
            )

        row = await conn.fetchrow(
            """
            INSERT INTO biller_payments (
                request_id, transaction_ref, customer_id, biller_code, category,
                amount, agent_id, customer_phone, customer_email, status
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'processing')
            RETURNING *
            """,
            request_id, transaction_ref, payment.customer_id, payment.biller_code,
            payment.category.value, payment.amount, payment.agent_id,
            payment.customer_phone, payment.customer_email,
        )
        tx_id = row["id"]

        pay_result = None
        providers_tried = []

        if BAXI_API_KEY:
            try:
                pay_result = await _pay_via_baxi(payment, transaction_ref)
                providers_tried.append("baxi")
            except Exception as e:
                logger.warning(f"Baxi payment failed: {e}")
                providers_tried.append("baxi(error)")

        if (not pay_result or pay_result.get("status") != "successful") and VTPASS_API_KEY:
            try:
                pay_result = await _pay_via_vtpass(payment, transaction_ref)
                providers_tried.append("vtpass")
            except Exception as e:
                logger.warning(f"VTpass payment failed: {e}")
                providers_tried.append("vtpass(error)")

        if not pay_result:
            await conn.execute(
                "UPDATE biller_payments SET status = 'failed', error_message = $1, updated_at = NOW() WHERE id = $2",
                "No payment provider available", tx_id,
            )
            raise HTTPException(status_code=502, detail="No payment provider available")

        status = pay_result.get("status", "failed")
        token = pay_result.get("token")
        provider_ref = pay_result.get("provider_reference")
        provider = pay_result.get("provider")
        error_msg = pay_result.get("error") if status != "successful" else None

        commission = Decimal("0")
        if status == "successful" and payment.agent_id:
            rate = COMMISSION_RATES.get(payment.category, Decimal("0.005"))
            commission = (payment.amount * rate).quantize(Decimal("0.01"))

        await conn.execute(
            """
            UPDATE biller_payments
            SET status = $1, token = $2, provider = $3, provider_reference = $4,
                error_message = $5, commission = $6, updated_at = NOW(),
                completed_at = CASE WHEN $1 = 'successful' THEN NOW() ELSE NULL END
            WHERE id = $7
            """,
            status, token, provider, provider_ref, error_msg, commission, tx_id,
        )

        if status == "successful" and payment.agent_id and commission > 0:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    await client.post(
                        f"{COMMISSION_SERVICE_URL}/api/v1/commissions",
                        json={
                            "agent_id": payment.agent_id,
                            "transaction_id": str(tx_id),
                            "transaction_type": f"bills_{payment.category.value}",
                            "amount": float(payment.amount),
                            "commission_amount": float(commission),
                        },
                    )
            except Exception as ce:
                logger.error(f"Failed to record commission: {ce}")

        if status != "successful":
            raise HTTPException(
                status_code=400,
                detail=error_msg or "Payment processing failed",
            )

        return PaymentResponse(
            transaction_id=str(tx_id),
            transaction_ref=transaction_ref,
            status=status,
            amount=str(payment.amount),
            customer_id=payment.customer_id,
            biller_code=payment.biller_code,
            category=payment.category.value,
            commission=str(commission) if commission > 0 else None,
            token=token,
            provider_reference=provider_ref,
            created_at=row["created_at"],
        )

@app.get("/payments/{transaction_ref}")
async def get_payment(transaction_ref: str):
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM biller_payments WHERE transaction_ref = $1 OR id::text = $1 OR request_id = $1",
            transaction_ref,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Payment not found")
        return PaymentResponse(
            transaction_id=str(row["id"]),
            transaction_ref=row["transaction_ref"],
            status=row["status"],
            amount=str(row["amount"]),
            customer_id=row["customer_id"],
            biller_code=row["biller_code"],
            category=row["category"],
            commission=str(row["commission"]) if row["commission"] else None,
            token=row["token"],
            provider_reference=row["provider_reference"],
            customer_name=row["customer_name"],
            created_at=row["created_at"],
        )

@app.get("/billers", response_model=List[BillerInfo])
async def list_billers(category: Optional[BillerCategory] = None):
    billers = []
    category_map = {
        "ikeja-electric-prepaid": ("Ikeja Electric Prepaid", BillerCategory.ELECTRICITY_PREPAID),
        "ikeja-electric-postpaid": ("Ikeja Electric Postpaid", BillerCategory.ELECTRICITY_POSTPAID),
        "eko-electric-prepaid": ("Eko Electric Prepaid", BillerCategory.ELECTRICITY_PREPAID),
        "eko-electric-postpaid": ("Eko Electric Postpaid", BillerCategory.ELECTRICITY_POSTPAID),
        "abuja-electric-prepaid": ("Abuja Electric Prepaid", BillerCategory.ELECTRICITY_PREPAID),
        "abuja-electric-postpaid": ("Abuja Electric Postpaid", BillerCategory.ELECTRICITY_POSTPAID),
        "kano-electric-prepaid": ("Kano Electric Prepaid", BillerCategory.ELECTRICITY_PREPAID),
        "ph-electric-prepaid": ("Port Harcourt Electric Prepaid", BillerCategory.ELECTRICITY_PREPAID),
        "benin-electric-prepaid": ("Benin Electric Prepaid", BillerCategory.ELECTRICITY_PREPAID),
        "jos-electric-prepaid": ("Jos Electric Prepaid", BillerCategory.ELECTRICITY_PREPAID),
        "kaduna-electric-prepaid": ("Kaduna Electric Prepaid", BillerCategory.ELECTRICITY_PREPAID),
        "enugu-electric-prepaid": ("Enugu Electric Prepaid", BillerCategory.ELECTRICITY_PREPAID),
        "ibadan-electric-prepaid": ("Ibadan Electric Prepaid", BillerCategory.ELECTRICITY_PREPAID),
        "dstv": ("DSTV", BillerCategory.CABLE_TV),
        "gotv": ("GOtv", BillerCategory.CABLE_TV),
        "startimes": ("StarTimes", BillerCategory.CABLE_TV),
        "showmax": ("Showmax", BillerCategory.CABLE_TV),
        "waec": ("WAEC Result Checker", BillerCategory.GOVERNMENT),
        "jamb": ("JAMB", BillerCategory.GOVERNMENT),
    }
    for code, (name, cat) in category_map.items():
        if category and cat != category:
            continue
        billers.append(BillerInfo(code=code, name=name, category=cat.value))
    return billers

@app.get("/billers/{biller_code}/variations", response_model=List[VariationOption])
async def get_biller_variations(biller_code: str):
    service_id = BILLER_SERVICE_MAP.get(biller_code, {}).get("vtpass", biller_code)
    if VTPASS_API_KEY:
        try:
            result = await _call_vtpass_api("service-variations", {"serviceID": service_id})
            variations = result.get("content", {}).get("varations", [])
            return [
                VariationOption(
                    code=v.get("variation_code", ""),
                    name=v.get("name", ""),
                    amount=Decimal(str(v.get("variation_amount", 0))),
                    fixed_price=v.get("fixedPrice", "No") == "Yes",
                )
                for v in variations
            ]
        except Exception as e:
            logger.error(f"Failed to fetch variations: {e}")
    raise HTTPException(status_code=502, detail="Failed to fetch biller variations")

@app.get("/transactions")
async def list_transactions(
    agent_id: Optional[str] = None,
    status: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
):
    async with db_pool.acquire() as conn:
        query = "SELECT * FROM biller_payments WHERE 1=1"
        params: list = []
        idx = 1
        if agent_id:
            query += f" AND agent_id = ${idx}"
            params.append(agent_id)
            idx += 1
        if status:
            query += f" AND status = ${idx}"
            params.append(status)
            idx += 1
        if category:
            query += f" AND category = ${idx}"
            params.append(category)
            idx += 1
        query += f" ORDER BY created_at DESC LIMIT ${idx} OFFSET ${idx + 1}"
        params.extend([limit, offset])
        rows = await conn.fetch(query, *params)
        return [
            {
                "transaction_id": str(r["id"]),
                "transaction_ref": r["transaction_ref"],
                "customer_id": r["customer_id"],
                "biller_code": r["biller_code"],
                "category": r["category"],
                "amount": str(r["amount"]),
                "commission": str(r["commission"]) if r["commission"] else None,
                "status": r["status"],
                "token": r["token"],
                "provider": r["provider"],
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        ]

@app.get("/health")
async def health_check():
    healthy = True
    details = {"service": "biller-integration", "database": "unknown"}
    try:
        async with db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        details["database"] = "connected"
    except Exception:
        details["database"] = "disconnected"
        healthy = False
    details["baxi"] = "configured" if BAXI_API_KEY else "not_configured"
    details["vtpass"] = "configured" if VTPASS_API_KEY else "not_configured"
    details["status"] = "healthy" if healthy else "degraded"
    return details

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8104)
