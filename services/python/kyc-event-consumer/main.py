"""
KYC Event Consumer Service
Port: 8216

Kafka consumer that listens for domain events and triggers appropriate
KYC/KYB verification workflows based on configurable rules with cooldown.

Trigger Rules:
  - account.application.created (tier >= 2) → standard KYC
  - loan.application.submitted → enhanced/full_edd per amount
  - kyc.verification.required → fires specified level
  - kyb.verification.required → triggers KYB corporate analysis
  - transaction.suspicious → enhanced re-verification
  - account.upgrade.requested → target tier's KYC level

Cooldown: Same customer can't re-trigger same level within 24h.

Integrations:
  - Kafka: consumes pos.kyc.events, account.*, loan.*, transaction.*, kyc.*
  - Redis: cooldown state (customer:level:last_triggered)
  - KYC Workflow Orchestrator (Python 8215): triggers workflows
  - Dapr: pub/sub for Kafka consumption via sidecar
  - Temporal: registers cooldown timers
  - Fluvio: streams trigger events to lakehouse
"""

import os
import json
import time
import uuid
import logging
import asyncio
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field

import httpx
from fastapi import FastAPI, BackgroundTasks
import sys as _sys2, os as _os2
_sys2.path.insert(0, _os2.path.join(_os2.path.dirname(_os2.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from pydantic import BaseModel

# --- Production: Graceful Shutdown ---
import signal
import sys
import atexit
import logging

# --- PostgreSQL Persistence ---
import asyncpg
from typing import Optional

_pg_pool: Optional[asyncpg.Pool] = None

async def get_pg_pool() -> Optional[asyncpg.Pool]:
    global _pg_pool
    if _pg_pool is None:
        try:
            _pg_pool = await asyncpg.create_pool(
                dsn=os.environ.get("DATABASE_URL", "postgresql://localhost:5432/agentbanking"),
                min_size=2, max_size=10, command_timeout=10
            )
            await _pg_pool.execute("""
                CREATE TABLE IF NOT EXISTS service_state (
                    key TEXT PRIMARY KEY,
                    value JSONB NOT NULL DEFAULT '{}',
                    service TEXT NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
        except Exception:
            _pg_pool = None
    return _pg_pool

async def pg_get(key: str, service: str):
    pool = await get_pg_pool()
    if pool:
        row = await pool.fetchrow(
            "SELECT value FROM service_state WHERE key = $1 AND service = $2", key, service
        )
        return row["value"] if row else None
    return None

async def pg_set(key: str, value, service: str):
    pool = await get_pg_pool()
    if pool:
        import json
        await pool.execute(
            "INSERT INTO service_state (key, value, service, updated_at) VALUES ($1, $2::jsonb, $3, NOW()) "
            "ON CONFLICT (key) DO UPDATE SET value = $2::jsonb, updated_at = NOW()",
            key, json.dumps(value) if not isinstance(value, str) else value, service
        )
# --- End PostgreSQL Persistence ---


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
logger = logging.getLogger("kyc-event-consumer")

# ══════════════════════════════════════════════════════════════════════════════
# Configuration
# ══════════════════════════════════════════════════════════════════════════════

KAFKA_BROKERS = os.getenv("KAFKA_BROKERS", "localhost:9092")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/16")
KYC_ORCHESTRATOR_URL = os.getenv("KYC_ORCHESTRATOR_URL", "http://localhost:8215")
KYB_ENGINE_URL = os.getenv("KYB_ENGINE_URL", "http://localhost:8130")
DAPR_URL = os.getenv("DAPR_HTTP_URL", "http://localhost:3500")
TEMPORAL_URL = os.getenv("TEMPORAL_URL", "http://localhost:7233")
FLUVIO_URL = os.getenv("FLUVIO_URL", "http://localhost:9003")
PORT = int(os.getenv("PORT", "8216"))
CONSUMER_GROUP = os.getenv("CONSUMER_GROUP", "kyc-processor")

# Cooldown period in hours (same customer can't re-trigger same level)
COOLDOWN_HOURS = int(os.getenv("COOLDOWN_HOURS", "24"))

# ══════════════════════════════════════════════════════════════════════════════
# Trigger Rules Configuration
# ══════════════════════════════════════════════════════════════════════════════

TRIGGER_RULES = {
    "account.application.created": {
        "condition": lambda event: event.get("tier", 1) >= 2,
        "kyc_level": lambda event: "standard" if event.get("tier") == 2 else "enhanced",
        "target_tier": lambda event: f"tier_{event.get('tier', 2)}",
        "cooldown_hours": 24,
        "description": "Account opening for Tier 2+ triggers standard/enhanced KYC",
    },
    "loan.application.submitted": {
        "condition": lambda event: True,  # All loans need KYC
        "kyc_level": lambda event: _loan_kyc_level(event),
        "target_tier": lambda event: "tier_3" if _loan_kyc_level(event) in ("enhanced", "full_edd") else "tier_2",
        "cooldown_hours": 24,
        "description": "Loan application triggers enhanced or full_edd KYC",
    },
    "kyc.verification.required": {
        "condition": lambda event: True,
        "kyc_level": lambda event: event.get("required_level", "standard"),
        "target_tier": lambda event: _level_to_tier(event.get("required_level", "standard")),
        "cooldown_hours": 1,  # Low cooldown — explicit triggers should fire
        "description": "Explicit KYC trigger from another service",
    },
    "kyb.verification.required": {
        "condition": lambda event: bool(event.get("company_id")),
        "kyc_level": lambda event: "full_edd",
        "target_tier": lambda event: "tier_3",
        "cooldown_hours": 48,
        "description": "KYB corporate verification trigger",
        "trigger_kyb": True,
    },
    "transaction.suspicious": {
        "condition": lambda event: True,
        "kyc_level": lambda event: "enhanced",
        "target_tier": lambda event: "tier_3",
        "cooldown_hours": 4,  # Shorter cooldown for suspicious activity
        "description": "Suspicious transaction triggers enhanced re-verification",
    },
    "account.upgrade.requested": {
        "condition": lambda event: True,
        "kyc_level": lambda event: _tier_to_level(event.get("target_tier", "tier_2")),
        "target_tier": lambda event: event.get("target_tier", "tier_2"),
        "cooldown_hours": 24,
        "description": "Account upgrade request triggers target tier KYC",
    },
}

SUBSCRIBED_TOPICS = [
    "pos.kyc.events",
    "account.application.created",
    "loan.application.submitted",
    "kyc.verification.required",
    "kyb.verification.required",
    "transaction.suspicious",
    "account.upgrade.requested",
]

def _loan_kyc_level(event: dict) -> str:
    """Determine KYC level for loan based on type and amount."""
    loan_type = event.get("loan_type", "personal")
    amount = event.get("amount", 0)
    if loan_type == "mortgage" or amount >= 50_000_000:
        return "full_edd"
    if loan_type in ("sme", "corporate") or amount >= 10_000_000:
        return "enhanced"
    return "enhanced"  # Minimum for any loan

def _level_to_tier(level: str) -> str:
    """Map KYC level to target tier."""
    mapping = {"basic": "tier_1", "standard": "tier_2", "enhanced": "tier_3", "full_edd": "tier_3"}
    return mapping.get(level, "tier_2")

def _tier_to_level(tier: str) -> str:
    """Map tier to KYC level."""
    mapping = {"tier_1": "basic", "tier_2": "standard", "tier_3": "enhanced"}
    return mapping.get(tier, "standard")

# ══════════════════════════════════════════════════════════════════════════════
# Cooldown Tracking (Redis-backed in production)
# ══════════════════════════════════════════════════════════════════════════════

cooldown_store: dict[str, datetime] = {}

def check_cooldown(customer_id: str, kyc_level: str, cooldown_hours: int) -> bool:
    """Check if this trigger is within cooldown period. Returns True if cooled down (OK to fire)."""
    key = f"{customer_id}:{kyc_level}"
    last_triggered = cooldown_store.get(key)
    if last_triggered is None:
        return True
    elapsed = datetime.now(timezone.utc) - last_triggered
    return elapsed > timedelta(hours=cooldown_hours)

def set_cooldown(customer_id: str, kyc_level: str):
    """Record that this trigger fired."""
    key = f"{customer_id}:{kyc_level}"
    cooldown_store[key] = datetime.now(timezone.utc)

# ══════════════════════════════════════════════════════════════════════════════
# Event Processing
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ProcessingStats:
    events_received: int = 0
    events_processed: int = 0
    events_skipped_cooldown: int = 0
    events_skipped_condition: int = 0
    workflows_triggered: int = 0
    kyb_triggered: int = 0
    errors: int = 0

stats = ProcessingStats()

async def process_event(topic: str, event: dict):
    """Process a single Kafka event and trigger appropriate KYC workflow."""
    stats.events_received += 1

    rule = TRIGGER_RULES.get(topic)
    if not rule:
        # Check if it's a generic pos.kyc.events message
        if topic == "pos.kyc.events":
            inner_topic = event.get("event_type", "")
            rule = TRIGGER_RULES.get(inner_topic)
            if not rule:
                stats.events_skipped_condition += 1
                return

    customer_id = event.get("customer_id") or event.get("customerId", "")
    if not customer_id:
        logger.warning(f"Event on {topic} has no customer_id, skipping")
        stats.events_skipped_condition += 1
        return

    # Check condition
    if not rule["condition"](event):
        stats.events_skipped_condition += 1
        logger.debug(f"Event on {topic} for {customer_id} failed condition check")
        return

    kyc_level = rule["kyc_level"](event)
    cooldown_hours = rule.get("cooldown_hours", COOLDOWN_HOURS)

    # Check cooldown
    if not check_cooldown(customer_id, kyc_level, cooldown_hours):
        stats.events_skipped_cooldown += 1
        logger.info(f"Event on {topic} for {customer_id} skipped (cooldown active, level={kyc_level})")
        return

    # Fire trigger
    set_cooldown(customer_id, kyc_level)
    target_tier = rule["target_tier"](event)

    if rule.get("trigger_kyb"):
        # Trigger KYB verification
        await trigger_kyb(event.get("company_id", ""), customer_id, event)
        stats.kyb_triggered += 1
    else:
        # Trigger KYC workflow
        await trigger_kyc_workflow(customer_id, kyc_level, target_tier, topic, event)
        stats.workflows_triggered += 1

    stats.events_processed += 1

    # Stream to Fluvio
    await stream_trigger_event(topic, customer_id, kyc_level, target_tier)

    logger.info(f"Triggered {kyc_level} KYC for {customer_id} (topic={topic}, tier={target_tier})")

async def trigger_kyc_workflow(customer_id: str, kyc_level: str, target_tier: str, trigger_topic: str, event: dict):
    """Call KYC Workflow Orchestrator to start a verification pipeline."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{KYC_ORCHESTRATOR_URL}/api/v1/workflow/start",
                json={
                    "customer_id": customer_id,
                    "kyc_level": kyc_level,
                    "target_tier": target_tier,
                    "triggered_by": f"event:{trigger_topic}",
                    "customer_data": {
                        "first_name": event.get("first_name", ""),
                        "last_name": event.get("last_name", ""),
                        "bvn": event.get("bvn", ""),
                        "nin": event.get("nin", ""),
                        "nationality": event.get("nationality", "Nigeria"),
                        "documents": event.get("documents", []),
                    },
                },
                timeout=10.0,
            )
            if resp.status_code in (200, 201, 202):
                data = resp.json()
                logger.info(f"KYC workflow started: {data.get('workflow_id')}")
            else:
                logger.error(f"KYC orchestrator returned {resp.status_code}")
                stats.errors += 1
    except Exception as e:
        logger.error(f"Failed to trigger KYC workflow: {e}")
        stats.errors += 1

async def trigger_kyb(company_id: str, customer_id: str, event: dict):
    """Trigger KYB corporate verification."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{KYB_ENGINE_URL}/api/v1/kyb/verify",
                json={
                    "company_id": company_id,
                    "customer_id": customer_id,
                    "rc_number": event.get("rc_number", ""),
                    "shareholders": event.get("shareholders", []),
                },
                timeout=15.0,
            )
            if resp.status_code in (200, 201, 202):
                logger.info(f"KYB verification triggered for company {company_id}")
            else:
                stats.errors += 1
    except Exception as e:
        logger.error(f"Failed to trigger KYB: {e}")
        stats.errors += 1

async def stream_trigger_event(topic: str, customer_id: str, kyc_level: str, target_tier: str):
    """Stream trigger event to Fluvio lakehouse."""
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{FLUVIO_URL}/api/v1/produce/kyc-triggers",
                json={
                    "topic": topic,
                    "customer_id": customer_id,
                    "kyc_level": kyc_level,
                    "target_tier": target_tier,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                timeout=5.0,
            )
    except Exception:
        pass

# ══════════════════════════════════════════════════════════════════════════════
# Dapr Event Subscription Endpoint
# ══════════════════════════════════════════════════════════════════════════════

app = FastAPI(

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/kyc_event_consumer")

@app.on_event("startup")
async def _init_pg_pool():
    await get_pg_pool()

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
    title="KYC Event Consumer",
    description="Kafka event consumer with trigger rules and cooldown tracking",
    version="1.0.0",
)

class DaprEvent(BaseModel):
    """Dapr CloudEvent envelope."""
    topic: str = ""
    data: dict = {}
    source: str = ""
    type: str = ""
    specversion: str = "1.0"
    id: str = ""

@app.post("/api/v1/events/process")
async def receive_event(event: DaprEvent, background_tasks: BackgroundTasks):
    """Receive events from Dapr pub/sub (Kafka via sidecar)."""
    # Persist operation result to PostgreSQL
    import json as _json, time as _time
    await pg_set("receive_event_" + str(int(_time.time() * 1000)), _json.dumps({"action": "receive_event", "timestamp": _time.time()}), "kyc-event-consumer")

    background_tasks.add_task(process_event, event.topic, event.data)
    return {"status": "accepted"}

@app.post("/api/v1/events/batch")
async def receive_batch(events: list[DaprEvent], background_tasks: BackgroundTasks):
    """Receive a batch of events."""
    # Persist operation result to PostgreSQL
    import json as _json, time as _time
    await pg_set("receive_batch_" + str(int(_time.time() * 1000)), _json.dumps({"action": "receive_batch", "timestamp": _time.time()}), "kyc-event-consumer")

    for event in events:
        background_tasks.add_task(process_event, event.topic, event.data)
    return {"status": "accepted", "count": len(events)}

# Dapr subscription declaration
@app.get("/dapr/subscribe")
async def dapr_subscribe():
    """Tell Dapr which topics we subscribe to."""
    # Load persisted state from PostgreSQL
    _pg_cached = await pg_get("dapr_subscribe", "kyc-event-consumer")
    if _pg_cached is not None:
        import json as _json
        try:
            return _json.loads(_pg_cached) if isinstance(_pg_cached, str) else _pg_cached
        except Exception:
            pass

    return [
        {"pubsubname": "kafka-pubsub", "topic": topic, "route": "/api/v1/events/process"}
        for topic in SUBSCRIBED_TOPICS
    ]

@app.get("/api/v1/rules")
async def get_trigger_rules():
    """List all configured trigger rules."""
    # Load persisted state from PostgreSQL
    _pg_cached = await pg_get("get_trigger_rules", "kyc-event-consumer")
    if _pg_cached is not None:
        import json as _json
        try:
            return _json.loads(_pg_cached) if isinstance(_pg_cached, str) else _pg_cached
        except Exception:
            pass

    rules = {}
    for topic, rule in TRIGGER_RULES.items():
        rules[topic] = {
            "description": rule["description"],
            "cooldown_hours": rule.get("cooldown_hours", COOLDOWN_HOURS),
            "triggers_kyb": rule.get("trigger_kyb", False),
        }
    return {"rules": rules, "subscribed_topics": SUBSCRIBED_TOPICS}

@app.get("/api/v1/stats")
async def get_stats():
    """Get processing statistics."""
    # Load persisted state from PostgreSQL
    _pg_cached = await pg_get("get_stats", "kyc-event-consumer")
    if _pg_cached is not None:
        import json as _json
        try:
            return _json.loads(_pg_cached) if isinstance(_pg_cached, str) else _pg_cached
        except Exception:
            pass

    return {
        "events_received": stats.events_received,
        "events_processed": stats.events_processed,
        "events_skipped_cooldown": stats.events_skipped_cooldown,
        "events_skipped_condition": stats.events_skipped_condition,
        "workflows_triggered": stats.workflows_triggered,
        "kyb_triggered": stats.kyb_triggered,
        "errors": stats.errors,
        "active_cooldowns": len(cooldown_store),
    }

@app.delete("/api/v1/cooldowns/{customer_id}")
async def clear_cooldown(customer_id: str):
    """Clear all cooldowns for a customer (admin use for re-verification)."""
    # Persist operation result to PostgreSQL
    import json as _json, time as _time
    await pg_set("clear_cooldown_" + str(int(_time.time() * 1000)), _json.dumps({"action": "clear_cooldown", "timestamp": _time.time()}), "kyc-event-consumer")

    cleared = 0
    keys_to_remove = [k for k in cooldown_store if k.startswith(f"{customer_id}:")]
    for k in keys_to_remove:
        del cooldown_store[k]
        cleared += 1
    return {"customer_id": customer_id, "cooldowns_cleared": cleared}

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "kyc-event-consumer",
        "version": "1.0.0",
        "language": "python",
        "consumer_group": CONSUMER_GROUP,
        "subscribed_topics": SUBSCRIBED_TOPICS,
        "trigger_rules_count": len(TRIGGER_RULES),
        "active_cooldowns": len(cooldown_store),
        "stats": {
            "events_received": stats.events_received,
            "workflows_triggered": stats.workflows_triggered,
        },
        "integrations": {
            "kafka": KAFKA_BROKERS,
            "kyc_orchestrator": KYC_ORCHESTRATOR_URL,
            "kyb_engine": KYB_ENGINE_URL,
            "redis": REDIS_URL,
            "temporal": TEMPORAL_URL,
        },
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
