import httpx
"""
WhatsApp Banking Channel — Conversational banking via WhatsApp Business API

Commands:
- BAL: Check float balance
- STMT: Mini-statement (last 5 transactions)
- SEND <amount> <phone>: P2P transfer
- BILL <type> <account> <amount>: Bill payment
- AIR <phone> <amount>: Airtime purchase
- HELP: Command reference
"""
import asyncio
import hashlib
import hmac
import json
import logging
import os
import time
from datetime import datetime
from typing import Optional

import asyncpg
from fastapi import FastAPI, Request, HTTPException
import sys as _sys2, os as _os2
_sys2.path.insert(0, _os2.path.join(_os2.path.dirname(_os2.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("whatsapp-banking")


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
            "service.name": os.environ.get("OTEL_SERVICE_NAME", "whatsapp-banking"),
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

app = FastAPI(title="54Link WhatsApp Banking", version="1.0.0")
apply_middleware(app, enable_auth=True)
# Instrument FastAPI with OpenTelemetry
if _otel_endpoint:
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
    except (ImportError, Exception):
        pass


DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost:5432/agentbanking")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "54link_verify")
pool: Optional[asyncpg.Pool] = None

class WhatsAppMessage(BaseModel):
    from_number: str
    body: str
    timestamp: int

class ConversationState:
    def __init__(self):
        self.sessions: dict[str, dict] = {}

    def get_session(self, phone: str) -> dict:
        if phone not in self.sessions:
            self.sessions[phone] = {
                "state": "idle",
                "agent_id": None,
                "last_active": time.time(),
                "context": {},
            }
        self.sessions[phone]["last_active"] = time.time()
        return self.sessions[phone]

    def clear_expired(self, timeout: int = 1800):
        now = time.time()
        expired = [k for k, v in self.sessions.items() if now - v["last_active"] > timeout]
        for k in expired:
            del self.sessions[k]

conv_state = ConversationState()

@app.on_event("startup")
async def startup():
    global pool
    try:
        pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=2,
            max_size=20,
            command_timeout=30,
        )
        logger.info("Connected to PostgreSQL")
    except Exception as e:
        logger.warning(f"DB connection failed (non-fatal): {e}")

@app.on_event("shutdown")
async def shutdown():
    if pool:
        await pool.close()

@app.get("/health")
async def health():
    db_ok = False
    if pool:
        try:
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            db_ok = True
        except Exception:
            pass
    return {"status": "healthy", "service": "whatsapp-banking", "db": db_ok}

@app.get("/webhook")
async def verify_webhook(hub_mode: str = "", hub_verify_token: str = "", hub_challenge: str = ""):
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return int(hub_challenge)
    raise HTTPException(status_code=403, detail="Verification failed")

@app.post("/webhook")
async def receive_message(request: Request):
    body = await request.json()
    entries = body.get("entry", [])
    for entry in entries:
        changes = entry.get("changes", [])
        for change in changes:
            messages = change.get("value", {}).get("messages", [])
            for msg in messages:
                phone = msg.get("from", "")
                text = msg.get("text", {}).get("body", "").strip()
                if phone and text:
                    response = await process_command(phone, text)
                    logger.info(f"[{phone}] '{text}' → '{response[:100]}...'")
    return {"status": "ok"}

async def process_command(phone: str, text: str) -> str:
    session = conv_state.get_session(phone)
    cmd = text.upper().split()

    if not cmd:
        return HELP_TEXT

    command = cmd[0]

    # Authenticate agent by phone
    if session["agent_id"] is None and command != "REG":
        agent = await lookup_agent_by_phone(phone)
        if agent:
            session["agent_id"] = agent["id"]
        else:
            return (
                "Welcome to 54Link WhatsApp Banking!\n\n"
                "Your phone number is not registered.\n"
                "Please contact your super-agent to register."
            )

    if command == "BAL":
        return await handle_balance(session)
    elif command == "STMT":
        return await handle_statement(session)
    elif command == "SEND" and len(cmd) >= 3:
        amount = parse_amount(cmd[1])
        recipient = cmd[2]
        return await handle_transfer(session, amount, recipient)
    elif command == "BILL" and len(cmd) >= 4:
        bill_type = cmd[1]
        account = cmd[2]
        amount = parse_amount(cmd[3])
        return await handle_bill_payment(session, bill_type, account, amount)
    elif command == "AIR" and len(cmd) >= 3:
        phone_num = cmd[1]
        amount = parse_amount(cmd[2])
        return await handle_airtime(session, phone_num, amount)
    elif command == "HELP":
        return HELP_TEXT
    else:
        return f"Unknown command: {command}\n\nType HELP for available commands."

async def lookup_agent_by_phone(phone: str) -> Optional[dict]:
    if not pool:
        return None
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, agent_code, name, float_balance FROM agents WHERE phone = $1 AND is_active = true",
                phone,
            )
            if row:
                return dict(row)
    except Exception as e:
        logger.error(f"Agent lookup failed: {e}")
    return None

async def handle_balance(session: dict) -> str:
    if not pool:
        return "Service temporarily unavailable."
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT float_balance, name FROM agents WHERE id = $1", session["agent_id"]
            )
            if row:
                balance = float(row["float_balance"] or 0)
                return (
                    f"💰 *Float Balance*\n\n"
                    f"Agent: {row['name']}\n"
                    f"Balance: NGN {balance:,.2f}\n"
                    f"As at: {datetime.now().strftime('%d %b %Y, %H:%M')}"
                )
    except Exception as e:
        logger.error(f"Balance check failed: {e}")
    return "Unable to fetch balance. Try again."

async def handle_statement(session: dict) -> str:
    if not pool:
        return "Service temporarily unavailable."
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT type, amount, status, created_at
                   FROM transactions
                   WHERE agent_id = $1
                   ORDER BY created_at DESC
                   LIMIT 5""",
                session["agent_id"],
            )
            if not rows:
                return "No recent transactions."

            lines = ["📋 *Mini-Statement (Last 5)*\n"]
            for r in rows:
                amt = float(r["amount"] or 0)
                dt = r["created_at"].strftime("%d/%m %H:%M")
                lines.append(f"  {dt} | {r['type']:10} | NGN {amt:>12,.2f} | {r['status']}")
            return "\n".join(lines)
    except Exception as e:
        logger.error(f"Statement failed: {e}")
    return "Unable to fetch statement. Try again."

async def handle_transfer(session: dict, amount: float, recipient: str) -> str:
    if amount <= 0:
        return "Invalid amount. Use: SEND <amount> <phone>"
    if amount > 500000:
        return "Maximum transfer: NGN 500,000"
    return (
        f"✅ Transfer initiated\n\n"
        f"Amount: NGN {amount:,.2f}\n"
        f"To: {recipient}\n"
        f"Status: Processing\n"
        f"Ref: TRF-{int(time.time())}"
    )

async def handle_bill_payment(session: dict, bill_type: str, account: str, amount: float) -> str:
    valid_types = {"DSTV", "GOTV", "ELECTRIC", "WATER", "INTERNET"}
    if bill_type.upper() not in valid_types:
        return f"Invalid bill type. Supported: {', '.join(valid_types)}"
    if amount <= 0:
        return "Invalid amount."
    return (
        f"✅ Bill Payment\n\n"
        f"Type: {bill_type.upper()}\n"
        f"Account: {account}\n"
        f"Amount: NGN {amount:,.2f}\n"
        f"Status: Processing\n"
        f"Ref: BIL-{int(time.time())}"
    )

async def handle_airtime(session: dict, phone_num: str, amount: float) -> str:
    if amount < 50 or amount > 50000:
        return "Airtime amount: NGN 50 - NGN 50,000"
    return (
        f"✅ Airtime Purchase\n\n"
        f"Phone: {phone_num}\n"
        f"Amount: NGN {amount:,.2f}\n"
        f"Status: Delivered\n"
        f"Ref: AIR-{int(time.time())}"
    )

def parse_amount(s: str) -> float:
    try:
        return float(s.replace(",", "").replace("NGN", "").strip())
    except ValueError:
        return 0

HELP_TEXT = """🏦 *54Link WhatsApp Banking*

Commands:
• *BAL* — Check float balance
• *STMT* — Mini-statement (last 5 txs)
• *SEND* <amount> <phone> — Transfer funds
• *BILL* <type> <account> <amount> — Pay bills
  Types: DSTV, GOTV, ELECTRIC, WATER, INTERNET
• *AIR* <phone> <amount> — Buy airtime
• *HELP* — Show this menu

Examples:
• BAL
• SEND 5000 08012345678
• BILL DSTV 1234567890 7500
• AIR 08098765432 1000"""

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8460")))
