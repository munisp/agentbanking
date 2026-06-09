import hashlib
import json
import logging
import os
import sys
import uuid
from typing import Dict, Any, List, Optional

import redis as _redis
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from . import models
from .config import get_db

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.idempotency import IdempotencyStore

_redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
try:
    _redis_client: Optional[_redis.Redis] = _redis.from_url(_redis_url, decode_responses=True)
except Exception:
    _redis_client = None

_idem_store = IdempotencyStore("gpg-txn", _redis_client)
_idem_store.start_eviction_job()


def _idem_hash(request_data: Dict[str, Any]) -> str:
    payload = json.dumps(request_data, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()

# --- Configuration and Logging ---

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the router
router = APIRouter(
    prefix="/transactions",
    tags=["Payment Transactions"],
    responses={404: {"description": "Not found"}},
)

# --- Helper Functions ---

def log_activity(db: Session, transaction_id: int, activity_type: models.ActivityType, description: str, context_data: Optional[str] = None):
    """
    Helper function to log an activity for a given transaction.
    """
    log_entry = models.PaymentActivityLog(
        transaction_id=transaction_id,
        activity_type=activity_type,
        description=description,
        context_data=context_data
    )
    db.add(log_entry)
    # Note: The log entry will be committed with the main transaction or explicitly later.

def get_transaction_by_id(db: Session, transaction_id: str) -> models.PaymentTransaction:
    """
    Fetches a transaction by its unique transaction_id.
    Raises HTTPException 404 if not found.
    """
    db_transaction = db.query(models.PaymentTransaction).filter(
        models.PaymentTransaction.transaction_id == transaction_id
    ).first()
    if not db_transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction with ID '{transaction_id}' not found"
        )
    return db_transaction

# --- CRUD Endpoints ---

@router.post(
    "/",
    response_model=models.PaymentTransactionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new payment transaction",
    description="Initiates a new payment transaction with a unique service-generated ID and sets the status to PENDING."
)
def create_transaction(
    transaction: models.PaymentTransactionCreate,
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    """
    Handles the creation of a new payment transaction with idempotency.
    Send an Idempotency-Key header to prevent duplicate transactions.
    """
    if idempotency_key:
        req_hash = _idem_hash(transaction.model_dump())
        cached_raw = _idem_store.check(idempotency_key, req_hash)
        if cached_raw:
            if cached_raw.get("request_hash") != req_hash:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Idempotency key reused with different request payload",
                )
            txn_id = cached_raw.get("transaction_id") or cached_raw.get("response")
            if txn_id:
                existing = db.query(models.PaymentTransaction).filter(
                    models.PaymentTransaction.transaction_id == txn_id
                ).first()
                if existing:
                    logger.info(f"Idempotency hit for key={idempotency_key}")
                    return existing
        else:
            acquired = _idem_store.acquire(idempotency_key, req_hash)
            if not acquired:
                raise HTTPException(status_code=409, detail="Request is already being processed")

    try:
        new_transaction_id = str(uuid.uuid4())

        db_transaction = models.PaymentTransaction(
            transaction_id=new_transaction_id,
            amount=transaction.amount,
            currency=transaction.currency,
            customer_id=transaction.customer_id,
            payment_method_type=transaction.payment_method_type,
            gateway_name=transaction.gateway_name,
            status=models.TransactionStatus.PENDING
        )

        db.add(db_transaction)
        db.flush()

        log_activity(
            db,
            db_transaction.id,
            models.ActivityType.CREATE,
            f"Transaction initiated for {transaction.amount} {transaction.currency} via {transaction.gateway_name}."
        )

        db_transaction.status = models.TransactionStatus.AUTHORIZED
        db_transaction.gateway_transaction_id = f"GW-{new_transaction_id[:8]}"
        db_transaction.gateway_response_code = "20000"

        log_activity(
            db,
            db_transaction.id,
            models.ActivityType.GATEWAY_CALL,
            f"Authorization successful. Gateway ID: {db_transaction.gateway_transaction_id}"
        )

        db.commit()
        db.refresh(db_transaction)

        if idempotency_key:
            _idem_store.complete(
                idempotency_key,
                _idem_hash(transaction.model_dump()),
                new_transaction_id,
            )

        logger.info(f"Transaction {new_transaction_id} created and authorized.")
        return db_transaction

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Integrity constraint violation (e.g., duplicate unique field)."
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating transaction: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during transaction creation."
        )

@router.get(
    "/{transaction_id}",
    response_model=models.PaymentTransactionDetailResponse,
    summary="Retrieve a single payment transaction with activity logs",
    description="Fetches the details of a payment transaction using its unique service ID, including all associated activity logs."
)
def read_transaction(transaction_id: str, db: Session = Depends(get_db)):
    """
    Retrieves a transaction and its activity logs by transaction_id.
    """
    db_transaction = get_transaction_by_id(db, transaction_id)
    return db_transaction

@router.get(
    "/",
    response_model=List[models.PaymentTransactionResponse],
    summary="List all payment transactions",
    description="Retrieves a list of all payment transactions with optional filtering and pagination."
)
def list_transactions(
    status_filter: Optional[models.TransactionStatus] = None,
    customer_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Lists transactions with optional filters for status and customer_id.
    """
    query = db.query(models.PaymentTransaction)
    
    if status_filter:
        query = query.filter(models.PaymentTransaction.status == status_filter)
    
    if customer_id:
        query = query.filter(models.PaymentTransaction.customer_id == customer_id)
        
    transactions = query.offset(skip).limit(limit).all()
    return transactions

@router.patch(
    "/{transaction_id}",
    response_model=models.PaymentTransactionResponse,
    summary="Update an existing payment transaction",
    description="Updates specific fields of a payment transaction, primarily used for status changes or recording gateway responses."
)
def update_transaction(
    transaction_id: str, 
    transaction_update: models.PaymentTransactionUpdate, 
    db: Session = Depends(get_db)
):
    """
    Updates a transaction's status or gateway details.
    """
    db_transaction = get_transaction_by_id(db, transaction_id)
    
    update_data = transaction_update.model_dump(exclude_unset=True)
    
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided for update."
        )

    old_status = db_transaction.status
    
    for key, value in update_data.items():
        setattr(db_transaction, key, value)
        
    if 'status' in update_data and old_status != db_transaction.status:
        log_activity(
            db, 
            db_transaction.id, 
            models.ActivityType.STATUS_CHANGE, 
            f"Status changed from {old_status.value} to {db_transaction.status.value}."
        )
    else:
        log_activity(
            db, 
            db_transaction.id, 
            models.ActivityType.UPDATE, 
            f"Transaction details updated."
        )

    db.commit()
    db.refresh(db_transaction)
    return db_transaction

@router.delete(
    "/{transaction_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a payment transaction",
    description="Deletes a payment transaction and all associated activity logs. This operation is typically restricted in production systems."
)
def delete_transaction(transaction_id: str, db: Session = Depends(get_db)):
    """
    Deletes a transaction.
    """
    db_transaction = get_transaction_by_id(db, transaction_id)
    
    db.delete(db_transaction)
    db.commit()
    logger.warning(f"Transaction {transaction_id} deleted.")
    return

# --- Business-Specific Endpoints ---

@router.post(
    "/{transaction_id}/capture",
    response_model=models.PaymentTransactionResponse,
    summary="Capture an authorized payment transaction",
    description="Finalizes a transaction that was previously only authorized, moving its status to SUCCESS."
)
def capture_transaction(transaction_id: str, db: Session = Depends(get_db)):
    """
    Captures an authorized transaction.
    """
    db_transaction = get_transaction_by_id(db, transaction_id)
    
    if db_transaction.status != models.TransactionStatus.AUTHORIZED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Transaction must be in 'AUTHORIZED' status to be captured. Current status: {db_transaction.status.value}"
        )
        
    # Execute gateway capture call
    db_transaction.status = models.TransactionStatus.SUCCESS
    
    log_activity(
        db, 
        db_transaction.id, 
        models.ActivityType.GATEWAY_CALL, 
        "Capture successful. Status set to SUCCESS."
    )
    
    db.commit()
    db.refresh(db_transaction)
    logger.info(f"Transaction {transaction_id} captured successfully.")
    return db_transaction

@router.post(
    "/{transaction_id}/refund",
    response_model=models.PaymentTransactionResponse,
    summary="Refund a successful payment transaction",
    description="Initiates a full refund for a successful transaction, moving its status to REFUNDED."
)
def refund_transaction(transaction_id: str, db: Session = Depends(get_db)):
    """
    Refunds a successful transaction.
    """
    db_transaction = get_transaction_by_id(db, transaction_id)
    
    if db_transaction.status != models.TransactionStatus.SUCCESS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Transaction must be in 'SUCCESS' status to be refunded. Current status: {db_transaction.status.value}"
        )
        
    # Simulate gateway refund call
    db_transaction.status = models.TransactionStatus.REFUNDED
    
    log_activity(
        db, 
        db_transaction.id, 
        models.ActivityType.GATEWAY_CALL, 
        "Simulated refund successful. Status set to REFUNDED."
    )
    
    db.commit()
    db.refresh(db_transaction)
    logger.info(f"Transaction {transaction_id} refunded successfully.")
    return db_transaction
