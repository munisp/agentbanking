"""
Configurable Fee Schedule Engine
Per-merchant/per-provider fee tiers with percentage caps

Supports flexible fee structures like:
- 0.5% capped at 100 NGN
- 0.2% flat
- 0.1% with minimum fee
- Fixed fee per transaction
- Tiered volume-based fees
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum

import asyncpg
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import os
import uuid

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is required")

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Fee Schedule Engine", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in ALLOWED_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db_pool = None


class FeeType(str, Enum):
    PERCENTAGE = "percentage"
    PERCENTAGE_CAPPED = "percentage_capped"
    FLAT = "flat"
    TIERED = "tiered"


class TransactionType(str, Enum):
    POS_CASH_OUT = "pos_cash_out"
    POS_CARD = "pos_card"
    TRANSFER_INTRA = "transfer_intra"
    TRANSFER_INTER = "transfer_inter"
    BILLS_ELECTRICITY = "bills_electricity"
    BILLS_CABLE_TV = "bills_cable_tv"
    BILLS_WATER = "bills_water"
    BILLS_GOVERNMENT = "bills_government"
    TELCO_AIRTIME = "telco_airtime"
    TELCO_DATA = "telco_data"
    WALLET_TOPUP = "wallet_topup"


class FeeConfigCreate(BaseModel):
    merchant_id: Optional[str] = None
    provider_id: Optional[str] = None
    transaction_type: TransactionType
    fee_type: FeeType
    percentage: Optional[Decimal] = Field(None, ge=0, le=100)
    cap_amount: Optional[Decimal] = Field(None, ge=0)
    min_fee: Optional[Decimal] = Field(None, ge=0)
    flat_amount: Optional[Decimal] = Field(None, ge=0)
    tiers: Optional[List[Dict[str, Any]]] = None
    is_active: bool = True
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None
    priority: int = Field(default=0, ge=0)


class FeeConfigResponse(BaseModel):
    id: str
    merchant_id: Optional[str]
    provider_id: Optional[str]
    transaction_type: str
    fee_type: str
    percentage: Optional[str]
    cap_amount: Optional[str]
    min_fee: Optional[str]
    flat_amount: Optional[str]
    tiers: Optional[List[Dict[str, Any]]]
    is_active: bool
    effective_from: Optional[datetime]
    effective_to: Optional[datetime]
    priority: int
    created_at: datetime
    updated_at: datetime


class FeeCalculationRequest(BaseModel):
    merchant_id: str
    provider_id: Optional[str] = None
    transaction_type: TransactionType
    transaction_amount: Decimal = Field(..., gt=0)


class FeeCalculationResult(BaseModel):
    fee_amount: str
    fee_config_id: str
    fee_type: str
    percentage_applied: Optional[str] = None
    cap_applied: bool = False
    min_applied: bool = False
    tier_matched: Optional[str] = None
    breakdown: Dict[str, str]


@app.on_event("startup")
async def startup():
    global db_pool
    db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=5, max_size=20)
    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS fee_configurations (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                merchant_id VARCHAR(50),
                provider_id VARCHAR(50),
                transaction_type VARCHAR(30) NOT NULL,
                fee_type VARCHAR(20) NOT NULL,
                percentage DECIMAL(8,4),
                cap_amount DECIMAL(15,2),
                min_fee DECIMAL(15,2),
                flat_amount DECIMAL(15,2),
                tiers JSONB,
                is_active BOOLEAN DEFAULT TRUE,
                effective_from TIMESTAMP,
                effective_to TIMESTAMP,
                priority INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_fc_merchant ON fee_configurations(merchant_id);
            CREATE INDEX IF NOT EXISTS idx_fc_provider ON fee_configurations(provider_id);
            CREATE INDEX IF NOT EXISTS idx_fc_txn_type ON fee_configurations(transaction_type);
            CREATE INDEX IF NOT EXISTS idx_fc_active ON fee_configurations(is_active);
        """)
    logger.info("Fee Schedule Engine started")


@app.on_event("shutdown")
async def shutdown():
    if db_pool:
        await db_pool.close()


def _calculate_fee(config: dict, amount: Decimal) -> Dict[str, Any]:
    fee_type = config["fee_type"]
    result = {
        "fee_amount": Decimal("0"),
        "fee_config_id": str(config["id"]),
        "fee_type": fee_type,
        "cap_applied": False,
        "min_applied": False,
        "breakdown": {},
    }

    if fee_type == FeeType.FLAT:
        fee = Decimal(str(config["flat_amount"] or 0))
        result["fee_amount"] = fee
        result["breakdown"]["flat_fee"] = str(fee)

    elif fee_type == FeeType.PERCENTAGE:
        pct = Decimal(str(config["percentage"] or 0))
        fee = (amount * pct / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        min_fee = Decimal(str(config["min_fee"] or 0))
        if min_fee > 0 and fee < min_fee:
            fee = min_fee
            result["min_applied"] = True
        result["fee_amount"] = fee
        result["percentage_applied"] = str(pct)
        result["breakdown"]["percentage"] = str(pct)
        result["breakdown"]["calculated_fee"] = str(fee)

    elif fee_type == FeeType.PERCENTAGE_CAPPED:
        pct = Decimal(str(config["percentage"] or 0))
        cap = Decimal(str(config["cap_amount"] or 0))
        min_fee = Decimal(str(config["min_fee"] or 0))
        fee = (amount * pct / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        result["breakdown"]["percentage"] = str(pct)
        result["breakdown"]["uncapped_fee"] = str(fee)
        if cap > 0 and fee > cap:
            fee = cap
            result["cap_applied"] = True
        if min_fee > 0 and fee < min_fee:
            fee = min_fee
            result["min_applied"] = True
        result["fee_amount"] = fee
        result["percentage_applied"] = str(pct)
        result["breakdown"]["cap"] = str(cap)
        result["breakdown"]["final_fee"] = str(fee)

    elif fee_type == FeeType.TIERED:
        tiers = config.get("tiers") or []
        fee = Decimal("0")
        matched_tier = None
        for tier in sorted(tiers, key=lambda t: float(t.get("min_amount", 0))):
            tier_min = Decimal(str(tier.get("min_amount", 0)))
            tier_max = Decimal(str(tier.get("max_amount", 999999999)))
            if tier_min <= amount <= tier_max:
                matched_tier = f"{tier_min}-{tier_max}"
                tier_type = tier.get("type", "percentage")
                if tier_type == "flat":
                    fee = Decimal(str(tier.get("amount", 0)))
                else:
                    pct = Decimal(str(tier.get("percentage", 0)))
                    fee = (amount * pct / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    tier_cap = Decimal(str(tier.get("cap", 0)))
                    if tier_cap > 0 and fee > tier_cap:
                        fee = tier_cap
                        result["cap_applied"] = True
                    result["percentage_applied"] = str(pct)
                break
        result["fee_amount"] = fee
        result["tier_matched"] = matched_tier
        result["breakdown"]["tier"] = matched_tier or "none"
        result["breakdown"]["fee"] = str(fee)

    return result


async def _find_applicable_config(
    conn: asyncpg.Connection,
    merchant_id: str,
    provider_id: Optional[str],
    transaction_type: str,
) -> Optional[dict]:
    now = datetime.utcnow()

    query = """
        SELECT * FROM fee_configurations
        WHERE transaction_type = $1
          AND is_active = TRUE
          AND (effective_from IS NULL OR effective_from <= $2)
          AND (effective_to IS NULL OR effective_to >= $2)
          AND (
              (merchant_id = $3 AND provider_id = $4)
              OR (merchant_id = $3 AND provider_id IS NULL)
              OR (merchant_id IS NULL AND provider_id = $4)
              OR (merchant_id IS NULL AND provider_id IS NULL)
          )
        ORDER BY
            CASE
                WHEN merchant_id IS NOT NULL AND provider_id IS NOT NULL THEN 0
                WHEN merchant_id IS NOT NULL AND provider_id IS NULL THEN 1
                WHEN merchant_id IS NULL AND provider_id IS NOT NULL THEN 2
                ELSE 3
            END,
            priority DESC
        LIMIT 1
    """
    row = await conn.fetchrow(query, transaction_type, now, merchant_id, provider_id)
    if row:
        result = dict(row)
        if result.get("tiers") and isinstance(result["tiers"], str):
            import json
            result["tiers"] = json.loads(result["tiers"])
        return result
    return None


@app.post("/fee-configs", response_model=FeeConfigResponse)
async def create_fee_config(config: FeeConfigCreate):
    async with db_pool.acquire() as conn:
        import json
        tiers_json = json.dumps(config.tiers) if config.tiers else None
        row = await conn.fetchrow(
            """
            INSERT INTO fee_configurations (
                merchant_id, provider_id, transaction_type, fee_type,
                percentage, cap_amount, min_fee, flat_amount, tiers,
                is_active, effective_from, effective_to, priority
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, $10, $11, $12, $13)
            RETURNING *
            """,
            config.merchant_id, config.provider_id, config.transaction_type.value,
            config.fee_type.value, config.percentage, config.cap_amount,
            config.min_fee, config.flat_amount, tiers_json,
            config.is_active, config.effective_from, config.effective_to,
            config.priority,
        )
        return _row_to_response(row)


@app.get("/fee-configs", response_model=List[FeeConfigResponse])
async def list_fee_configs(
    merchant_id: Optional[str] = None,
    provider_id: Optional[str] = None,
    transaction_type: Optional[str] = None,
    active_only: bool = True,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
):
    async with db_pool.acquire() as conn:
        query = "SELECT * FROM fee_configurations WHERE 1=1"
        params: list = []
        idx = 1
        if merchant_id:
            query += f" AND merchant_id = ${idx}"
            params.append(merchant_id)
            idx += 1
        if provider_id:
            query += f" AND provider_id = ${idx}"
            params.append(provider_id)
            idx += 1
        if transaction_type:
            query += f" AND transaction_type = ${idx}"
            params.append(transaction_type)
            idx += 1
        if active_only:
            query += " AND is_active = TRUE"
        query += f" ORDER BY priority DESC, created_at DESC LIMIT ${idx} OFFSET ${idx + 1}"
        params.extend([limit, offset])
        rows = await conn.fetch(query, *params)
        return [_row_to_response(r) for r in rows]


@app.get("/fee-configs/{config_id}", response_model=FeeConfigResponse)
async def get_fee_config(config_id: str):
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM fee_configurations WHERE id = $1", uuid.UUID(config_id)
        )
        if not row:
            raise HTTPException(status_code=404, detail="Fee config not found")
        return _row_to_response(row)


@app.put("/fee-configs/{config_id}", response_model=FeeConfigResponse)
async def update_fee_config(config_id: str, config: FeeConfigCreate):
    async with db_pool.acquire() as conn:
        import json
        tiers_json = json.dumps(config.tiers) if config.tiers else None
        row = await conn.fetchrow(
            """
            UPDATE fee_configurations
            SET merchant_id = $1, provider_id = $2, transaction_type = $3,
                fee_type = $4, percentage = $5, cap_amount = $6, min_fee = $7,
                flat_amount = $8, tiers = $9::jsonb, is_active = $10,
                effective_from = $11, effective_to = $12, priority = $13,
                updated_at = NOW()
            WHERE id = $14 RETURNING *
            """,
            config.merchant_id, config.provider_id, config.transaction_type.value,
            config.fee_type.value, config.percentage, config.cap_amount,
            config.min_fee, config.flat_amount, tiers_json,
            config.is_active, config.effective_from, config.effective_to,
            config.priority, uuid.UUID(config_id),
        )
        if not row:
            raise HTTPException(status_code=404, detail="Fee config not found")
        return _row_to_response(row)


@app.delete("/fee-configs/{config_id}")
async def deactivate_fee_config(config_id: str):
    async with db_pool.acquire() as conn:
        await conn.execute(
            "UPDATE fee_configurations SET is_active = FALSE, updated_at = NOW() WHERE id = $1",
            uuid.UUID(config_id),
        )
        return {"status": "deactivated", "id": config_id}


@app.post("/calculate-fee", response_model=FeeCalculationResult)
async def calculate_fee(request: FeeCalculationRequest):
    async with db_pool.acquire() as conn:
        config = await _find_applicable_config(
            conn, request.merchant_id, request.provider_id, request.transaction_type.value
        )
        if not config:
            raise HTTPException(
                status_code=404,
                detail=f"No fee configuration found for merchant={request.merchant_id}, "
                       f"type={request.transaction_type.value}",
            )
        result = _calculate_fee(config, request.transaction_amount)
        return FeeCalculationResult(
            fee_amount=str(result["fee_amount"]),
            fee_config_id=result["fee_config_id"],
            fee_type=result["fee_type"],
            percentage_applied=result.get("percentage_applied"),
            cap_applied=result["cap_applied"],
            min_applied=result["min_applied"],
            tier_matched=result.get("tier_matched"),
            breakdown={k: str(v) for k, v in result["breakdown"].items()},
        )


@app.post("/calculate-fee/batch")
async def calculate_fee_batch(requests: List[FeeCalculationRequest]):
    results = []
    async with db_pool.acquire() as conn:
        for req in requests:
            config = await _find_applicable_config(
                conn, req.merchant_id, req.provider_id, req.transaction_type.value
            )
            if config:
                result = _calculate_fee(config, req.transaction_amount)
                results.append({
                    "merchant_id": req.merchant_id,
                    "transaction_type": req.transaction_type.value,
                    "transaction_amount": str(req.transaction_amount),
                    "fee_amount": str(result["fee_amount"]),
                    "fee_config_id": result["fee_config_id"],
                    "fee_type": result["fee_type"],
                })
            else:
                results.append({
                    "merchant_id": req.merchant_id,
                    "transaction_type": req.transaction_type.value,
                    "transaction_amount": str(req.transaction_amount),
                    "fee_amount": "0",
                    "fee_config_id": None,
                    "fee_type": "none",
                    "error": "No fee configuration found",
                })
    return results


def _row_to_response(row: asyncpg.Record) -> FeeConfigResponse:
    import json
    tiers = row["tiers"]
    if tiers and isinstance(tiers, str):
        tiers = json.loads(tiers)
    return FeeConfigResponse(
        id=str(row["id"]),
        merchant_id=row["merchant_id"],
        provider_id=row["provider_id"],
        transaction_type=row["transaction_type"],
        fee_type=row["fee_type"],
        percentage=str(row["percentage"]) if row["percentage"] is not None else None,
        cap_amount=str(row["cap_amount"]) if row["cap_amount"] is not None else None,
        min_fee=str(row["min_fee"]) if row["min_fee"] is not None else None,
        flat_amount=str(row["flat_amount"]) if row["flat_amount"] is not None else None,
        tiers=tiers,
        is_active=row["is_active"],
        effective_from=row["effective_from"],
        effective_to=row["effective_to"],
        priority=row["priority"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@app.get("/health")
async def health_check():
    healthy = True
    details = {"service": "fee-schedule-engine", "database": "unknown"}
    try:
        async with db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        details["database"] = "connected"
    except Exception:
        details["database"] = "disconnected"
        healthy = False
    details["status"] = "healthy" if healthy else "degraded"
    return details


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8106)
