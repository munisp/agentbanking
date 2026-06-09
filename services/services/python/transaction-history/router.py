import csv
import hashlib
import io
import json
import os
import sys
import datetime
from typing import Dict, Any, List, Optional

import redis as _redis
from fastapi import APIRouter, Depends, Header, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, extract, or_

from . import models
from .config import get_db, logger

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.idempotency import IdempotencyStore

_redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
try:
    _redis_client: Optional[_redis.Redis] = _redis.from_url(_redis_url, decode_responses=True)
except Exception:
    _redis_client = None

_idem_store = IdempotencyStore("txnhist", _redis_client)
_idem_store.start_eviction_job()

# --- Router Initialization ---

router = APIRouter(
    prefix="/transactions",
    tags=["transactions"],
    responses={404: {"description": "Not found"}},
)

# --- Business Logic Helper Functions ---

def get_transaction_by_id(db: Session, transaction_id: int) -> models.Transaction:
    """Fetches a transaction by its ID or raises a 404 error."""
    db_transaction = db.query(models.Transaction).filter(models.Transaction.id == transaction_id).first()
    if db_transaction is None:
        logger.warning(f"Transaction not found: ID {transaction_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    return db_transaction

# --- CRUD Endpoints ---

@router.post("/", response_model=models.TransactionResponse, status_code=status.HTTP_201_CREATED)
def create_transaction(
    transaction: models.TransactionCreate,
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    """
    **Creates a new transaction record with idempotency support.**
    Send an Idempotency-Key header to prevent duplicate transaction records.
    """
    if idempotency_key:
        req_hash = hashlib.sha256(json.dumps(transaction.model_dump(exclude_none=True), sort_keys=True, default=str).encode()).hexdigest()
        cached_raw = _idem_store.check(idempotency_key, req_hash)
        if cached_raw:
            if cached_raw.get("request_hash") != req_hash:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Idempotency key reused with different request payload",
                )
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

    logger.info(f"Attempting to create new transaction for user {transaction.user_id}")
    try:
        db_transaction = models.Transaction(
            **transaction.model_dump(exclude_none=True, exclude={"metadata"}),
            metadata_json=transaction.metadata
        )
        db.add(db_transaction)
        db.commit()
        db.refresh(db_transaction)

        if idempotency_key:
            _idem_store.complete(
                idempotency_key,
                hashlib.sha256(
                    json.dumps(transaction.model_dump(exclude_none=True), sort_keys=True, default=str).encode()
                ).hexdigest(),
                str(db_transaction.id),
            )

        logger.info(f"Transaction created successfully: ID {db_transaction.id}")
        return db_transaction
    except Exception as e:
        logger.error(f"Error creating transaction: {e}")
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not create transaction")

@router.get("/{transaction_id}", response_model=models.TransactionResponse)
def read_transaction(transaction_id: int, db: Session = Depends(get_db)):
    """
    **Retrieves a single transaction by its unique ID.**
    """
    return get_transaction_by_id(db, transaction_id)

@router.put("/{transaction_id}", response_model=models.TransactionResponse)
def update_transaction(transaction_id: int, transaction_update: models.TransactionUpdate, db: Session = Depends(get_db)):
    """
    **Updates the status or description of an existing transaction.**

    This is typically used to change the status from PENDING to COMPLETED or FAILED.
    """
    db_transaction = get_transaction_by_id(db, transaction_id)

    update_data = transaction_update.model_dump(exclude_unset=True)
    
    # Handle metadata_json update separately
    metadata_update = update_data.pop("metadata", None)
    if metadata_update is not None:
        db_transaction.metadata_json = metadata_update

    for key, value in update_data.items():
        setattr(db_transaction, key, value)

    db.commit()
    db.refresh(db_transaction)
    logger.info(f"Transaction updated: ID {transaction_id}, New Status: {db_transaction.status}")
    return db_transaction

@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(transaction_id: int, db: Session = Depends(get_db)):
    """
    **Deletes a transaction record.**

    Note: In a production system, transactions are often soft-deleted or archived, not permanently removed.
    """
    db_transaction = get_transaction_by_id(db, transaction_id)
    db.delete(db_transaction)
    db.commit()
    logger.info(f"Transaction deleted: ID {transaction_id}")
    return

# --- Search and List Endpoint ---

@router.get("/", response_model=List[models.TransactionResponse])
def list_transactions(
    db: Session = Depends(get_db),
    user_id: Optional[int] = Query(None, description="Filter by user ID."),
    status: Optional[models.TransactionStatus] = Query(None, description="Filter by transaction status."),
    transaction_type: Optional[models.TransactionType] = Query(None, description="Filter by transaction type."),
    start_date: Optional[datetime.date] = Query(None, description="Filter transactions created on or after this date (YYYY-MM-DD)."),
    end_date: Optional[datetime.date] = Query(None, description="Filter transactions created on or before this date (YYYY-MM-DD)."),
    min_amount: Optional[float] = Query(None, description="Filter by minimum transaction amount."),
    max_amount: Optional[float] = Query(None, description="Filter by maximum transaction amount."),
    search_term: Optional[str] = Query(None, description="Search by description."),
    skip: int = Query(0, ge=0, description="Number of records to skip (for pagination)."),
    limit: int = Query(100, le=1000, description="Maximum number of records to return (for pagination)."),
):
    """
    **Lists all transactions with comprehensive filtering, searching, and pagination.**
    """
    query = db.query(models.Transaction)

    if user_id is not None:
        query = query.filter(models.Transaction.user_id == user_id)
    if status is not None:
        query = query.filter(models.Transaction.status == status)
    if transaction_type is not None:
        query = query.filter(models.Transaction.transaction_type == transaction_type)
    
    if start_date is not None:
        # Filter by timestamp greater than or equal to the start of the start_date
        query = query.filter(models.Transaction.timestamp >= start_date)
    if end_date is not None:
        # Filter by timestamp less than the start of the day *after* the end_date
        # This ensures transactions on end_date are included up to 23:59:59
        next_day = end_date + datetime.timedelta(days=1)
        query = query.filter(models.Transaction.timestamp < next_day)

    if min_amount is not None:
        query = query.filter(models.Transaction.amount >= min_amount)
    if max_amount is not None:
        query = query.filter(models.Transaction.amount <= max_amount)

    if search_term:
        # Case-insensitive search on the description field
        query = query.filter(models.Transaction.description.ilike(f"%{search_term}%"))

    # Default sorting by timestamp descending (most recent first)
    query = query.order_by(models.Transaction.timestamp.desc())

    transactions = query.offset(skip).limit(limit).all()
    logger.info(f"Retrieved {len(transactions)} transactions with filters.")
    return transactions

# --- Analytics Endpoint ---

@router.get("/analytics", response_model=models.TransactionAnalytics)
def get_transaction_analytics(
    db: Session = Depends(get_db),
    user_id: Optional[int] = Query(None, description="Filter analytics by user ID."),
    start_date: Optional[datetime.date] = Query(None, description="Start date for the analytics period (YYYY-MM-DD)."),
    end_date: Optional[datetime.date] = Query(None, description="End date for the analytics period (YYYY-MM-DD)."),
):
    """
    **Provides summary analytics for transactions based on filters.**
    """
    query = db.query(models.Transaction)

    if user_id is not None:
        query = query.filter(models.Transaction.user_id == user_id)
    
    if start_date is not None:
        query = query.filter(models.Transaction.timestamp >= start_date)
    if end_date is not None:
        next_day = end_date + datetime.timedelta(days=1)
        query = query.filter(models.Transaction.timestamp < next_day)

    # 1. Total transactions and total amount
    total_transactions = query.count()
    total_amount_result = query.with_entities(func.sum(models.Transaction.amount)).scalar()
    total_amount = total_amount_result if total_amount_result is not None else 0.0

    # 2. Completed and Failed counts
    completed_transactions = query.filter(models.Transaction.status == models.TransactionStatus.COMPLETED).count()
    failed_transactions = query.filter(or_(
        models.Transaction.status == models.TransactionStatus.FAILED,
        models.Transaction.status == models.TransactionStatus.CANCELLED
    )).count()

    # 3. Summary by type
    summary_by_type_results = (
        query.with_entities(
            models.Transaction.transaction_type,
            func.sum(models.Transaction.amount)
        )
        .group_by(models.Transaction.transaction_type)
        .all()
    )
    summary_by_type = {
        item[0]: item[1] for item in summary_by_type_results
    }

    analytics_data = models.TransactionAnalytics(
        total_transactions=total_transactions,
        total_amount=total_amount,
        completed_transactions=completed_transactions,
        failed_transactions=failed_transactions,
        summary_by_type=summary_by_type
    )
    logger.info(f"Generated analytics: Total transactions {total_transactions}")
    return analytics_data

# --- Export Endpoint ---

@router.get("/export", response_model=None)
def export_transactions(
    db: Session = Depends(get_db),
    user_id: Optional[int] = Query(None, description="Filter by user ID for export."),
    status: Optional[models.TransactionStatus] = Query(None, description="Filter by transaction status for export."),
    start_date: Optional[datetime.date] = Query(None, description="Start date for the export period (YYYY-MM-DD)."),
    end_date: Optional[datetime.date] = Query(None, description="End date for the export period (YYYY-MM-DD)."),
):
    """
    **Exports filtered transaction data as a CSV file.**
    """
    query = db.query(models.Transaction)

    if user_id is not None:
        query = query.filter(models.Transaction.user_id == user_id)
    if status is not None:
        query = query.filter(models.Transaction.status == status)
    
    if start_date is not None:
        query = query.filter(models.Transaction.timestamp >= start_date)
    if end_date is not None:
        next_day = end_date + datetime.timedelta(days=1)
        query = query.filter(models.Transaction.timestamp < next_day)

    transactions = query.order_by(models.Transaction.timestamp.desc()).all()

    # Use an in-memory text buffer
    output = io.StringIO()
    writer = csv.writer(output)

    # Write header
    header = ["ID", "User ID", "Type", "Amount", "Currency", "Status", "Timestamp", "Description", "Metadata"]
    writer.writerow(header)

    # Write data rows
    for t in transactions:
        metadata_str = str(t.metadata_json) if t.metadata_json else ""
        row = [
            t.id,
            t.user_id,
            t.transaction_type.value,
            t.amount,
            t.currency,
            t.status.value,
            t.timestamp.isoformat(),
            t.description,
            metadata_str
        ]
        writer.writerow(row)

    output.seek(0)
    
    logger.info(f"Exported {len(transactions)} transactions to CSV.")
    
    # Return a StreamingResponse with the CSV data
    filename = f"transactions_export_{datetime.date.today().isoformat()}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

# --- FastAPI Application Setup (for local testing/running) ---

if __name__ == "__main__":
    from fastapi import FastAPI
    from .config import engine
    from .models import init_db

    # Initialize the database (create tables)
    init_db(engine)

    app = FastAPI(
        title="Transaction History Service",
        description="Complete transaction tracking with search, export, and analytics.",
        version="1.0.0",
    )
    app.include_router(router)

    # Example of running the app (requires uvicorn)
    # import uvicorn
    # uvicorn.run(app, host="0.0.0.0", port=8000)
    print("FastAPI app and router configured. Run with uvicorn to test.")
