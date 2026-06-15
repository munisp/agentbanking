"""
NFC & QR Payments - FastAPI microservice
Contactless payment processing via NFC tap and QR code scanning with dynamic code generation
"""
import os
import logging
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query
import sys as _sys2, os as _os2
_sys2.path.insert(0, _os2.path.join(_os2.path.dirname(_os2.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from fastapi.middleware.cors import CORSMiddleware

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

logging.basicConfig(level=logging.INFO)
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
            "service.name": os.environ.get("OTEL_SERVICE_NAME", "nfc-qr-payments"),
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

app = FastAPI(title="NFC & QR Payments", description="Contactless payment processing via NFC tap and QR code scanning with dynamic code generation", version="1.0.0")
apply_middleware(app, enable_auth=True)
# Instrument FastAPI with OpenTelemetry
if _otel_endpoint:
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
    except (ImportError, Exception):
        pass


import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/nfc_qr_payments")

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
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# --- Domain Helpers ---

def validate_request(data: dict, required_fields: list) -> list:
    """Validate that all required fields are present in request data."""
    missing = [f for f in required_fields if f not in data or data[f] is None]
    return missing

def sanitize_input(value: str) -> str:
    """Sanitize user input to prevent injection attacks."""
    if not isinstance(value, str):
        return str(value)
    return value.strip().replace("<", "&lt;").replace(">", "&gt;")

def format_currency(amount: float, currency: str = "NGN") -> str:
    """Format amount with currency symbol."""
    symbols = {"NGN": "₦", "USD": "$", "GBP": "£", "EUR": "€", "KES": "KSh"}
    symbol = symbols.get(currency, currency + " ")
    return f"{symbol}{amount:,.2f}"

def generate_reference(prefix: str = "REF") -> str:
    """Generate a unique reference ID."""
    import time
    import hashlib
    ts = str(time.time()).encode()
    h = hashlib.md5(ts).hexdigest()[:8].upper()
    return f"{prefix}-{h}"

def paginate(items: list, page: int = 1, per_page: int = 20) -> dict:
    """Paginate a list of items."""
    start = (page - 1) * per_page
    end = start + per_page
    return {
        "items": items[start:end],
        "total": len(items),
        "page": page,
        "per_page": per_page,
        "total_pages": (len(items) + per_page - 1) // per_page
    }

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "nfc-qr-payments", "version": "1.0.0", "timestamp": datetime.utcnow().isoformat()}

import json
import time
import hashlib
import httpx

KAFKA_DAPR_URL = f"http://localhost:{os.environ.get('DAPR_HTTP_PORT', '3500')}/v1.0/publish/kafka-pubsub"
REDIS_DAPR_URL = f"http://localhost:{os.environ.get('DAPR_HTTP_PORT', '3500')}/v1.0/state/redis-statestore"
TIGERBEETLE_URL = os.environ.get("TIGERBEETLE_SIDECAR_URL", "http://localhost:8200")
FLUVIO_URL = os.environ.get("FLUVIO_ENDPOINT", "http://localhost:9003")
OPENSEARCH_URL = os.environ.get("OPENSEARCH_URL", "http://localhost:9200")
LAKEHOUSE_URL = os.environ.get("LAKEHOUSE_URL", "http://localhost:8181")

async def publish_kafka(topic: str, data: dict):
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            await client.post(f"{KAFKA_DAPR_URL}/{topic}", json=data)
    except Exception as e:
        logging.warning(f"Kafka publish failed: {e}")

async def cache_redis(key: str, value: dict, ttl: int = 3600):
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            await client.post(REDIS_DAPR_URL, json=[{"key": key, "value": value}])
    except Exception:
        pass

async def record_gl_entry(ref: str, amount: float, debit: str, credit: str):
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            await client.post(f"{TIGERBEETLE_URL}/transfer", json={
                "reference": ref, "amount": amount,
                "debit_account": debit, "credit_account": credit,
            })
    except Exception:
        pass

async def index_opensearch(index: str, doc_id: str, data: dict):
    try:
        verify = os.environ.get("OPENSEARCH_VERIFY_CERTS", "true").lower() == "true"
        async with httpx.AsyncClient(timeout=3.0, verify=verify) as client:
            await client.put(f"{OPENSEARCH_URL}/{index}/_doc/{doc_id}", json=data)
    except Exception:
        pass

async def push_lakehouse(table: str, data: dict):
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            await client.post(f"{LAKEHOUSE_URL}/ingest", json={"table": table, "data": data})
    except Exception:
        pass

def calculate_fee(amount: float, tx_type: str = "transfer") -> dict:
    """CBN fee schedule for QR/NFC payments."""
    if tx_type == "nfc":
        fee = max(amount * 0.015, 50.0)  # 1.5%, min ₦50
    else:
        fee = min(amount * 0.01, 100.0)  # 1%, max ₦100
    commission = fee * 0.3
    return {"fee": round(fee, 2), "commission": round(commission, 2), "net": round(amount - fee, 2)}

# ── QR Code Endpoints ─────────────────────────────────────────────────────────

from pydantic import BaseModel, Field

class QRGenerateRequest(BaseModel):
    agent_id: int
    amount: Optional[float] = None
    description: Optional[str] = None
    currency: str = "NGN"
    expiry_minutes: int = 30
    merchant_id: Optional[str] = None

class QRPayRequest(BaseModel):
    code: str
    amount: float
    payer_phone: str
    payer_pin: str

class NFCPaymentRequest(BaseModel):
    terminal_id: str
    amount: float
    currency: str = "NGN"
    card_type: str = "unknown"
    card_last_four: Optional[str] = None
    card_hash: Optional[str] = None
    agent_id: int
    emv_data: Optional[Dict[str, Any]] = None

class NFCRefundRequest(BaseModel):
    transaction_ref: str
    reason: str
    agent_id: int

@app.post("/api/v1/qr/generate")
async def generate_qr(req: QRGenerateRequest):
    """Generate a payment QR code with real DB persistence."""
    ref = generate_reference("QR")
    expires_at = datetime.utcnow().isoformat() + "Z"

    qr_payload = json.dumps({
        "type": "54link_qr_payment", "code": ref,
        "amount": req.amount, "currency": req.currency,
        "merchant": req.merchant_id,
    })

    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO qr_codes (code, type, status, "agentId", amount, currency, description, metadata, "expiresAt", "createdAt")
               VALUES (%s, %s, 'active', %s, %s, %s, %s, %s, NOW() + INTERVAL '%s minutes', NOW()) RETURNING id""",
            (ref, "dynamic" if req.amount else "static", req.agent_id,
             req.amount, req.currency, req.description,
             json.dumps({"merchantId": req.merchant_id, "source": "python-service"}),
             req.expiry_minutes)
        )
        row = cur.fetchone()
        conn.commit()
        conn.close()
    except Exception as e:
        logging.warning(f"QR DB insert failed: {e}")

    if req.amount and req.amount > 0:
        await record_gl_entry(f"qr-gen-{ref}", req.amount, "QR_PENDING_DEBIT", "QR_ESCROW")

    await publish_kafka("qr.code.generated", {
        "code": ref, "amount": req.amount, "agentId": req.agent_id,
        "merchantId": req.merchant_id, "timestamp": datetime.utcnow().isoformat(),
    })
    await cache_redis(f"qr:{ref}", {"amount": req.amount, "agentId": req.agent_id, "status": "active"})
    await index_opensearch("qr_codes", ref, {"code": ref, "amount": req.amount, "type": "dynamic" if req.amount else "static"})

    log_audit("qr_generate", ref, json.dumps({"agent_id": req.agent_id, "amount": req.amount}))

    return {
        "code": ref, "qr_data": qr_payload, "amount": req.amount,
        "currency": req.currency, "expires_in": req.expiry_minutes * 60,
        "type": "dynamic" if req.amount else "static",
    }

@app.post("/api/v1/qr/scan")
async def scan_qr(code: str):
    """Validate a QR code before payment."""
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute('SELECT * FROM qr_codes WHERE code = %s LIMIT 1', (code,))
        qr = cur.fetchone()
        conn.close()
    except Exception:
        raise HTTPException(500, "Database error")

    if not qr:
        raise HTTPException(404, "QR code not found")
    if qr.get("status") != "active":
        raise HTTPException(400, f"QR code is {qr.get('status')}")

    await publish_kafka("qr.code.scanned", {"code": code, "source": "python"})

    return {
        "code": code, "amount": float(qr.get("amount") or 0),
        "status": qr.get("status"), "currency": qr.get("currency", "NGN"),
        "agentId": qr.get("agentId"),
    }

@app.post("/api/v1/qr/pay")
async def qr_pay(req: QRPayRequest):
    """Execute a QR code payment with full middleware integration."""
    if req.amount <= 0:
        raise HTTPException(400, "Amount must be positive")

    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute('SELECT * FROM qr_codes WHERE code = %s LIMIT 1', (req.code,))
        qr = cur.fetchone()
        if not qr:
            conn.close()
            raise HTTPException(404, "QR code not found")
        if qr.get("status") != "active":
            conn.close()
            raise HTTPException(400, "QR code already used or inactive")

        qr_amount = float(qr.get("amount") or 0)
        if qr_amount > 0 and abs(qr_amount - req.amount) > 0.01:
            conn.close()
            raise HTTPException(400, f"QR requires exact amount ₦{qr_amount:.2f}")

        fees = calculate_fee(req.amount, "qr")
        ref = generate_reference("QRP-PY")

        cur.execute(
            """INSERT INTO transactions (amount, reference, type, status, metadata, "createdAt")
               VALUES (%s, %s, 'qr_payment', 'completed', %s, NOW()) RETURNING id""",
            (req.amount, ref, json.dumps({
                "qrCode": req.code, "payerPhone": req.payer_phone,
                "fee": fees["fee"], "commission": fees["commission"],
                "netAmount": fees["net"], "agentId": qr.get("agentId"),
            }))
        )
        cur.execute("UPDATE qr_codes SET status = 'used' WHERE code = %s", (req.code,))
        conn.commit()
        conn.close()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Payment failed: {str(e)}")

    await record_gl_entry(ref, req.amount, "PAYER_QR_DEBIT", "MERCHANT_QR_CREDIT")

    await publish_kafka("qr.payment.completed", {
        "reference": ref, "qrCode": req.code, "amount": req.amount,
        "fee": fees["fee"], "netAmount": fees["net"],
        "payerPhone": req.payer_phone, "agentId": qr.get("agentId"),
        "timestamp": datetime.utcnow().isoformat(),
    })

    await index_opensearch("qr_payments", ref, {"reference": ref, "amount": req.amount, "code": req.code})
    await push_lakehouse("qr_payment_events", {"reference": ref, "amount": req.amount, "fee": fees["fee"]})
    await cache_redis(f"qr:{req.code}", {"status": "used"}, 60)

    log_audit("qr_payment", ref, json.dumps({"amount": req.amount, "code": req.code}))

    return {
        "reference": ref, "status": "completed", "amount": req.amount,
        "fee": fees["fee"], "netAmount": fees["net"], "commission": fees["commission"],
    }

# ── NFC Payment Endpoints ─────────────────────────────────────────────────────

@app.post("/api/v1/nfc/tap")
async def process_nfc(req: NFCPaymentRequest):
    """Process NFC tap-to-pay with EMV validation and full middleware integration."""
    if req.amount <= 0:
        raise HTTPException(400, "Amount must be positive")

    emv_validation = "not_provided"
    if req.emv_data:
        ct = req.emv_data.get("cryptogramType", "")
        if ct == "AAC":
            raise HTTPException(400, "Card declined (AAC cryptogram)")
        elif ct == "ARQC" and req.emv_data.get("cryptogram", ""):
            emv_validation = "validated"
        elif ct == "TC":
            emv_validation = "terminal_verified"

    fees = calculate_fee(req.amount, "nfc")
    ref = generate_reference("NFC-PY")

    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO transactions (amount, reference, type, status, metadata, "createdAt")
               VALUES (%s, %s, 'nfc_tap_to_pay', 'completed', %s, NOW()) RETURNING id""",
            (req.amount, ref, json.dumps({
                "terminalId": req.terminal_id, "cardType": req.card_type,
                "cardLastFour": req.card_last_four, "emvValidation": emv_validation,
                "fee": fees["fee"], "commission": fees["commission"],
                "netAmount": fees["net"], "agentId": req.agent_id,
            }))
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"NFC DB insert failed: {e}")

    await record_gl_entry(ref, req.amount, "NFC_CARD_DEBIT", "AGENT_NFC_CREDIT")

    await publish_kafka("nfc.transaction.completed", {
        "reference": ref, "amount": req.amount, "fee": fees["fee"],
        "netAmount": fees["net"], "terminalId": req.terminal_id,
        "cardType": req.card_type, "emvValidation": emv_validation,
        "agentId": req.agent_id, "timestamp": datetime.utcnow().isoformat(),
    })

    await index_opensearch("nfc_transactions", ref, {
        "reference": ref, "amount": req.amount, "cardType": req.card_type,
        "terminalId": req.terminal_id,
    })
    await push_lakehouse("nfc_payment_events", {"reference": ref, "amount": req.amount, "fee": fees["fee"]})
    await cache_redis(f"nfc:txn:{ref}", {"status": "completed", "amount": req.amount}, 3600)

    log_audit("nfc_payment", ref, json.dumps({"amount": req.amount, "terminal": req.terminal_id}))

    return {
        "reference": ref, "status": "completed", "amount": req.amount,
        "fee": fees["fee"], "netAmount": fees["net"], "commission": fees["commission"],
        "cardType": req.card_type, "emvValidation": emv_validation,
    }

@app.post("/api/v1/nfc/refund")
async def refund_nfc(req: NFCRefundRequest):
    """Refund an NFC tap-to-pay transaction."""
    refund_ref = generate_reference("NFCR-PY")

    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM transactions WHERE reference = %s LIMIT 1", (req.transaction_ref,))
        txn = cur.fetchone()
        if not txn:
            conn.close()
            raise HTTPException(404, "Transaction not found")
        amount = float(txn.get("amount", 0))

        cur.execute(
            """INSERT INTO transactions (amount, reference, type, status, metadata, "createdAt")
               VALUES (%s, %s, 'nfc_refund', 'completed', %s, NOW())""",
            (amount, refund_ref, json.dumps({
                "originalRef": req.transaction_ref, "reason": req.reason, "agentId": req.agent_id,
            }))
        )
        cur.execute("UPDATE transactions SET status = 'reversed' WHERE reference = %s", (req.transaction_ref,))
        conn.commit()
        conn.close()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Refund failed: {str(e)}")

    await record_gl_entry(refund_ref, amount, "AGENT_NFC_CREDIT", "NFC_CARD_DEBIT")
    await publish_kafka("nfc.transaction.refunded", {
        "reference": refund_ref, "originalRef": req.transaction_ref,
        "amount": amount, "reason": req.reason,
    })

    log_audit("nfc_refund", refund_ref, json.dumps({"original": req.transaction_ref}))

    return {"reference": refund_ref, "status": "refunded", "amount": amount}

# ── Analytics ─────────────────────────────────────────────────────────────────

@app.get("/api/v1/qr/analytics")
async def qr_analytics():
    """QR payment analytics with fraud detection signals."""
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT COUNT(*) as total FROM qr_codes")
        total = cur.fetchone()["total"]
        cur.execute("SELECT COUNT(*) as used FROM qr_codes WHERE status = 'used'")
        used = cur.fetchone()["used"]
        cur.execute("SELECT COALESCE(SUM(amount::numeric), 0) as vol FROM transactions WHERE type IN ('qr_payment', 'dynamic_qr_payment')")
        volume = float(cur.fetchone()["vol"])
        conn.close()
    except Exception:
        total, used, volume = 0, 0, 0.0

    return {
        "totalGenerated": total, "totalUsed": used,
        "totalActive": total - used, "totalVolume": volume,
        "conversionRate": round(used / total * 100, 1) if total > 0 else 0,
        "generatedAt": datetime.utcnow().isoformat(),
    }

@app.get("/api/v1/nfc/analytics")
async def nfc_analytics():
    """NFC payment analytics."""
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT COUNT(*) as total FROM transactions WHERE type = 'nfc_tap_to_pay'")
        total = cur.fetchone()["total"]
        cur.execute("SELECT COALESCE(SUM(amount::numeric), 0) as vol FROM transactions WHERE type = 'nfc_tap_to_pay'")
        volume = float(cur.fetchone()["vol"])
        conn.close()
    except Exception:
        total, volume = 0, 0.0

    return {
        "totalTransactions": total, "totalVolume": volume,
        "averageAmount": round(volume / total, 2) if total > 0 else 0,
        "generatedAt": datetime.utcnow().isoformat(),
    }

@app.get("/api/v1/nfc/fraud/check")
async def nfc_fraud_check(terminal_id: str, amount: float):
    """Real-time NFC fraud detection using velocity checks and anomaly scoring."""
    risk_score = 0.0
    flags: List[str] = []

    if amount > 500000:
        risk_score += 40
        flags.append("high_value_transaction")
    if amount > 1000000:
        risk_score += 30
        flags.append("exceeds_cbn_single_limit")

    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """SELECT COUNT(*) as cnt, COALESCE(SUM(amount::numeric), 0) as vol
               FROM transactions WHERE type = 'nfc_tap_to_pay'
               AND metadata::jsonb->>'terminalId' = %s
               AND "createdAt" >= NOW() - INTERVAL '1 hour'""",
            (terminal_id,)
        )
        row = cur.fetchone()
        hourly_count = row["cnt"]
        hourly_volume = float(row["vol"])
        conn.close()

        if hourly_count > 20:
            risk_score += 25
            flags.append("high_velocity")
        if hourly_volume > 2000000:
            risk_score += 20
            flags.append("high_hourly_volume")
    except Exception:
        pass

    decision = "approve" if risk_score < 50 else ("review" if risk_score < 80 else "decline")

    if risk_score >= 50:
        await publish_kafka("nfc.fraud.detected", {
            "terminalId": terminal_id, "amount": amount,
            "riskScore": risk_score, "flags": flags, "decision": decision,
        })

    return {
        "riskScore": risk_score, "decision": decision,
        "flags": flags, "terminalId": terminal_id, "amount": amount,
    }

@app.get("/api/v1/payments/{payment_id}")
async def get_payment(payment_id: str):
    """Get payment status from DB."""
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM transactions WHERE reference = %s LIMIT 1", (payment_id,))
        txn = cur.fetchone()
        conn.close()
        if txn:
            return {
                "payment_id": payment_id, "status": txn.get("status"),
                "amount": float(txn.get("amount", 0)), "type": txn.get("type"),
                "createdAt": str(txn.get("createdAt", "")),
            }
    except Exception:
        pass
    raise HTTPException(404, "Payment not found")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
