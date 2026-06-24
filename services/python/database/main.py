import os
from fastapi import FastAPI, Depends, HTTPException, status, Security
import sys as _sys2, os as _os2
_sys2.path.insert(0, _os2.path.join(_os2.path.dirname(_os2.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from fastapi.security import APIKeyHeader
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List
import logging

# Import transaction management utilities
from .transactions import transaction_scope, TransactionManager, transfer_money

from . import models
from .models import Base, Agent, Customer, Account, Transaction
from .models import AgentCreate, AgentInDB, AgentUpdate
from .models import CustomerCreate, CustomerInDB, CustomerUpdate
from .models import AccountCreate, AccountInDB, AccountUpdate
from .models import TransactionCreate, TransactionInDB, TransactionUpdate
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .config import settings

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

# Configure logging
logging.basicConfig(level=settings.LOG_LEVEL, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Database setup with production-ready connection pooling
if "postgresql" in settings.DATABASE_URL.lower():
    # PostgreSQL with connection pooling
    engine = create_engine(
        settings.DATABASE_URL,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_recycle=settings.DB_POOL_RECYCLE,
        pool_pre_ping=settings.DB_POOL_PRE_PING,
        echo=settings.DB_ECHO
    )
    logger.info(f"PostgreSQL engine created with pool_size={settings.DB_POOL_SIZE}, max_overflow={settings.DB_MAX_OVERFLOW}")
else:
    # Other databases
    engine = create_engine(
        settings.DATABASE_URL,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_pre_ping=settings.DB_POOL_PRE_PING,
        echo=settings.DB_ECHO
    )

SessionLocal = sessionmaker(
    autocommit=settings.DB_AUTOCOMMIT,
    autoflush=settings.DB_AUTOFLUSH,
    bind=engine
)

Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.PROJECT_NAME, version=settings.PROJECT_VERSION)

@app.on_event("startup")
async def _init_pg_pool():
    await get_pg_pool()

apply_middleware(app, enable_auth=True)

# API Key authentication
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)

def get_api_key(api_key: str = Security(api_key_header)):
    if api_key == settings.API_KEY:
        return api_key
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API Key",
    )

# Dependency to get the DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Global Exception Handler
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    logger.error(f"HTTP Exception: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"message": exc.detail},
    )

@app.get("/", tags=["Health Check"])
async def root():
    logger.info("Root endpoint accessed.")
    return {"message": "Remittance Platform DB Service is running!"}

@app.get("/health", tags=["Health Check"])
async def health_check(db: Session = Depends(get_db)):
    try:
        db.execute("SELECT 1")
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database connection failed")

@app.get("/metrics", tags=["Monitoring"])
async def get_metrics():
    # In a real-world scenario, this would expose Prometheus metrics.
    # Return service metrics.
    return {"status": "ok", "metrics": "available", "uptime": "running"}

# --- Agent Endpoints ---

@app.post("/agents/", response_model=AgentInDB, status_code=status.HTTP_201_CREATED, tags=["Agents"], dependencies=[Depends(get_api_key)])
def create_agent(agent: AgentCreate, db: Session = Depends(get_db)):
    logger.info(f"Attempting to create agent with ID: {agent.agent_id}")
    db_agent = db.query(Agent).filter(Agent.agent_id == agent.agent_id).first()
    if db_agent:
        logger.warning(f"Agent creation failed: Agent ID {agent.agent_id} already registered.")
        raise HTTPException(status_code=400, detail="Agent ID already registered")
    db_agent = Agent(**agent.dict())
    db.add(db_agent)
    db.commit()
    db.refresh(db_agent)
    logger.info(f"Agent created successfully with ID: {db_agent.agent_id}")
    return db_agent

@app.get("/agents/", response_model=List[AgentInDB], tags=["Agents"], dependencies=[Depends(get_api_key)])
def read_agents(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    logger.info(f"Fetching agents with skip={skip}, limit={limit}")
    agents = db.query(Agent).offset(skip).limit(limit).all()
    return agents

@app.get("/agents/{agent_id}", response_model=AgentInDB, tags=["Agents"], dependencies=[Depends(get_api_key)])
def read_agent(agent_id: str, db: Session = Depends(get_db)):
    logger.info(f"Fetching agent with ID: {agent_id}")
    db_agent = db.query(Agent).filter(Agent.agent_id == agent_id).first()
    if db_agent is None:
        logger.warning(f"Agent not found with ID: {agent_id}")
        raise HTTPException(status_code=404, detail="Agent not found")
    return db_agent

@app.put("/agents/{agent_id}", response_model=AgentInDB, tags=["Agents"], dependencies=[Depends(get_api_key)])
def update_agent(agent_id: str, agent: AgentUpdate, db: Session = Depends(get_db)):
    logger.info(f"Attempting to update agent with ID: {agent_id}")
    db_agent = db.query(Agent).filter(Agent.agent_id == agent_id).first()
    if db_agent is None:
        logger.warning(f"Agent update failed: Agent not found with ID: {agent_id}")
        raise HTTPException(status_code=404, detail="Agent not found")
    for key, value in agent.dict(exclude_unset=True).items():
        setattr(db_agent, key, value)
    db.commit()
    db.refresh(db_agent)
    logger.info(f"Agent with ID: {agent_id} updated successfully.")
    return db_agent

@app.delete("/agents/{agent_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Agents"], dependencies=[Depends(get_api_key)])
def delete_agent(agent_id: str, db: Session = Depends(get_db)):
    logger.info(f"Attempting to delete agent with ID: {agent_id}")
    db_agent = db.query(Agent).filter(Agent.agent_id == agent_id).first()
    if db_agent is None:
        logger.warning(f"Agent deletion failed: Agent not found with ID: {agent_id}")
        raise HTTPException(status_code=404, detail="Agent not found")
    db.delete(db_agent)
    db.commit()
    logger.info(f"Agent with ID: {agent_id} deleted successfully.")
    return

# --- Customer Endpoints ---

@app.post("/customers/", response_model=CustomerInDB, status_code=status.HTTP_201_CREATED, tags=["Customers"], dependencies=[Depends(get_api_key)])
def create_customer(customer: CustomerCreate, db: Session = Depends(get_db)):
    logger.info(f"Attempting to create customer with ID: {customer.customer_id}")
    db_customer = db.query(Customer).filter(Customer.customer_id == customer.customer_id).first()
    if db_customer:
        logger.warning(f"Customer creation failed: Customer ID {customer.customer_id} already registered.")
        raise HTTPException(status_code=400, detail="Customer ID already registered")
    db_customer = Customer(**customer.dict())
    db.add(db_customer)
    db.commit()
    db.refresh(db_customer)
    logger.info(f"Customer created successfully with ID: {db_customer.customer_id}")
    return db_customer

@app.get("/customers/", response_model=List[CustomerInDB], tags=["Customers"], dependencies=[Depends(get_api_key)])
def read_customers(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    logger.info(f"Fetching customers with skip={skip}, limit={limit}")
    customers = db.query(Customer).offset(skip).limit(limit).all()
    return customers

@app.get("/customers/{customer_id}", response_model=CustomerInDB, tags=["Customers"], dependencies=[Depends(get_api_key)])
def read_customer(customer_id: str, db: Session = Depends(get_db)):
    logger.info(f"Fetching customer with ID: {customer_id}")
    db_customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
    if db_customer is None:
        logger.warning(f"Customer not found with ID: {customer_id}")
        raise HTTPException(status_code=404, detail="Customer not found")
    return db_customer

@app.put("/customers/{customer_id}", response_model=CustomerInDB, tags=["Customers"], dependencies=[Depends(get_api_key)])
def update_customer(customer_id: str, customer: CustomerUpdate, db: Session = Depends(get_db)):
    logger.info(f"Attempting to update customer with ID: {customer_id}")
    db_customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
    if db_customer is None:
        logger.warning(f"Customer update failed: Customer not found with ID: {customer_id}")
        raise HTTPException(status_code=404, detail="Customer not found")
    for key, value in customer.dict(exclude_unset=True).items():
        setattr(db_customer, key, value)
    db.commit()
    db.refresh(db_customer)
    logger.info(f"Customer with ID: {customer_id} updated successfully.")
    return db_customer

@app.delete("/customers/{customer_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Customers"], dependencies=[Depends(get_api_key)])
def delete_customer(customer_id: str, db: Session = Depends(get_db)):
    logger.info(f"Attempting to delete customer with ID: {customer_id}")
    db_customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
    if db_customer is None:
        logger.warning(f"Customer deletion failed: Customer not found with ID: {customer_id}")
        raise HTTPException(status_code=404, detail="Customer not found")
    db.delete(db_customer)
    db.commit()
    logger.info(f"Customer with ID: {customer_id} deleted successfully.")
    return

# --- Account Endpoints ---

@app.post("/accounts/", response_model=AccountInDB, status_code=status.HTTP_201_CREATED, tags=["Accounts"], dependencies=[Depends(get_api_key)])
def create_account(account: AccountCreate, db: Session = Depends(get_db)):
    logger.info(f"Attempting to create account with number: {account.account_number}")
    db_account = db.query(Account).filter(Account.account_number == account.account_number).first()
    if db_account:
        logger.warning(f"Account creation failed: Account number {account.account_number} already registered.")
        raise HTTPException(status_code=400, detail="Account number already registered")
    
    # Check if customer and agent exist
    customer = db.query(Customer).filter(Customer.id == account.customer_id).first()
    if not customer:
        logger.warning(f"Account creation failed: Customer not found with ID: {account.customer_id}")
        raise HTTPException(status_code=404, detail="Customer not found")
    agent = db.query(Agent).filter(Agent.id == account.agent_id).first()
    if not agent:
        logger.warning(f"Account creation failed: Agent not found with ID: {account.agent_id}")
        raise HTTPException(status_code=404, detail="Agent not found")

    db_account = Account(**account.dict())
    db.add(db_account)
    db.commit()
    db.refresh(db_account)
    logger.info(f"Account created successfully with number: {db_account.account_number}")
    return db_account

@app.get("/accounts/", response_model=List[AccountInDB], tags=["Accounts"], dependencies=[Depends(get_api_key)])
def read_accounts(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    logger.info(f"Fetching accounts with skip={skip}, limit={limit}")
    accounts = db.query(Account).offset(skip).limit(limit).all()
    return accounts

@app.get("/accounts/{account_number}", response_model=AccountInDB, tags=["Accounts"], dependencies=[Depends(get_api_key)])
def read_account(account_number: str, db: Session = Depends(get_db)):
    logger.info(f"Fetching account with number: {account_number}")
    db_account = db.query(Account).filter(Account.account_number == account_number).first()
    if db_account is None:
        logger.warning(f"Account not found with number: {account_number}")
        raise HTTPException(status_code=404, detail="Account not found")
    return db_account

@app.put("/accounts/{account_number}", response_model=AccountInDB, tags=["Accounts"], dependencies=[Depends(get_api_key)])
def update_account(account_number: str, account: AccountUpdate, db: Session = Depends(get_db)):
    logger.info(f"Attempting to update account with number: {account_number}")
    db_account = db.query(Account).filter(Account.account_number == account_number).first()
    if db_account is None:
        logger.warning(f"Account update failed: Account not found with number: {account_number}")
        raise HTTPException(status_code=404, detail="Account not found")
    for key, value in account.dict(exclude_unset=True).items():
        setattr(db_account, key, value)
    db.commit()
    db.refresh(db_account)
    logger.info(f"Account with number: {account_number} updated successfully.")
    return db_account

@app.delete("/accounts/{account_number}", status_code=status.HTTP_204_NO_CONTENT, tags=["Accounts"], dependencies=[Depends(get_api_key)])
def delete_account(account_number: str, db: Session = Depends(get_db)):
    logger.info(f"Attempting to delete account with number: {account_number}")
    db_account = db.query(Account).filter(Account.account_number == account_number).first()
    if db_account is None:
        logger.warning(f"Account deletion failed: Account not found with number: {account_number}")
        raise HTTPException(status_code=404, detail="Account not found")
    db.delete(db_account)
    db.commit()
    logger.info(f"Account with number: {account_number} deleted successfully.")
    return

# --- Transaction Endpoints ---

@app.post("/transactions/", response_model=TransactionInDB, status_code=status.HTTP_201_CREATED, tags=["Transactions"], dependencies=[Depends(get_api_key)])
def create_transaction(transaction: TransactionCreate, db: Session = Depends(get_db)):
    logger.info(f"Attempting to create transaction with ID: {transaction.transaction_id}")
    db_transaction = db.query(Transaction).filter(Transaction.transaction_id == transaction.transaction_id).first()
    if db_transaction:
        logger.warning(f"Transaction creation failed: Transaction ID {transaction.transaction_id} already registered.")
        raise HTTPException(status_code=400, detail="Transaction ID already registered")
    
    # Check if account, agent, and customer exist
    account = db.query(Account).filter(Account.id == transaction.account_id).first()
    if not account:
        logger.warning(f"Transaction creation failed: Account not found with ID: {transaction.account_id}")
        raise HTTPException(status_code=404, detail="Account not found")
    agent = db.query(Agent).filter(Agent.id == transaction.agent_id).first()
    if not agent:
        logger.warning(f"Transaction creation failed: Agent not found with ID: {transaction.agent_id}")
        raise HTTPException(status_code=404, detail="Agent not found")
    customer = db.query(Customer).filter(Customer.id == transaction.customer_id).first()
    if not customer:
        logger.warning(f"Transaction creation failed: Customer not found with ID: {transaction.customer_id}")
        raise HTTPException(status_code=404, detail="Customer not found")

    db_transaction = Transaction(**transaction.dict())
    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)
    logger.info(f"Transaction created successfully with ID: {db_transaction.transaction_id}")
    return db_transaction

@app.get("/transactions/", response_model=List[TransactionInDB], tags=["Transactions"], dependencies=[Depends(get_api_key)])
def read_transactions(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    logger.info(f"Fetching transactions with skip={skip}, limit={limit}")
    transactions = db.query(Transaction).offset(skip).limit(limit).all()
    return transactions

@app.get("/transactions/{transaction_id}", response_model=TransactionInDB, tags=["Transactions"], dependencies=[Depends(get_api_key)])
def read_transaction(transaction_id: str, db: Session = Depends(get_db)):
    logger.info(f"Fetching transaction with ID: {transaction_id}")
    db_transaction = db.query(Transaction).filter(Transaction.transaction_id == transaction_id).first()
    if db_transaction is None:
        logger.warning(f"Transaction not found with ID: {transaction_id}")
        raise HTTPException(status_code=404, detail="Transaction not found")
    return db_transaction

@app.put("/transactions/{transaction_id}", response_model=TransactionInDB, tags=["Transactions"], dependencies=[Depends(get_api_key)])
def update_transaction(transaction_id: str, transaction: TransactionUpdate, db: Session = Depends(get_db)):
    logger.info(f"Attempting to update transaction with ID: {transaction_id}")
    db_transaction = db.query(Transaction).filter(Transaction.transaction_id == transaction_id).first()
    if db_transaction is None:
        logger.warning(f"Transaction update failed: Transaction not found with ID: {transaction_id}")
        raise HTTPException(status_code=404, detail="Transaction not found")
    for key, value in transaction.dict(exclude_unset=True).items():
        setattr(db_transaction, key, value)
    db.commit()
    db.refresh(db_transaction)
    logger.info(f"Transaction with ID: {transaction_id} updated successfully.")
    return db_transaction

@app.delete("/transactions/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Transactions"], dependencies=[Depends(get_api_key)])
def delete_transaction(transaction_id: str, db: Session = Depends(get_db)):
    logger.info(f"Attempting to delete transaction with ID: {transaction_id}")
    db_transaction = db.query(Transaction).filter(Transaction.transaction_id == transaction_id).first()
    if db_transaction is None:
        logger.warning(f"Transaction deletion failed: Transaction not found with ID: {transaction_id}")
        raise HTTPException(status_code=404, detail="Transaction not found")
    db.delete(db_transaction)
    db.commit()
    logger.info(f"Transaction with ID: {transaction_id} deleted successfully.")
    return
