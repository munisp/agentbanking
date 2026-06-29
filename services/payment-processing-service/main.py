from fastapi import FastAPI
from sqlalchemy import text

from database import Base, engine
from api import (
    health_router,
    payment_router,
    qr_router,
    system_router,
    charges_router,
    transfers_router,
    transactions_router,
)
from utils import get_config
from utils.coa_client import CoAClient
from middlewares import RequiredHeadersMiddleware

# Setup config
config = get_config()

# Initialize CoA Client
coa_client = CoAClient()

app = FastAPI(
    title="Payment processing service",
    description="54agent payment processing service.",
    version="0.0.0",
)

app.add_middleware(
    RequiredHeadersMiddleware,
    required_headers=[
        "x-tenant-id",
        "x-keycloak-id",
        "x-ledger-id",
        "x-mint-account-id",
    ],
    exclude_prefixes=["/health", "/dapr", "/charges", "/transfers", "/api/v1/transactions"],
)

Base.metadata.create_all(bind=engine)

with engine.connect() as _conn:
    _conn.execute(text("""
        CREATE TABLE IF NOT EXISTS payment_transactions (
            id VARCHAR PRIMARY KEY,
            tenant_id VARCHAR NOT NULL,
            agent_keycloak_id VARCHAR NOT NULL DEFAULT '',
            amount DECIMAL(18,2) NOT NULL DEFAULT 0,
            currency VARCHAR(10) NOT NULL DEFAULT 'NGN',
            channel VARCHAR(50) NOT NULL DEFAULT '',
            type VARCHAR(50) NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            provider_id VARCHAR(100) NOT NULL DEFAULT '',
            insurance_type VARCHAR(50) NOT NULL DEFAULT '',
            plan_id VARCHAR(100) NOT NULL DEFAULT '',
            customer_phone VARCHAR(20) NOT NULL DEFAULT '',
            policy_number VARCHAR(100) NOT NULL DEFAULT '',
            reference VARCHAR(100) NOT NULL DEFAULT '',
            status VARCHAR(30) NOT NULL DEFAULT 'success',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """))
    _conn.execute(text("CREATE INDEX IF NOT EXISTS idx_pay_txn_tenant ON payment_transactions(tenant_id, type, channel)"))
    _conn.commit()

app.include_router(health_router, prefix="", tags=["health"])
app.include_router(transactions_router, prefix="", tags=["transactions"])
app.include_router(charges_router, prefix="/charges", tags=["charges"])
app.include_router(transfers_router, prefix="/transfers", tags=["transfers"])
app.include_router(payment_router, prefix="/payment", tags=["payment"])
app.include_router(qr_router, prefix="/qr", tags=["qr"])
app.include_router(system_router, prefix="/system", tags=["system"])
