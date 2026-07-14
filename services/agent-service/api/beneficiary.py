from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
import uuid

from database import get_session

beneficiary_router = APIRouter()


class BeneficiaryBody(BaseModel):
    name: str = ""
    account_number: str = ""
    bank_name: str = ""
    bank_code: str = ""
    phone: str = ""
    nickname: str = ""
    is_starred: bool = False


def _serialize(row) -> dict:
    d = dict(row)
    for k, v in d.items():
        if hasattr(v, "isoformat"):
            d[k] = v.isoformat()
    return d


@beneficiary_router.get("/api/v1/beneficiaries/{agent_keycloak_id}")
def list_beneficiaries(
    agent_keycloak_id: str,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
):
    rows = db.execute(
        text(
            "SELECT * FROM agent_beneficiaries "
            "WHERE agent_keycloak_id = :kid AND tenant_id = :tid "
            "ORDER BY is_starred DESC, created_at DESC"
        ),
        {"kid": agent_keycloak_id, "tid": tenant_id},
    ).mappings().all()
    return {"beneficiaries": [_serialize(r) for r in rows]}


@beneficiary_router.post("/api/v1/beneficiaries/{agent_keycloak_id}", status_code=201)
def create_beneficiary(
    agent_keycloak_id: str,
    body: BeneficiaryBody,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
):
    data = body.model_dump()
    row = db.execute(
        text(
            "INSERT INTO agent_beneficiaries "
            "(id, agent_keycloak_id, tenant_id, name, account_number, bank_name, bank_code, phone, nickname, is_starred) "
            "VALUES (:id, :kid, :tid, :name, :account_number, :bank_name, :bank_code, :phone, :nickname, :is_starred) "
            "RETURNING *"
        ),
        {"id": str(uuid.uuid4()), "kid": agent_keycloak_id, "tid": tenant_id, **data},
    ).mappings().first()
    db.commit()
    return _serialize(row)


@beneficiary_router.put("/api/v1/beneficiaries/{agent_keycloak_id}/{beneficiary_id}")
def update_beneficiary(
    agent_keycloak_id: str,
    beneficiary_id: str,
    body: BeneficiaryBody,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
):
    data = body.model_dump()
    row = db.execute(
        text(
            "UPDATE agent_beneficiaries SET "
            "name=:name, account_number=:account_number, bank_name=:bank_name, "
            "bank_code=:bank_code, phone=:phone, nickname=:nickname, is_starred=:is_starred, "
            "updated_at=NOW() "
            "WHERE id=:id AND agent_keycloak_id=:kid AND tenant_id=:tid "
            "RETURNING *"
        ),
        {"id": beneficiary_id, "kid": agent_keycloak_id, "tid": tenant_id, **data},
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Beneficiary not found")
    db.commit()
    return _serialize(row)


@beneficiary_router.delete("/api/v1/beneficiaries/{agent_keycloak_id}/{beneficiary_id}", status_code=204)
def delete_beneficiary(
    agent_keycloak_id: str,
    beneficiary_id: str,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
):
    result = db.execute(
        text(
            "DELETE FROM agent_beneficiaries "
            "WHERE id=:id AND agent_keycloak_id=:kid AND tenant_id=:tid"
        ),
        {"id": beneficiary_id, "kid": agent_keycloak_id, "tid": tenant_id},
    )
    db.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Beneficiary not found")
