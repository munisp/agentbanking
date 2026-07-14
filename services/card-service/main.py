"""Card Management Service"""

import base64
import hmac
import os
import secrets
import hashlib

import bcrypt
import uvicorn
import asyncpg
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from datetime import datetime, timedelta, timezone
from enum import Enum
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from middlewares import RequiredHeadersMiddleware
from utils.errors import raise_http_exception_handler
from utils.kafka_instance import KafkaClientInstance
from utils.kafka_client import CardEventTypes
from utils.coa_client import CoAClient

load_dotenv()

app = FastAPI(title="54agent Card Service", version="1.0.0")

coa_client = CoAClient()

app.add_middleware(
    RequiredHeadersMiddleware,
    required_headers=["x-tenant-id", "x-keycloak-id"],
    exclude_prefixes=["/health", "/dapr"],
)

_allowed_origins = [
    o.strip()
    for o in os.getenv("ALLOWED_ORIGINS", "").split(",")
    if o.strip()
] or ["http://localhost:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization", "x-tenant-id", "x-keycloak-id"],
)

db_pool = None
_card_enc_key: bytes = b""
_card_hmac_key: bytes = b""


# ---------------------------------------------------------------------------
# Cryptographic helpers
# ---------------------------------------------------------------------------

def _encrypt_pan(pan: str) -> str:
    """AES-256-GCM encrypt a PAN. Returns base64(nonce‖ciphertext)."""
    aesgcm = AESGCM(_card_enc_key)
    nonce = secrets.token_bytes(12)
    ct = aesgcm.encrypt(nonce, pan.encode(), None)
    return base64.b64encode(nonce + ct).decode()


def _decrypt_pan(encrypted: str) -> str:
    """Decrypt an AES-256-GCM encrypted PAN."""
    data = base64.b64decode(encrypted)
    nonce, ct = data[:12], data[12:]
    return AESGCM(_card_enc_key).decrypt(nonce, ct, None).decode()


def _pan_search_hash(pan: str) -> str:
    """HMAC-SHA256 of PAN — used for equality lookup without exposing plaintext."""
    return hmac.new(_card_hmac_key, pan.encode(), hashlib.sha256).hexdigest()


def _hash_pin(pin: str) -> str:
    return bcrypt.hashpw(pin.encode(), bcrypt.gensalt(rounds=12)).decode()


def _verify_pin(pin: str, pin_hash: str) -> bool:
    return bcrypt.checkpw(pin.encode(), pin_hash.encode())


def _luhn_check_digit(partial: str) -> int:
    total = 0
    for i, d in enumerate(reversed(partial)):
        n = int(d)
        if i % 2 == 0:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return (10 - total % 10) % 10


def _generate_card_number() -> str:
    """Generate a 16-digit Visa PAN using CSPRNG with Luhn check digit."""
    partial = "4" + "".join(str(secrets.randbelow(10)) for _ in range(14))
    return partial + str(_luhn_check_digit(partial))


def _generate_cvv() -> str:
    """Generate a 3-digit CVV using CSPRNG."""
    return f"{secrets.randbelow(900) + 100:03d}"


# ---------------------------------------------------------------------------
# Models / Enums
# ---------------------------------------------------------------------------

class CardType(str, Enum):
    DEBIT = "debit"
    CREDIT = "credit"
    VIRTUAL = "virtual"


class CardStatus(str, Enum):
    ACTIVE = "active"
    BLOCKED = "blocked"
    FROZEN = "frozen"
    LOST = "lost"


class CardCreation(BaseModel):
    account_id: str
    card_type: CardType
    name_on_card: str


class CardCreationAdmin(BaseModel):
    account_id: str
    card_type: CardType
    name_on_card: str
    customer_id: str


class SetPinSchema(BaseModel):
    pin: str


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup():
    global db_pool, _card_enc_key, _card_hmac_key

    raw_enc = os.environ.get("CARD_ENCRYPTION_KEY")
    if not raw_enc:
        raise RuntimeError("CARD_ENCRYPTION_KEY environment variable is required (32 bytes, base64-encoded)")
    _card_enc_key = base64.b64decode(raw_enc)
    if len(_card_enc_key) != 32:
        raise RuntimeError("CARD_ENCRYPTION_KEY must decode to exactly 32 bytes")

    raw_hmac = os.environ.get("CARD_HMAC_KEY")
    if not raw_hmac:
        raise RuntimeError("CARD_HMAC_KEY environment variable is required (32 bytes, base64-encoded)")
    _card_hmac_key = base64.b64decode(raw_hmac)
    if len(_card_hmac_key) < 32:
        raise RuntimeError("CARD_HMAC_KEY must decode to at least 32 bytes")

    db_pool = await asyncpg.create_pool(
        host=os.getenv("DB_HOST", "postgres"),
        port=os.getenv("DB_PORT", "5432"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "postgres"),
        database=os.getenv("DB_NAME", "card_db"),
        min_size=5,
        max_size=20,
    )

    async with db_pool.acquire() as conn:
        # PCI-DSS: PAN stored encrypted; CVV never stored; PIN uses bcrypt.
        # Step 1: create table for fresh deployments (no-op if it already exists).
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS cards (
                id                      SERIAL PRIMARY KEY,
                tenant_id               VARCHAR(50)  NOT NULL,
                card_id                 VARCHAR(50)  UNIQUE NOT NULL,
                card_number_encrypted   TEXT,
                card_number_last4       VARCHAR(4),
                card_number_search_hash VARCHAR(64),
                card_type               VARCHAR(20)  NOT NULL,
                customer_id             VARCHAR(50)  NOT NULL,
                account_id              VARCHAR(50)  NOT NULL,
                name_on_card            VARCHAR(255) NOT NULL,
                expiry_date             DATE         NOT NULL,
                pin_hash                VARCHAR(255),
                status                  VARCHAR(20)  DEFAULT 'active',
                daily_limit             DECIMAL(15,2) DEFAULT 500000,
                monthly_limit           DECIMAL(15,2) DEFAULT 5000000,
                daily_spent             DECIMAL(15,2) DEFAULT 0,
                monthly_spent           DECIMAL(15,2) DEFAULT 0,
                created_at              TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
            );
        """)
        # Step 2: migrate existing deployments — remove old plaintext columns first.
        await conn.execute("ALTER TABLE cards DROP COLUMN IF EXISTS card_number")
        await conn.execute("ALTER TABLE cards DROP COLUMN IF EXISTS cvv")
        # Step 3: add new encrypted columns (nullable so existing rows are not rejected).
        await conn.execute("ALTER TABLE cards ADD COLUMN IF NOT EXISTS card_number_encrypted TEXT")
        await conn.execute("ALTER TABLE cards ADD COLUMN IF NOT EXISTS card_number_last4 VARCHAR(4)")
        await conn.execute("ALTER TABLE cards ADD COLUMN IF NOT EXISTS card_number_search_hash VARCHAR(64)")
        # Step 4: create indexes now that the columns are guaranteed to exist.
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_cards_number_hash ON cards(card_number_search_hash)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_cards_customer    ON cards(customer_id)")


@app.on_event("shutdown")
async def shutdown():
    if db_pool:
        await db_pool.close()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "card-service"}


@app.post("/api/v1/cards/issue")
async def issue_card(
    card: CardCreation,
    db=Depends(lambda: db_pool),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    customer_id: str = Header(..., alias="x-keycloak-id"),
):
    try:
        card_id = f"CRD{int(datetime.now(timezone.utc).timestamp())}{secrets.token_hex(4)}"
        pan = _generate_card_number()
        cvv = _generate_cvv()  # returned once; never stored
        expiry_date = datetime.now(timezone.utc).date() + timedelta(days=365 * 3)

        pan_encrypted = _encrypt_pan(pan)
        pan_last4 = pan[-4:]
        pan_hash = _pan_search_hash(pan)

        async with db.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO cards (
                    card_id, card_number_encrypted, card_number_last4, card_number_search_hash,
                    card_type, customer_id, account_id, name_on_card, expiry_date, tenant_id
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """,
                card_id, pan_encrypted, pan_last4, pan_hash,
                card.card_type.value, customer_id, card.account_id,
                card.name_on_card, expiry_date, tenant_id,
            )

        KafkaClientInstance.publish_card_event(
            event_type=CardEventTypes.CARD_ISSUED,
            card_id=card_id,
            tenant_id=tenant_id,
            status="active",
            metadata={
                # PAN and CVV are NOT included in event metadata (PCI-DSS)
                "card_last4": pan_last4,
                "card_type": card.card_type.value,
                "customer_id": customer_id,
                "account_id": card.account_id,
                "name_on_card": card.name_on_card,
                "expiry_date": str(expiry_date),
            },
        )

        return {
            "status": "issued",
            "card_id": card_id,
            "card_number": pan,       # Full PAN shown ONCE at issuance — never stored
            "card_last4": pan_last4,
            "cvv": cvv,               # CVV shown ONCE at issuance — never stored (PCI-DSS)
            "expiry_date": expiry_date,
            "message": "Record your card details securely. PAN and CVV will not be shown again.",
        }
    except Exception as e:
        raise_http_exception_handler(500, f"Failed to issue card: {str(e)}", "CRD-ISSUE-5001")


@app.post("/api/v1/cards/issue/admin")
async def issue_card_admin(
    card: CardCreationAdmin,
    db=Depends(lambda: db_pool),
    tenant_id: str = Header(..., alias="x-tenant-id"),
):
    try:
        card_id = f"CRD{int(datetime.now(timezone.utc).timestamp())}{secrets.token_hex(4)}"
        pan = _generate_card_number()
        cvv = _generate_cvv()  # returned once; never stored
        expiry_date = datetime.now(timezone.utc).date() + timedelta(days=365 * 3)

        pan_encrypted = _encrypt_pan(pan)
        pan_last4 = pan[-4:]
        pan_hash = _pan_search_hash(pan)

        async with db.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO cards (
                    card_id, card_number_encrypted, card_number_last4, card_number_search_hash,
                    card_type, customer_id, account_id, name_on_card, expiry_date, tenant_id
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """,
                card_id, pan_encrypted, pan_last4, pan_hash,
                card.card_type.value, card.customer_id, card.account_id,
                card.name_on_card, expiry_date, tenant_id,
            )

        KafkaClientInstance.publish_card_event(
            event_type=CardEventTypes.CARD_ISSUED,
            card_id=card_id,
            tenant_id=tenant_id,
            status="active",
            metadata={
                "card_last4": pan_last4,
                "card_type": card.card_type.value,
                "customer_id": card.customer_id,
                "account_id": card.account_id,
                "name_on_card": card.name_on_card,
                "expiry_date": str(expiry_date),
            },
        )

        return {
            "status": "issued",
            "card_id": card_id,
            "card_number": pan,
            "card_last4": pan_last4,
            "cvv": cvv,
            "expiry_date": expiry_date,
            "message": "Record your card details securely. PAN and CVV will not be shown again.",
        }
    except Exception as e:
        raise_http_exception_handler(500, f"Failed to issue card: {str(e)}", "CRD-ISSUE-ADMIN-5001")


@app.get("/api/v1/cards/tenant")
async def list_tenant_cards(
    db=Depends(lambda: db_pool),
    tenant_id: str = Header(..., alias="x-tenant-id"),
):
    try:
        async with db.acquire() as conn:
            rows = await conn.fetch(
                """SELECT card_id, card_number_last4, card_type, customer_id, account_id,
                          name_on_card, expiry_date, status, tenant_id, created_at
                   FROM cards WHERE tenant_id = $1 ORDER BY created_at DESC""",
                tenant_id,
            )
        cards = [dict(row) for row in rows]
        return {"cards": cards, "total": len(cards)}
    except Exception as e:
        raise_http_exception_handler(500, f"Failed to fetch cards: {str(e)}", "CRD-LIST-5001")


@app.get("/api/v1/cards/customer")
async def list_customer_cards(
    db=Depends(lambda: db_pool),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    customer_id: str = Header(..., alias="x-keycloak-id"),
):
    async with db.acquire() as conn:
        rows = await conn.fetch(
            """SELECT card_id, card_number_last4, card_type, customer_id, account_id,
                      name_on_card, expiry_date, status, created_at
               FROM cards WHERE customer_id = $1 AND tenant_id = $2 ORDER BY created_at DESC""",
            customer_id,
            tenant_id,
        )
    cards = [dict(row) for row in rows]
    return {"customer_id": customer_id, "cards": cards, "total": len(cards)}


@app.get("/api/v1/cards/lookup")
async def lookup_card_by_number(
    card_number: str,
    db=Depends(lambda: db_pool),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    customer_id: str = Header(..., alias="x-keycloak-id"),
):
    """Lookup a card by its full PAN. Ownership-scoped: only the card's owner can look it up."""
    try:
        search_hash = _pan_search_hash(card_number)

        async with db.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT card_id, card_number_last4, card_type, customer_id, account_id,
                          name_on_card, expiry_date, status, tenant_id, created_at
                   FROM cards
                   WHERE tenant_id = $1 AND card_number_search_hash = $2 AND customer_id = $3""",
                tenant_id,
                search_hash,
                customer_id,
            )

        if not row:
            raise HTTPException(status_code=404, detail="Card not found.")

        return {"message": "success", "card": dict(row)}
    except HTTPException:
        raise
    except Exception as e:
        raise_http_exception_handler(500, f"Failed to lookup card: {str(e)}", "CRD-LOOKUP-5001")


@app.post("/api/v1/cards/{card_id}/set-pin")
async def set_pin(
    card_id: str,
    payload: SetPinSchema,
    db=Depends(lambda: db_pool),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    customer_id: str = Header(..., alias="x-keycloak-id"),
):
    try:
        if len(payload.pin) != 4 or not payload.pin.isdigit():
            raise HTTPException(status_code=400, detail="PIN must be exactly 4 digits.")

        pin_hash = _hash_pin(payload.pin)

        async with db.acquire() as conn:
            result = await conn.execute(
                "UPDATE cards SET pin_hash = $1 WHERE card_id = $2 AND customer_id = $3 AND tenant_id = $4",
                pin_hash, card_id, customer_id, tenant_id,
            )

        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Card not found.")

        return {"message": "success", "card_id": card_id}
    except HTTPException:
        raise
    except Exception as e:
        raise_http_exception_handler(500, f"Failed to set PIN: {str(e)}", "CRD-SETPIN-5001")


@app.post("/api/v1/cards/{card_id}/freeze")
async def freeze_card(
    card_id: str,
    db=Depends(lambda: db_pool),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    customer_id: str = Header(..., alias="x-keycloak-id"),
):
    try:
        async with db.acquire() as conn:
            result = await conn.execute(
                "UPDATE cards SET status = 'frozen' WHERE card_id = $1 AND customer_id = $2 AND tenant_id = $3",
                card_id, customer_id, tenant_id,
            )

        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Card not found.")

        return {"status": "frozen", "card_id": card_id}
    except HTTPException:
        raise
    except Exception as e:
        raise_http_exception_handler(500, f"Failed to freeze card: {str(e)}", "CRD-FREEZE-5001")


@app.post("/api/v1/cards/{card_id}/unfreeze")
async def unfreeze_card(
    card_id: str,
    db=Depends(lambda: db_pool),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    customer_id: str = Header(..., alias="x-keycloak-id"),
):
    try:
        async with db.acquire() as conn:
            result = await conn.execute(
                "UPDATE cards SET status = 'active' WHERE card_id = $1 AND customer_id = $2 AND tenant_id = $3",
                card_id, customer_id, tenant_id,
            )

        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Card not found.")

        return {"status": "active", "card_id": card_id}
    except HTTPException:
        raise
    except Exception as e:
        raise_http_exception_handler(500, f"Failed to unfreeze card: {str(e)}", "CRD-UNFREEZE-5001")


@app.post("/api/v1/cards/{card_id}/block")
async def block_card(
    card_id: str,
    db=Depends(lambda: db_pool),
    tenant_id: str = Header(..., alias="x-tenant-id"),
):
    try:
        async with db.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT card_id FROM cards WHERE card_id = $1 AND tenant_id = $2",
                card_id, tenant_id,
            )
            if not row:
                raise HTTPException(status_code=404, detail="Card not found.")

            await conn.execute(
                "UPDATE cards SET status = 'blocked' WHERE card_id = $1 AND tenant_id = $2",
                card_id, tenant_id,
            )

        return {"status": "blocked", "card_id": card_id}
    except HTTPException:
        raise
    except Exception as e:
        raise_http_exception_handler(500, f"Failed to block card: {str(e)}", "CRD-BLOCK-5001")


@app.post("/api/v1/cards/{card_id}/unblock")
async def unblock_card(
    card_id: str,
    db=Depends(lambda: db_pool),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    customer_id: str = Header(..., alias="x-keycloak-id"),
):
    try:
        async with db.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT card_id FROM cards WHERE card_id = $1 AND tenant_id = $2",
                card_id, tenant_id,
            )
            if not row:
                raise HTTPException(status_code=404, detail="Card not found.")

            await conn.execute(
                "UPDATE cards SET status = 'active' WHERE card_id = $1 AND tenant_id = $2",
                card_id, tenant_id,
            )

        return {"status": "active", "card_id": card_id}
    except HTTPException:
        raise
    except Exception as e:
        raise_http_exception_handler(500, f"Failed to unblock card: {str(e)}", "CRD-UNBLOCK-5001")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8017")))
