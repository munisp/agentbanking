import logging

from fastapi import FastAPI
from sqlalchemy import text

from database import Base, engine
from api.v1 import account_router, health_router, system_router, bank_router, statements_router, opening_router, closure_router, safe_deposit_router, billing_router, savings_router
from utils import get_config
from utils.coa_client import CoAClient
from database import get_session
from middlewares import RequiredHeadersMiddleware

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Setup config
config = get_config()

# Initialize CoA Client
coa_client = CoAClient()

app = FastAPI(
    title="Account service",
    description="54link account management service.",
    version="0.0.0"
)

app.add_middleware(
    RequiredHeadersMiddleware,
    required_headers=[
        "x-tenant-id",
        "x-keycloak-id",
        "x-ledger-id",
    ],
    exclude_prefixes=["/health", "/dapr", "/api/v1/savings"],
)

Base.metadata.create_all(bind=engine)

with engine.connect() as _conn:
    _conn.execute(text("""
        CREATE TABLE IF NOT EXISTS agent_savings_goals (
            id VARCHAR PRIMARY KEY,
            tenant_id VARCHAR NOT NULL,
            agent_keycloak_id VARCHAR NOT NULL DEFAULT '',
            name VARCHAR NOT NULL DEFAULT '',
            target_amount DECIMAL(18,2) NOT NULL DEFAULT 0,
            current_amount DECIMAL(18,2) NOT NULL DEFAULT 0,
            category VARCHAR(50) NOT NULL DEFAULT 'other',
            target_date DATE,
            auto_save BOOLEAN NOT NULL DEFAULT FALSE,
            auto_amount DECIMAL(18,2) NOT NULL DEFAULT 0,
            status VARCHAR(20) NOT NULL DEFAULT 'active',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """))
    _conn.execute(text("CREATE INDEX IF NOT EXISTS idx_savings_goals_agent ON agent_savings_goals(agent_keycloak_id, tenant_id)"))
    _conn.commit()

app.include_router(health_router, prefix="", tags=["health"])
app.include_router(account_router, prefix="/account", tags=["account"])
app.include_router(bank_router, prefix="/bank", tags=["bank"])
app.include_router(system_router, prefix="/system", tags=["system"])
app.include_router(statements_router, prefix="/statements", tags=["statements"])
app.include_router(opening_router, prefix="/account-opening", tags=["account-opening"])
app.include_router(closure_router, prefix="/account-closure", tags=["account-closure"])
app.include_router(safe_deposit_router, prefix="/safe-deposit", tags=["safe-deposit"])
app.include_router(billing_router, prefix="/billing", tags=["billing"])
app.include_router(savings_router, prefix="/api/v1/savings", tags=["savings"])

@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Account Service is running..")
