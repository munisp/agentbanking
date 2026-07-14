"""Dispute Resolution Service"""

import os
import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import List, Optional

import asyncpg
import uvicorn
from adapters import TransactionLedgerAdapter
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from middlewares import RequiredHeadersMiddleware
from pydantic import BaseModel
from schemas import Context
from utils.kafka_client import DisputeEventTypes
from utils.kafka_instance import kafka_client

load_dotenv()

app = FastAPI(title="54agent Dispute Service", version="1.0.0")

app.add_middleware(
    RequiredHeadersMiddleware,
    required_headers=["x-tenant-id", "x-keycloak-id"],
    exclude_prefixes=["/health", "/dapr"],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db_pool: asyncpg.Pool = None


# ── DB setup ──────────────────────────────────────────────────────────────────

async def _get_db() -> Optional[asyncpg.Pool]:
    return db_pool


def _require_db(db: Optional[asyncpg.Pool]) -> asyncpg.Pool:
    """Raise 503 immediately for write paths that cannot degrade gracefully."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not ready")
    return db


@app.on_event("startup")
async def startup():
    global db_pool

    try:
        db_pool = await asyncpg.create_pool(
            host=os.getenv("DB_HOST", "postgres"),
            port=int(os.getenv("DB_PORT", "5432")),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", "postgres"),
            database=os.getenv("DB_NAME", "link_core_banking"),
            min_size=5,
            max_size=20,
        )
        # Probe the connection before trusting it
        async with db_pool.acquire() as _conn:
            await _conn.fetchval("SELECT 1")
    except Exception as exc:
        import logging
        logging.getLogger("dispute-service").warning(
            "Database unreachable at startup (%s). Starting in degraded mode.", exc
        )
        db_pool = None
        return

    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS disputes (
                id          SERIAL PRIMARY KEY,
                dispute_id  VARCHAR(50) UNIQUE NOT NULL,
                customer_id VARCHAR(50) NOT NULL,
                agent_id    VARCHAR(50),
                transaction_id VARCHAR(50),
                dispute_type VARCHAR(50) NOT NULL,
                tenant_id   VARCHAR(50) NOT NULL,
                amount      DECIMAL(15,2),
                title       VARCHAR(255),
                description TEXT,
                category    VARCHAR(50),
                priority    VARCHAR(20) DEFAULT 'medium',
                status      VARCHAR(20) DEFAULT 'open',
                resolution  TEXT,
                admin_notes TEXT,
                evidence_urls TEXT,
                refund_amount DECIMAL(15,2),
                resolved_at TIMESTAMP,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_disputes_customer ON disputes(customer_id);
            CREATE INDEX IF NOT EXISTS idx_disputes_tenant   ON disputes(tenant_id);
            CREATE INDEX IF NOT EXISTS idx_disputes_status   ON disputes(status);

            CREATE TABLE IF NOT EXISTS dispute_messages (
                id          SERIAL PRIMARY KEY,
                dispute_id  INTEGER NOT NULL REFERENCES disputes(id) ON DELETE CASCADE,
                sender_type VARCHAR(20) NOT NULL,
                sender_id   VARCHAR(50) NOT NULL,
                message     TEXT NOT NULL,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_dmsg_dispute ON dispute_messages(dispute_id);

            CREATE TABLE IF NOT EXISTS dispute_auto_rules (
                id              SERIAL PRIMARY KEY,
                rule_id         VARCHAR(50) UNIQUE NOT NULL,
                tenant_id       VARCHAR(50) NOT NULL,
                name            VARCHAR(255) NOT NULL,
                dispute_type    VARCHAR(50) NOT NULL,
                threshold_amount DECIMAL(15,2),
                action          VARCHAR(50) NOT NULL,
                active          BOOLEAN DEFAULT TRUE,
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_auto_rules_tenant ON dispute_auto_rules(tenant_id);

            CREATE TABLE IF NOT EXISTS dispute_arbitration (
                id              SERIAL PRIMARY KEY,
                case_id         VARCHAR(50) UNIQUE NOT NULL,
                dispute_id      VARCHAR(50) NOT NULL REFERENCES disputes(dispute_id),
                tenant_id       VARCHAR(50) NOT NULL,
                stage           VARCHAR(50) DEFAULT 'pending_panel',
                ruling          VARCHAR(50),
                refund_amount   DECIMAL(15,2),
                panel_notes     TEXT,
                ruled_at        TIMESTAMP,
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_arbitration_tenant ON dispute_arbitration(tenant_id);

            CREATE TABLE IF NOT EXISTS chargebacks (
                id              SERIAL PRIMARY KEY,
                chargeback_id   VARCHAR(50) UNIQUE NOT NULL,
                dispute_id      VARCHAR(50) REFERENCES disputes(dispute_id),
                tenant_id       VARCHAR(50) NOT NULL,
                transaction_id  VARCHAR(50),
                amount          DECIMAL(15,2),
                reason          VARCHAR(255),
                status          VARCHAR(20) DEFAULT 'pending',
                outcome         VARCHAR(50),
                refund_amount   DECIMAL(15,2),
                resolved_at     TIMESTAMP,
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_chargebacks_tenant ON chargebacks(tenant_id);

            CREATE TABLE IF NOT EXISTS customer_dispute_portal (
                id                  SERIAL PRIMARY KEY,
                portal_dispute_id   VARCHAR(50) UNIQUE NOT NULL,
                dispute_id          VARCHAR(50) REFERENCES disputes(dispute_id),
                tenant_id           VARCHAR(50) NOT NULL,
                transaction_reference VARCHAR(100),
                reason              VARCHAR(100),
                evidence            TEXT,
                customer_email      VARCHAR(255),
                status              VARCHAR(20) DEFAULT 'submitted',
                created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_portal_tenant ON customer_dispute_portal(tenant_id);
        """)

        # Safe column additions for existing deployments
        for col_sql in [
            "ALTER TABLE disputes ADD COLUMN IF NOT EXISTS agent_id VARCHAR(50)",
            "ALTER TABLE disputes ADD COLUMN IF NOT EXISTS title VARCHAR(255)",
            "ALTER TABLE disputes ADD COLUMN IF NOT EXISTS category VARCHAR(50)",
            "ALTER TABLE disputes ADD COLUMN IF NOT EXISTS priority VARCHAR(20) DEFAULT 'medium'",
            "ALTER TABLE disputes ADD COLUMN IF NOT EXISTS admin_notes TEXT",
            "ALTER TABLE disputes ADD COLUMN IF NOT EXISTS evidence_urls TEXT",
            "ALTER TABLE disputes ADD COLUMN IF NOT EXISTS refund_amount DECIMAL(15,2)",
            "ALTER TABLE disputes ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMP",
            "ALTER TABLE disputes ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            "ALTER TABLE disputes ALTER COLUMN transaction_id DROP NOT NULL",
            "ALTER TABLE disputes ALTER COLUMN amount DROP NOT NULL",
        ]:
            try:
                await conn.execute(col_sql)
            except Exception:
                pass  # column already exists or constraint already dropped


@app.on_event("shutdown")
async def shutdown():
    if db_pool:
        await db_pool.close()


# ── Schemas ────────────────────────────────────────────────────────────────────

class DisputeStatus(str, Enum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    CLOSED = "closed"
    ESCALATED = "escalated"


class CreateDisputeSchema(BaseModel):
    # Accept both field naming conventions (backend canonical vs agent-app friendly)
    transaction_id: Optional[str] = None
    transaction_reference: Optional[str] = None  # alias used by agent apps
    dispute_type: Optional[str] = None
    reason: Optional[str] = None               # alias used by agent apps
    title: Optional[str] = None
    description: str
    category: Optional[str] = None
    priority: str = "medium"
    agent_id: Optional[str] = None
    amount: Optional[float] = None
    evidence_urls: Optional[List[str]] = None
    evidence: Optional[str] = None             # single evidence string from agent apps


class UpdateDisputeSchema(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    admin_notes: Optional[str] = None


class ResolveDisputeSchema(BaseModel):
    resolution: str
    admin_notes: Optional[str] = None
    refund_amount: Optional[float] = None


class CreateMessageSchema(BaseModel):
    message: Optional[str] = None
    content: Optional[str] = None   # alias used by agent apps
    sender_type: str = "agent"
    sender_id: Optional[str] = None  # inferred from x-keycloak-id if omitted


class CreateAutoRuleSchema(BaseModel):
    id: Optional[str] = None  # if present, update existing rule
    name: str
    dispute_type: str
    threshold_amount: Optional[float] = None
    action: str
    active: bool = True


class ArbitrationRulingSchema(BaseModel):
    ruling: str
    refund_amount: Optional[float] = None
    panel_notes: str


class ResolveChargebackSchema(BaseModel):
    outcome: str
    refund_amount: Optional[float] = None


class CustomerPortalDisputeSchema(BaseModel):
    transaction_reference: Optional[str] = None
    reason: Optional[str] = None
    evidence: Optional[str] = None
    customer_email: Optional[str] = None


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _fetch_dispute(conn, dispute_id: str, tenant_id: str):
    row = await conn.fetchrow(
        "SELECT * FROM disputes WHERE dispute_id = $1 AND tenant_id = $2",
        dispute_id, tenant_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Dispute not found")
    return row


def _ai_recommendation(dispute_type: str, amount: Optional[float]):
    """Simple rule-based recommendation to back the mediation AI UI."""
    dtype = (dispute_type or "").lower()
    amt = float(amount or 0)
    if dtype in ("unauthorized", "unauthorized_charge"):
        return "full_refund", min(amt, amt), 0.92
    if dtype in ("duplicate_transaction",):
        return "full_refund", amt, 0.88
    if dtype in ("wrong_amount", "incorrect_amount"):
        return "partial_refund", amt * 0.5, 0.75
    if dtype in ("failed_credit",):
        return "full_refund", amt, 0.85
    if dtype in ("technical_error",):
        return "partial_refund", amt * 0.5, 0.65
    return "deny", 0, 0.55


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "dispute-service"}


# ── Core Dispute CRUD ──────────────────────────────────────────────────────────

@app.get("/api/v1/disputes")
async def get_all_disputes(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    tenant_id: str = Header(..., alias="x-tenant-id"),
    db: asyncpg.Pool = Depends(_get_db),
):
    conditions = ["tenant_id = $1"]
    params = [tenant_id]
    if status:
        params.append(status)
        conditions.append(f"status = ${len(params)}")
    if priority:
        params.append(priority)
        conditions.append(f"priority = ${len(params)}")

    params += [limit, offset]
    where = " AND ".join(conditions)
    rows = await db.fetch(
        f"SELECT * FROM disputes WHERE {where} ORDER BY created_at DESC LIMIT ${len(params)-1} OFFSET ${len(params)}",
        *params,
    )
    return [dict(r) for r in rows]


@app.get("/api/v1/disputes/tenant")
async def get_tenant_disputes(
    status: Optional[str] = None,
    limit: int = 50,
    tenant_id: str = Header(..., alias="x-tenant-id"),
    db: asyncpg.Pool = Depends(_get_db),
):
    if status:
        rows = await db.fetch(
            "SELECT * FROM disputes WHERE tenant_id = $1 AND status = $2 ORDER BY created_at DESC LIMIT $3",
            tenant_id, status, limit,
        )
    else:
        rows = await db.fetch(
            "SELECT * FROM disputes WHERE tenant_id = $1 ORDER BY created_at DESC LIMIT $2",
            tenant_id, limit,
        )
    return [dict(r) for r in rows]


@app.get("/api/v1/disputes/stats")
async def get_stats_v1(
    tenant_id: str = Header(..., alias="x-tenant-id"),
    db: Optional[asyncpg.Pool] = Depends(_get_db),
):
    if db is None:
        return {"total": 0, "open": 0, "investigating": 0, "resolved": 0, "closed": 0, "escalated": 0, "total_amount": "0.00"}
    row = await db.fetchrow(
        """SELECT
             COUNT(*)                                          AS total,
             COUNT(*) FILTER (WHERE status = 'open')          AS open,
             COUNT(*) FILTER (WHERE status = 'investigating') AS investigating,
             COUNT(*) FILTER (WHERE status = 'resolved')      AS resolved,
             COUNT(*) FILTER (WHERE status = 'closed')        AS closed,
             COUNT(*) FILTER (WHERE status = 'escalated')     AS escalated,
             COALESCE(SUM(amount), 0)                         AS total_amount
           FROM disputes
           WHERE tenant_id = $1""",
        tenant_id,
    )
    return {
        "total": row["total"],
        "open": row["open"],
        "investigating": row["investigating"],
        "resolved": row["resolved"],
        "closed": row["closed"],
        "escalated": row["escalated"],
        "total_amount": f"{row['total_amount']:.2f}",
    }


@app.get("/api/v1/disputes/{dispute_id}")
async def get_dispute(
    dispute_id: str,
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
    ledger_id: Optional[str] = Header(None, alias="x-ledger-id"),
    db: asyncpg.Pool = Depends(_get_db),
):
    async with db.acquire() as conn:
        dispute = await _fetch_dispute(conn, dispute_id, tenant_id)
        result = dict(dispute)

        if ledger_id and dispute["transaction_id"]:
            try:
                context = Context(tenant_id=tenant_id, keycloak_id=keycloak_id, ledger_id=ledger_id)
                txn_response = TransactionLedgerAdapter().get_transaction_by_id(dispute["transaction_id"], context)
                result["transaction"] = txn_response.get("transaction") or {}
            except Exception:
                result["transaction"] = {}

        return result


@app.post("/api/v1/disputes", status_code=201)
async def create_dispute(
    payload: CreateDisputeSchema,
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
    ledger_id: Optional[str] = Header(None, alias="x-ledger-id"),
    db: Optional[asyncpg.Pool] = Depends(_get_db),
):
    db = _require_db(db)
    # Normalise field aliases
    txn_id = payload.transaction_id or payload.transaction_reference
    dispute_type = payload.dispute_type or payload.reason
    if not dispute_type:
        raise HTTPException(status_code=422, detail="dispute_type or reason is required")

    dispute_id = f"DSP-{uuid.uuid4().hex[:10].upper()}"
    title = payload.title or f"{dispute_type.replace('_', ' ').title()} Dispute"

    evidence_parts: List[str] = []
    if payload.evidence_urls:
        evidence_parts.extend(payload.evidence_urls)
    if payload.evidence:
        evidence_parts.append(payload.evidence)
    evidence = ",".join(evidence_parts) if evidence_parts else None

    amount = payload.amount
    if amount is None and ledger_id and txn_id:
        try:
            context = Context(tenant_id=tenant_id, keycloak_id=keycloak_id, ledger_id=ledger_id)
            txn_response = TransactionLedgerAdapter().get_transaction_by_id(txn_id, context)
            txn = txn_response.get("transaction")
            if txn:
                amount = txn.get("amount")
        except Exception:
            pass

    async with db.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO disputes
               (dispute_id, customer_id, agent_id, transaction_id, dispute_type,
                tenant_id, amount, title, description, category, priority,
                status, evidence_urls)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,'open',$12)
               RETURNING *""",
            dispute_id, keycloak_id, payload.agent_id, txn_id,
            dispute_type, tenant_id,
            Decimal(str(amount)) if amount is not None else None,
            title, payload.description, payload.category, payload.priority, evidence,
        )

        await conn.execute(
            """INSERT INTO dispute_messages (dispute_id, sender_type, sender_id, message)
               VALUES ($1, 'system', 'dispute-service', $2)""",
            row["id"], f"Dispute '{title}' opened. Priority: {payload.priority}.",
        )

    try:
        kafka_client.publish_dispute_event(
            event_type=DisputeEventTypes.DISPUTE_CREATED,
            dispute_id=dispute_id,
            tenant_id=tenant_id,
            status="open",
            metadata={
                "customer_id": keycloak_id,
                "transaction_id": txn_id,
                "dispute_type": dispute_type,
                "amount": str(amount) if amount else None,
            },
        )
    except Exception:
        pass

    return {"status": "created", "dispute_id": dispute_id, **dict(row)}


@app.put("/api/v1/disputes/{dispute_id}")
async def update_dispute(
    dispute_id: str,
    payload: UpdateDisputeSchema,
    tenant_id: str = Header(..., alias="x-tenant-id"),
    db: asyncpg.Pool = Depends(_get_db),
):
    async with db.acquire() as conn:
        await _fetch_dispute(conn, dispute_id, tenant_id)

        updates = {k: v for k, v in payload.model_dump().items() if v is not None}
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        set_clauses = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(updates.keys()))
        values = list(updates.values())
        row = await conn.fetchrow(
            f"UPDATE disputes SET {set_clauses}, updated_at = NOW() WHERE dispute_id = $1 RETURNING *",
            dispute_id, *values,
        )
    return dict(row)


@app.put("/api/v1/administration/disputes/{dispute_id}/resolve")
async def resolve_dispute(
    dispute_id: str,
    payload: ResolveDisputeSchema,
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
    db: asyncpg.Pool = Depends(_get_db),
):
    async with db.acquire() as conn:
        dispute = await _fetch_dispute(conn, dispute_id, tenant_id)

        row = await conn.fetchrow(
            """UPDATE disputes
               SET status = 'resolved', resolution = $1,
                   admin_notes = COALESCE($2, admin_notes),
                   refund_amount = COALESCE($3, refund_amount),
                   resolved_at = NOW(), updated_at = NOW()
               WHERE dispute_id = $4 AND tenant_id = $5
               RETURNING dispute_id, resolved_at""",
            payload.resolution, payload.admin_notes,
            Decimal(str(payload.refund_amount)) if payload.refund_amount is not None else None,
            dispute_id, tenant_id,
        )

        await conn.execute(
            """INSERT INTO dispute_messages (dispute_id, sender_type, sender_id, message)
               VALUES ($1, 'admin', $2, $3)""",
            dispute["id"], keycloak_id,
            f"Dispute resolved. Resolution: {payload.resolution}",
        )

    try:
        kafka_client.publish_dispute_event(
            event_type=DisputeEventTypes.DISPUTE_RESOLVED,
            dispute_id=dispute_id,
            tenant_id=tenant_id,
            status="resolved",
            metadata={"resolution": payload.resolution, "resolved_by": keycloak_id},
        )
    except Exception:
        pass

    return {
        "status": "resolved",
        "dispute_id": row["dispute_id"],
        "resolved_at": row["resolved_at"].isoformat() if row["resolved_at"] else None,
    }


# ── Dispute Messages ───────────────────────────────────────────────────────────

@app.get("/api/v1/disputes/{dispute_id}/messages")
async def get_messages(
    dispute_id: str,
    tenant_id: str = Header(..., alias="x-tenant-id"),
    db: asyncpg.Pool = Depends(_get_db),
):
    async with db.acquire() as conn:
        dispute = await _fetch_dispute(conn, dispute_id, tenant_id)
        rows = await conn.fetch(
            "SELECT * FROM dispute_messages WHERE dispute_id = $1 ORDER BY created_at ASC",
            dispute["id"],
        )
    return [dict(r) for r in rows]


@app.post("/api/v1/disputes/{dispute_id}/messages", status_code=201)
async def post_message(
    dispute_id: str,
    payload: CreateMessageSchema,
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
    db: asyncpg.Pool = Depends(_get_db),
):
    msg_text = payload.message or payload.content
    if not msg_text:
        raise HTTPException(status_code=422, detail="message or content is required")
    sender_id = payload.sender_id or keycloak_id

    async with db.acquire() as conn:
        dispute = await _fetch_dispute(conn, dispute_id, tenant_id)
        row = await conn.fetchrow(
            """INSERT INTO dispute_messages (dispute_id, sender_type, sender_id, message)
               VALUES ($1, $2, $3, $4) RETURNING *""",
            dispute["id"], payload.sender_type, sender_id, msg_text,
        )
    return dict(row)


# Legacy paths (kept for backwards compat with old clients)
@app.get("/disputes/{dispute_id}/messages")
async def get_messages_legacy(
    dispute_id: str,
    tenant_id: str = Header(..., alias="x-tenant-id"),
    db: asyncpg.Pool = Depends(_get_db),
):
    return await get_messages(dispute_id, tenant_id=tenant_id, db=db)


@app.post("/disputes/{dispute_id}/messages", status_code=201)
async def post_message_legacy(
    dispute_id: str,
    payload: CreateMessageSchema,
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
    db: asyncpg.Pool = Depends(_get_db),
):
    return await post_message(dispute_id, payload, tenant_id=tenant_id, keycloak_id=keycloak_id, db=db)


# ── Dispute Stats (legacy path) ────────────────────────────────────────────────

@app.get("/disputes/stats")
async def get_stats_legacy(
    tenant_id: str = Header(..., alias="x-tenant-id"),
    db: asyncpg.Pool = Depends(_get_db),
):
    return await get_stats_v1(tenant_id=tenant_id, db=db)


# ── Dispute Resolution Queue ───────────────────────────────────────────────────

@app.get("/api/v1/dispute-resolution")
async def get_dispute_resolution_queue(
    status: Optional[str] = None,
    dispute_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    tenant_id: str = Header(..., alias="x-tenant-id"),
    db: asyncpg.Pool = Depends(_get_db),
):
    conditions = ["tenant_id = $1", "status NOT IN ('resolved', 'closed')"]
    params = [tenant_id]

    if status:
        params.append(status)
        conditions.append(f"status = ${len(params)}")
    if dispute_type:
        params.append(dispute_type)
        conditions.append(f"dispute_type = ${len(params)}")

    params += [limit, offset]
    where = " AND ".join(conditions)
    rows = await db.fetch(
        f"""SELECT *,
               CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END AS priority_order
            FROM disputes WHERE {where}
            ORDER BY priority_order ASC, created_at ASC
            LIMIT ${len(params)-1} OFFSET ${len(params)}""",
        *params,
    )
    return [dict(r) for r in rows]


# ── Customer Dispute Portal ────────────────────────────────────────────────────

@app.get("/api/v1/customer-dispute-portal")
async def list_customer_portal_disputes(
    status: Optional[str] = None,
    tenant_id: str = Header(..., alias="x-tenant-id"),
    db: asyncpg.Pool = Depends(_get_db),
):
    if status:
        rows = await db.fetch(
            """SELECT cdp.*, d.status AS dispute_status, d.resolution
               FROM customer_dispute_portal cdp
               LEFT JOIN disputes d ON d.dispute_id = cdp.dispute_id
               WHERE cdp.tenant_id = $1 AND cdp.status = $2
               ORDER BY cdp.created_at DESC""",
            tenant_id, status,
        )
    else:
        rows = await db.fetch(
            """SELECT cdp.*, d.status AS dispute_status, d.resolution
               FROM customer_dispute_portal cdp
               LEFT JOIN disputes d ON d.dispute_id = cdp.dispute_id
               WHERE cdp.tenant_id = $1
               ORDER BY cdp.created_at DESC""",
            tenant_id,
        )
    return [dict(r) for r in rows]


@app.post("/api/v1/customer-dispute-portal", status_code=201)
async def create_customer_portal_dispute(
    payload: CustomerPortalDisputeSchema,
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
    db: asyncpg.Pool = Depends(_get_db),
):
    portal_id = f"CDP-{uuid.uuid4().hex[:10].upper()}"
    dispute_id = None

    async with db.acquire() as conn:
        if payload.transaction_reference and payload.reason:
            new_dispute_id = f"DSP-{uuid.uuid4().hex[:10].upper()}"
            title = f"{(payload.reason or 'customer').replace('_', ' ').title()} Dispute"
            d_row = await conn.fetchrow(
                """INSERT INTO disputes
                   (dispute_id, customer_id, transaction_id, dispute_type,
                    tenant_id, title, description, priority, status)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,'medium','open')
                   RETURNING dispute_id""",
                new_dispute_id, keycloak_id, payload.transaction_reference,
                payload.reason or "customer_portal",
                tenant_id, title,
                f"Customer portal submission. Evidence: {payload.evidence or 'none'}",
            )
            dispute_id = d_row["dispute_id"]

        row = await conn.fetchrow(
            """INSERT INTO customer_dispute_portal
               (portal_dispute_id, dispute_id, tenant_id, transaction_reference,
                reason, evidence, customer_email, status)
               VALUES ($1,$2,$3,$4,$5,$6,$7,'submitted')
               RETURNING *""",
            portal_id, dispute_id, tenant_id,
            payload.transaction_reference, payload.reason,
            payload.evidence, payload.customer_email,
        )
    return {"status": "submitted", "portal_dispute_id": portal_id, "dispute_id": dispute_id, **dict(row)}


# ── Dispute Mediation AI ───────────────────────────────────────────────────────

@app.get("/api/v1/dispute-mediation-ai")
async def list_mediation_recommendations(
    status: Optional[str] = None,
    tenant_id: str = Header(..., alias="x-tenant-id"),
    db: asyncpg.Pool = Depends(_get_db),
):
    conditions = ["tenant_id = $1", "status IN ('open', 'investigating')"]
    params = [tenant_id]
    if status:
        params.append(status)
        conditions.append(f"status = ${len(params)}")

    where = " AND ".join(conditions)
    rows = await db.fetch(
        f"SELECT * FROM disputes WHERE {where} ORDER BY created_at DESC LIMIT 50",
        *params,
    )

    recommendations = []
    for r in rows:
        rec, suggested_amount, confidence = _ai_recommendation(r["dispute_type"], r["amount"])
        recommendations.append({
            **dict(r),
            "recommendation": rec,
            "suggested_amount": suggested_amount,
            "confidence_score": confidence,
        })
    return recommendations


@app.post("/api/v1/dispute-mediation-ai/{dispute_id}/decision")
async def apply_mediation_decision(
    dispute_id: str,
    payload: dict,
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
    db: asyncpg.Pool = Depends(_get_db),
):
    recommendation = payload.get("recommendation", "")
    suggested_amount = payload.get("suggested_amount")
    note = payload.get("note", f"AI-mediated decision: {recommendation}")

    new_status = "resolved" if recommendation in ("full_refund", "partial_refund", "deny", "merchant_credit") else "investigating"

    async with db.acquire() as conn:
        dispute = await _fetch_dispute(conn, dispute_id, tenant_id)
        await conn.execute(
            """UPDATE disputes
               SET status = $1,
                   resolution = $2,
                   refund_amount = COALESCE($3, refund_amount),
                   admin_notes = COALESCE(admin_notes || ' | ', '') || $4,
                   resolved_at = CASE WHEN $1 = 'resolved' THEN NOW() ELSE resolved_at END,
                   updated_at = NOW()
               WHERE dispute_id = $5 AND tenant_id = $6""",
            new_status, recommendation,
            Decimal(str(suggested_amount)) if suggested_amount is not None else None,
            note, dispute_id, tenant_id,
        )
        await conn.execute(
            """INSERT INTO dispute_messages (dispute_id, sender_type, sender_id, message)
               VALUES ($1, 'system', 'mediation-ai', $2)""",
            dispute["id"], f"AI decision applied: {recommendation}. {note}",
        )
    return {"status": "applied", "dispute_id": dispute_id, "recommendation": recommendation}


# ── Dispute Auto Rules ─────────────────────────────────────────────────────────

@app.get("/api/v1/dispute-auto-rules")
async def list_auto_rules(
    tenant_id: str = Header(..., alias="x-tenant-id"),
    db: asyncpg.Pool = Depends(_get_db),
):
    rows = await db.fetch(
        "SELECT * FROM dispute_auto_rules WHERE tenant_id = $1 ORDER BY created_at DESC",
        tenant_id,
    )
    return [dict(r) for r in rows]


@app.post("/api/v1/dispute-auto-rules", status_code=201)
async def upsert_auto_rule(
    payload: CreateAutoRuleSchema,
    tenant_id: str = Header(..., alias="x-tenant-id"),
    db: asyncpg.Pool = Depends(_get_db),
):
    async with db.acquire() as conn:
        if payload.id:
            row = await conn.fetchrow(
                """UPDATE dispute_auto_rules
                   SET name=$1, dispute_type=$2, threshold_amount=$3, action=$4, active=$5, updated_at=NOW()
                   WHERE rule_id=$6 AND tenant_id=$7
                   RETURNING *""",
                payload.name, payload.dispute_type,
                Decimal(str(payload.threshold_amount)) if payload.threshold_amount is not None else None,
                payload.action, payload.active, payload.id, tenant_id,
            )
            if not row:
                raise HTTPException(status_code=404, detail="Rule not found")
        else:
            rule_id = f"RULE-{uuid.uuid4().hex[:8].upper()}"
            row = await conn.fetchrow(
                """INSERT INTO dispute_auto_rules
                   (rule_id, tenant_id, name, dispute_type, threshold_amount, action, active)
                   VALUES ($1,$2,$3,$4,$5,$6,$7)
                   RETURNING *""",
                rule_id, tenant_id, payload.name, payload.dispute_type,
                Decimal(str(payload.threshold_amount)) if payload.threshold_amount is not None else None,
                payload.action, payload.active,
            )
    return dict(row)


# ── Dispute Arbitration ────────────────────────────────────────────────────────

@app.get("/api/v1/arbitration")
async def list_arbitration_cases(
    status: Optional[str] = None,
    tenant_id: str = Header(..., alias="x-tenant-id"),
    db: asyncpg.Pool = Depends(_get_db),
):
    if status:
        rows = await db.fetch(
            """SELECT da.*, d.dispute_type, d.amount, d.description, d.customer_id
               FROM dispute_arbitration da
               JOIN disputes d ON d.dispute_id = da.dispute_id
               WHERE da.tenant_id = $1 AND da.stage = $2
               ORDER BY da.created_at DESC""",
            tenant_id, status,
        )
    else:
        rows = await db.fetch(
            """SELECT da.*, d.dispute_type, d.amount, d.description, d.customer_id
               FROM dispute_arbitration da
               JOIN disputes d ON d.dispute_id = da.dispute_id
               WHERE da.tenant_id = $1
               ORDER BY da.created_at DESC""",
            tenant_id,
        )
    return [dict(r) for r in rows]


@app.put("/api/v1/arbitration/{case_id}/ruling")
async def resolve_arbitration(
    case_id: str,
    payload: ArbitrationRulingSchema,
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
    db: asyncpg.Pool = Depends(_get_db),
):
    async with db.acquire() as conn:
        case = await conn.fetchrow(
            "SELECT * FROM dispute_arbitration WHERE case_id = $1 AND tenant_id = $2",
            case_id, tenant_id,
        )
        if not case:
            raise HTTPException(status_code=404, detail="Arbitration case not found")

        row = await conn.fetchrow(
            """UPDATE dispute_arbitration
               SET ruling=$1, refund_amount=$2, panel_notes=$3,
                   stage='ruled', ruled_at=NOW(), updated_at=NOW()
               WHERE case_id=$4 AND tenant_id=$5
               RETURNING *""",
            payload.ruling,
            Decimal(str(payload.refund_amount)) if payload.refund_amount is not None else None,
            payload.panel_notes, case_id, tenant_id,
        )

        # Mirror ruling to the underlying dispute
        new_dispute_status = "resolved" if payload.ruling != "dismissed" else "closed"
        await conn.execute(
            "UPDATE disputes SET status=$1, admin_notes=COALESCE(admin_notes||' | ','') || $2, updated_at=NOW() WHERE dispute_id=$3",
            new_dispute_status,
            f"Arbitration ruling: {payload.ruling}. {payload.panel_notes}",
            case["dispute_id"],
        )

    return {"status": "ruled", "case_id": case_id, "ruling": payload.ruling}


# ── Chargebacks ────────────────────────────────────────────────────────────────

@app.get("/api/v1/chargebacks")
async def list_chargebacks(
    status: Optional[str] = None,
    tenant_id: str = Header(..., alias="x-tenant-id"),
    db: asyncpg.Pool = Depends(_get_db),
):
    if status:
        rows = await db.fetch(
            "SELECT * FROM chargebacks WHERE tenant_id = $1 AND status = $2 ORDER BY created_at DESC",
            tenant_id, status,
        )
    else:
        rows = await db.fetch(
            "SELECT * FROM chargebacks WHERE tenant_id = $1 ORDER BY created_at DESC",
            tenant_id,
        )
    return [dict(r) for r in rows]


@app.put("/api/v1/chargebacks/{chargeback_id}/resolve")
async def resolve_chargeback(
    chargeback_id: str,
    payload: ResolveChargebackSchema,
    tenant_id: str = Header(..., alias="x-tenant-id"),
    db: asyncpg.Pool = Depends(_get_db),
):
    async with db.acquire() as conn:
        cb = await conn.fetchrow(
            "SELECT * FROM chargebacks WHERE chargeback_id = $1 AND tenant_id = $2",
            chargeback_id, tenant_id,
        )
        if not cb:
            raise HTTPException(status_code=404, detail="Chargeback not found")

        row = await conn.fetchrow(
            """UPDATE chargebacks
               SET outcome=$1, refund_amount=$2, status='resolved',
                   resolved_at=NOW(), updated_at=NOW()
               WHERE chargeback_id=$3 AND tenant_id=$4
               RETURNING *""",
            payload.outcome,
            Decimal(str(payload.refund_amount)) if payload.refund_amount is not None else None,
            chargeback_id, tenant_id,
        )
    return dict(row)


# ── Dispute Analytics ──────────────────────────────────────────────────────────

@app.get("/api/v1/dispute-analytics/resolution-metrics")
async def get_resolution_metrics(
    days: int = 30,
    tenant_id: str = Header(..., alias="x-tenant-id"),
    db: asyncpg.Pool = Depends(_get_db),
):
    row = await db.fetchrow(
        """SELECT
             COUNT(*) FILTER (WHERE status = 'resolved')                AS resolved,
             COUNT(*) FILTER (WHERE status IN ('open','investigating')) AS pending,
             COUNT(*)                                                    AS total,
             ROUND(
               100.0 * COUNT(*) FILTER (WHERE status = 'resolved') / NULLIF(COUNT(*), 0), 2
             )                                                           AS resolution_rate,
             ROUND(AVG(EXTRACT(EPOCH FROM (resolved_at - created_at))/3600)
               FILTER (WHERE resolved_at IS NOT NULL), 2)               AS avg_resolution_hours
           FROM disputes
           WHERE tenant_id = $1
             AND created_at >= NOW() - ($2 || ' days')::INTERVAL""",
        tenant_id, str(days),
    )
    return {
        "period_days": days,
        "resolved": row["resolved"],
        "pending": row["pending"],
        "total": row["total"],
        "resolution_rate": float(row["resolution_rate"] or 0),
        "avg_resolution_hours": float(row["avg_resolution_hours"] or 0),
    }


@app.get("/api/v1/dispute-analytics/refund-rates")
async def get_refund_rates(
    days: int = 30,
    tenant_id: str = Header(..., alias="x-tenant-id"),
    db: asyncpg.Pool = Depends(_get_db),
):
    row = await db.fetchrow(
        """SELECT
             COUNT(*) FILTER (WHERE refund_amount > 0)     AS disputes_with_refund,
             COUNT(*)                                       AS total,
             COALESCE(SUM(refund_amount), 0)               AS total_refunded,
             COALESCE(AVG(refund_amount) FILTER (WHERE refund_amount > 0), 0) AS avg_refund,
             ROUND(
               100.0 * COUNT(*) FILTER (WHERE refund_amount > 0) / NULLIF(COUNT(*), 0), 2
             )                                             AS refund_rate
           FROM disputes
           WHERE tenant_id = $1
             AND created_at >= NOW() - ($2 || ' days')::INTERVAL""",
        tenant_id, str(days),
    )
    return {
        "period_days": days,
        "disputes_with_refund": row["disputes_with_refund"],
        "total": row["total"],
        "total_refunded": float(row["total_refunded"]),
        "avg_refund": float(row["avg_refund"]),
        "refund_rate": float(row["refund_rate"] or 0),
    }


@app.get("/api/v1/dispute-analytics/sla-compliance")
async def get_sla_compliance(
    tenant_id: str = Header(..., alias="x-tenant-id"),
    db: asyncpg.Pool = Depends(_get_db),
):
    """SLA targets: high=24h, medium=72h, low=168h (7 days)."""
    rows = await db.fetch(
        """SELECT
             priority,
             COUNT(*) AS total,
             COUNT(*) FILTER (WHERE
               (priority = 'high'   AND EXTRACT(EPOCH FROM (COALESCE(resolved_at, NOW()) - created_at))/3600 <= 24) OR
               (priority = 'medium' AND EXTRACT(EPOCH FROM (COALESCE(resolved_at, NOW()) - created_at))/3600 <= 72) OR
               (priority = 'low'    AND EXTRACT(EPOCH FROM (COALESCE(resolved_at, NOW()) - created_at))/3600 <= 168)
             ) AS within_sla
           FROM disputes
           WHERE tenant_id = $1
           GROUP BY priority""",
        tenant_id,
    )
    by_priority = []
    total_total = 0
    total_within = 0
    for r in rows:
        total_total += r["total"]
        total_within += r["within_sla"]
        by_priority.append({
            "priority": r["priority"],
            "total": r["total"],
            "within_sla": r["within_sla"],
            "compliance_rate": round(100.0 * r["within_sla"] / r["total"], 2) if r["total"] else 100.0,
        })
    overall = round(100.0 * total_within / total_total, 2) if total_total else 100.0
    return {"overall_compliance": overall, "by_priority": by_priority}


@app.get("/api/v1/dispute-analytics/trend")
async def get_trend_data(
    weeks: int = 8,
    tenant_id: str = Header(..., alias="x-tenant-id"),
    db: asyncpg.Pool = Depends(_get_db),
):
    rows = await db.fetch(
        """SELECT
             DATE_TRUNC('week', created_at) AS week_start,
             COUNT(*)                        AS total,
             COUNT(*) FILTER (WHERE status = 'resolved') AS resolved
           FROM disputes
           WHERE tenant_id = $1
             AND created_at >= NOW() - ($2 || ' weeks')::INTERVAL
           GROUP BY week_start
           ORDER BY week_start ASC""",
        tenant_id, str(weeks),
    )
    data = [{"week": r["week_start"].isoformat(), "total": r["total"], "resolved": r["resolved"]} for r in rows]
    weekly_avg = round(sum(r["total"] for r in rows) / len(rows), 2) if rows else 0
    trend_direction = "stable"
    if len(data) >= 2:
        if data[-1]["total"] > data[-2]["total"]:
            trend_direction = "increasing"
        elif data[-1]["total"] < data[-2]["total"]:
            trend_direction = "decreasing"
    return {"weeks": weeks, "weekly_avg": weekly_avg, "trend_direction": trend_direction, "data": data}


@app.get("/api/v1/dispute-analytics/top-categories")
async def get_top_categories(
    limit: int = 10,
    days: int = 30,
    tenant_id: str = Header(..., alias="x-tenant-id"),
    db: asyncpg.Pool = Depends(_get_db),
):
    rows = await db.fetch(
        """SELECT
             COALESCE(category, dispute_type, 'uncategorized') AS category,
             COUNT(*)                                           AS count,
             COALESCE(SUM(amount), 0)                          AS total_amount,
             COUNT(*) FILTER (WHERE status = 'resolved')       AS resolved
           FROM disputes
           WHERE tenant_id = $1
             AND created_at >= NOW() - ($2 || ' days')::INTERVAL
           GROUP BY category
           ORDER BY count DESC
           LIMIT $3""",
        tenant_id, str(days), limit,
    )
    return [
        {
            "category": r["category"],
            "count": r["count"],
            "total_amount": float(r["total_amount"]),
            "resolved": r["resolved"],
            "resolution_rate": round(100.0 * r["resolved"] / r["count"], 2) if r["count"] else 0,
        }
        for r in rows
    ]


@app.get("/api/v1/dispute-analytics/summary")
async def get_analytics_summary(
    tenant_id: str = Header(..., alias="x-tenant-id"),
    db: Optional[asyncpg.Pool] = Depends(_get_db),
):
    if db is None:
        return {"total_disputes": 0, "open": 0, "in_progress": 0, "resolved": 0, "escalated": 0, "total_amount_disputed": 0.0, "total_refunded": 0.0, "avg_resolution_hours": 0.0, "sla_compliance": 100.0}
    row = await db.fetchrow(
        """SELECT
             COUNT(*)                                             AS total_disputes,
             COUNT(*) FILTER (WHERE status = 'open')            AS open,
             COUNT(*) FILTER (WHERE status = 'investigating')   AS in_progress,
             COUNT(*) FILTER (WHERE status = 'resolved')        AS resolved,
             COUNT(*) FILTER (WHERE status = 'escalated')       AS escalated,
             COALESCE(SUM(amount), 0)                           AS total_amount_disputed,
             COALESCE(SUM(refund_amount), 0)                    AS total_refunded,
             ROUND(AVG(EXTRACT(EPOCH FROM (resolved_at - created_at))/3600)
               FILTER (WHERE resolved_at IS NOT NULL), 2)       AS avg_resolution_hours
           FROM disputes
           WHERE tenant_id = $1""",
        tenant_id,
    )
    return {
        "total_disputes": row["total_disputes"],
        "open": row["open"],
        "in_progress": row["in_progress"],
        "resolved": row["resolved"],
        "escalated": row["escalated"],
        "total_amount_disputed": float(row["total_amount_disputed"]),
        "total_refunded": float(row["total_refunded"]),
        "avg_resolution_hours": float(row["avg_resolution_hours"] or 0),
        "sla_compliance": 100.0,  # populated separately via /sla-compliance
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8019")))
