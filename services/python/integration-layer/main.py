import hashlib
import json
import os
import sys
from typing import Dict, Any, List, Optional

import redis as _redis
from fastapi import FastAPI, Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import logging

from . import models
from .models import SessionLocal, engine

# --- Production: Graceful Shutdown ---
import signal
import sys
import atexit
import logging

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

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.idempotency import IdempotencyStore

_redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
try:
    _redis_client: Optional[_redis.Redis] = _redis.from_url(_redis_url, decode_responses=True)
except Exception:
    _redis_client = None

_idem_store = IdempotencyStore("intlayer-txn", _redis_client)

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Remittance Platform Integration Service")

@app.on_event("startup")
async def _start_eviction():
    _idem_store.start_eviction_job()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# OAuth2PasswordBearer for authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Dependency to get the DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# JWT token validation
def get_current_user(token: str = Depends(oauth2_scheme)):
    # In a real application, you would decode the token, validate it, and fetch the user.
    # For this example, we'll just check if the token is present.
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    logger.info(f"User authenticated with token: {token[:10]}...")
    from fastapi import HTTPException
    raise HTTPException(status_code=401, detail="Authentication required")

@app.get("/health", tags=["Health Check"])
async def health_check():
    logger.info("Health check requested.")
    return {"status": "healthy"}

@app.get("/metrics", tags=["Metrics"])
async def get_metrics(current_user: dict = Depends(get_current_user)):
    logger.info(f"Metrics requested by user: {current_user['username']}")
    # In a real application, you would gather actual metrics here
    return {"total_agents": 100, "total_transactions": 1000, "active_agents": 80}

# Agent Endpoints
@app.post("/agents/", response_model=models.Agent, tags=["Agents"])
async def create_agent(agent: models.AgentCreate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    logger.info(f"Create agent requested by user: {current_user['username']}")
    db_agent = models.Agent(**agent.dict())
    db.add(db_agent)
    db.commit()
    db.refresh(db_agent)
    return db_agent

@app.get("/agents/", response_model=List[models.Agent], tags=["Agents"])
async def read_agents(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    logger.info(f"Read agents requested by user: {current_user['username']}")
    agents = db.query(models.Agent).offset(skip).limit(limit).all()
    return agents

@app.get("/agents/{agent_id}", response_model=models.Agent, tags=["Agents"])
async def read_agent(agent_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    logger.info(f"Read agent {agent_id} requested by user: {current_user['username']}")
    agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
    if agent is None:
        logger.warning(f"Agent {agent_id} not found.")
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent

@app.put("/agents/{agent_id}", response_model=models.Agent, tags=["Agents"])
async def update_agent(agent_id: int, agent: models.AgentCreate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    logger.info(f"Update agent {agent_id} requested by user: {current_user['username']}")
    db_agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
    if db_agent is None:
        logger.warning(f"Agent {agent_id} not found for update.")
        raise HTTPException(status_code=404, detail="Agent not found")
    for key, value in agent.dict().items():
        setattr(db_agent, key, value)
    db.commit()
    db.refresh(db_agent)
    return db_agent

@app.delete("/agents/{agent_id}", tags=["Agents"])
async def delete_agent(agent_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    logger.info(f"Delete agent {agent_id} requested by user: {current_user['username']}")
    db_agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
    if db_agent is None:
        logger.warning(f"Agent {agent_id} not found for deletion.")
        raise HTTPException(status_code=404, detail="Agent not found")
    db.delete(db_agent)
    db.commit()
    return {"message": "Agent deleted successfully"}

# Transaction Endpoints
@app.post("/transactions/", response_model=models.Transaction, tags=["Transactions"])
async def create_transaction(
    transaction: models.TransactionCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    """Create transaction with idempotency. Send Idempotency-Key header to prevent duplicates."""
    logger.info(f"Create transaction requested by user: {current_user['username']}")

    if idempotency_key:
        req_hash = hashlib.sha256(json.dumps(transaction.dict(), sort_keys=True, default=str).encode()).hexdigest()
        cached_raw = _idem_store.check(idempotency_key, req_hash)
        if cached_raw:
            if cached_raw.get("request_hash") != req_hash:
                raise HTTPException(status_code=422, detail="Idempotency key reused with different request payload")
            txn_id = cached_raw.get("transaction_id") or cached_raw.get("response")
            if txn_id:
                existing = db.query(models.Transaction).filter(models.Transaction.id == int(txn_id)).first()
                if existing:
                    logger.info(f"Idempotency hit for key={idempotency_key}")
                    return existing
        else:
            acquired = _idem_store.acquire(idempotency_key, req_hash)
            if not acquired:
                raise HTTPException(status_code=409, detail="Request is already being processed")

    db_transaction = models.Transaction(**transaction.dict())
    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)

    if idempotency_key:
        _idem_store.complete(
            idempotency_key,
            hashlib.sha256(json.dumps(transaction.dict(), sort_keys=True, default=str).encode()).hexdigest(),
            str(db_transaction.id),
        )

    return db_transaction

@app.get("/transactions/", response_model=List[models.Transaction], tags=["Transactions"])
async def read_transactions(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    logger.info(f"Read transactions requested by user: {current_user['username']}")
    transactions = db.query(models.Transaction).offset(skip).limit(limit).all()
    return transactions

@app.get("/transactions/{transaction_id}", response_model=models.Transaction, tags=["Transactions"])
async def read_transaction(transaction_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    logger.info(f"Read transaction {transaction_id} requested by user: {current_user['username']}")
    transaction = db.query(models.Transaction).filter(models.Transaction.id == transaction_id).first()
    if transaction is None:
        logger.warning(f"Transaction {transaction_id} not found.")
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction

@app.put("/transactions/{transaction_id}", response_model=models.Transaction, tags=["Transactions"])
async def update_transaction(transaction_id: int, transaction: models.TransactionCreate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    logger.info(f"Update transaction {transaction_id} requested by user: {current_user['username']}")
    db_transaction = db.query(models.Transaction).filter(models.Transaction.id == transaction_id).first()
    if db_transaction is None:
        logger.warning(f"Transaction {transaction_id} not found for update.")
        raise HTTPException(status_code=404, detail="Transaction not found")
    for key, value in transaction.dict().items():
        setattr(db_transaction, key, value)
    db.commit()
    db.refresh(db_transaction)
    return db_transaction

@app.delete("/transactions/{transaction_id}", tags=["Transactions"])
async def delete_transaction(transaction_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    logger.info(f"Delete transaction {transaction_id} requested by user: {current_user['username']}")
    db_transaction = db.query(models.Transaction).filter(models.Transaction.id == transaction_id).first()
    if db_transaction is None:
        logger.warning(f"Transaction {transaction_id} not found for deletion.")
        raise HTTPException(status_code=404, detail="Transaction not found")
    db.delete(db_transaction)
    db.commit()
    return {"message": "Transaction deleted successfully"}
