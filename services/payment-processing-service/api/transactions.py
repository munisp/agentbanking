from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from typing import Optional
import uuid

from database import get_session
from fastapi import Depends
from sqlalchemy.orm import Session

transactions_router = APIRouter()


class TransactionCreate(BaseModel):
    amount: float = 0
    currency: str = "NGN"
    channel: str = ""
    type: str = ""
    description: str = ""
    provider_id: str = ""
    insurance_type: str = ""
    plan_id: str = ""
    customer_phone: str = ""
    policy_number: str = ""
    reference: str = ""
    # NF-FF-33: status is server-controlled. Callers may not set it; any
    # supplied value is validated against the enum and rejected unless it is
    # exactly "pending" (the only state a newly created record may have).
    status: Optional[str] = None
    metadata: dict = {}


ALLOWED_TRANSACTION_STATUSES = frozenset({"pending", "success", "failed", "reversed"})


def _row(r) -> dict:
    d = dict(r)
    for k, v in d.items():
        if hasattr(v, "isoformat"):
            d[k] = v.isoformat()
    return d


@transactions_router.get("/api/v1/transactions")
def list_transactions(
    type: Optional[str] = None,
    channel: Optional[str] = None,
    limit: int = 20,
    page: int = 1,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
):
    offset = (page - 1) * limit
    filters = ["tenant_id = :tid"]
    params: dict = {"tid": tenant_id, "limit": limit, "offset": offset}
    if type:
        filters.append("type = :type")
        params["type"] = type
    if channel:
        filters.append("channel = :channel")
        params["channel"] = channel
    where = " AND ".join(filters)
    rows = db.execute(
        text(f"SELECT * FROM payment_transactions WHERE {where} ORDER BY created_at DESC LIMIT :limit OFFSET :offset"),
        params,
    ).mappings().all()
    total = db.execute(
        text(f"SELECT COUNT(*) FROM payment_transactions WHERE {where}"),
        {k: v for k, v in params.items() if k not in ("limit", "offset")},
    ).scalar()
    return {"transactions": [_row(r) for r in rows], "total": total, "page": page, "limit": limit}


@transactions_router.post("/api/v1/transactions", status_code=201)
def create_transaction(
    body: TransactionCreate,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
):
    # NF-FF-33: enum-lock and reject caller status overrides; new records
    # always enter as "pending" and transition only via server-side flows.
    if body.status is not None:
        requested = str(body.status).strip().lower()
        if requested not in ALLOWED_TRANSACTION_STATUSES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid transaction status '{body.status}'.",
            )
        if requested != "pending":
            raise HTTPException(
                status_code=400,
                detail="Transaction status is server-controlled; new transactions are always 'pending'.",
            )

    ref = body.reference or str(uuid.uuid4())

    # NF-FF-33: dedupe on reference — a reference may only be recorded once
    # per tenant; replays get 409 instead of a duplicate row.
    existing = db.execute(
        text(
            "SELECT id FROM payment_transactions WHERE tenant_id = :tid AND reference = :ref"
        ),
        {"tid": tenant_id, "ref": ref},
    ).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail="A transaction with this reference already exists.",
        )

    row = db.execute(
        text("""
            INSERT INTO payment_transactions
              (id, tenant_id, agent_keycloak_id, amount, currency, channel, type,
               description, provider_id, insurance_type, plan_id, customer_phone,
               policy_number, reference, status)
            VALUES
              (:id, :tid, :kid, :amount, :currency, :channel, :type,
               :description, :provider_id, :insurance_type, :plan_id, :customer_phone,
               :policy_number, :reference, :status)
            RETURNING *
        """),
        {
            "id": str(uuid.uuid4()),
            "tid": tenant_id,
            "kid": keycloak_id,
            "amount": body.amount,
            "currency": body.currency,
            "channel": body.channel,
            "type": body.type,
            "description": body.description,
            "provider_id": body.provider_id,
            "insurance_type": body.insurance_type,
            "plan_id": body.plan_id,
            "customer_phone": body.customer_phone,
            "policy_number": body.policy_number,
            "reference": ref,
            "status": "pending",
        },
    ).mappings().first()
    db.commit()
    return _row(row)
