import logging
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from database import get_db
from service import (
    PartyService, TransactionService, FXRateService,
    NotFoundError, ConflictError, InvalidTransactionError
)
from schemas import (
    PartyCreate, PartyUpdate, PartyRead,
    TransactionCreate, TransactionUpdate, TransactionRead,
    FXRateCreate, FXRateRead,
    PaginatedPartyResponse, PaginatedTransactionResponse, PaginatedFXRateResponse,
    TransactionStatus
)

# --- Configuration and Logging ---
from config import settings
logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL)

router = APIRouter(prefix="/api/v1", tags=["cross-border"])

# --- Exception Handlers ---

def handle_service_errors(e: Exception) -> None:
    if isinstance(e, NotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    elif isinstance(e, ConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    elif isinstance(e, InvalidTransactionError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    else:
        logger.error(f"Unhandled exception: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred.")

# --- Party Endpoints ---

@router.post("/parties", response_model=PartyRead, status_code=status.HTTP_201_CREATED, summary="Create a new Party (Sender/Receiver)")
def create_party(party_in: PartyCreate, db: Session = Depends(get_db)) -> None:
    """Creates a new party involved in cross-border transactions."""
    try:
        service = PartyService(db)
        return service.create_party(party_in)
    except Exception as e:
        handle_service_errors(e)

@router.get("/parties", response_model=PaginatedPartyResponse, summary="List all Parties")
def list_parties(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=1000),
    db: Session = Depends(get_db)
) -> None:
    """Retrieves a paginated list of all parties."""
    try:
        service = PartyService(db)
        parties = service.get_parties(skip=skip, limit=limit)
        total = service.count_parties()
        return PaginatedPartyResponse(
            total=total,
            page=skip // limit + 1,
            size=len(parties),
            items=[PartyRead.model_validate(p) for p in parties]
        )
    except Exception as e:
        handle_service_errors(e)

@router.get("/parties/{party_id}", response_model=PartyRead, summary="Get a Party by ID")
def get_party(party_id: int, db: Session = Depends(get_db)) -> None:
    """Retrieves a single party by its ID."""
    try:
        service = PartyService(db)
        return service.get_party(party_id)
    except Exception as e:
        handle_service_errors(e)

@router.put("/parties/{party_id}", response_model=PartyRead, summary="Update a Party")
def update_party(party_id: int, party_in: PartyUpdate, db: Session = Depends(get_db)) -> None:
    """Updates an existing party's details."""
    try:
        service = PartyService(db)
        return service.update_party(party_id, party_in)
    except Exception as e:
        handle_service_errors(e)

@router.delete("/parties/{party_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a Party")
def delete_party(party_id: int, db: Session = Depends(get_db)) -> None:
    """Deletes a party. Fails if the party is associated with any transactions."""
    try:
        service = PartyService(db)
        service.delete_party(party_id)
        return
    except Exception as e:
        handle_service_errors(e)

# --- Transaction Endpoints ---

@router.post("/transactions", response_model=TransactionRead, status_code=status.HTTP_201_CREATED, summary="Create a new Cross-Border Transaction")
def create_transaction(transaction_in: TransactionCreate, db: Session = Depends(get_db)) -> None:
    """
    Initiates a new cross-border transaction. 
    The service layer handles FX rate lookup, target amount calculation, and compliance checks.
    """
    try:
        service = TransactionService(db)
        return service.create_transaction(transaction_in)
    except Exception as e:
        handle_service_errors(e)

@router.get("/transactions", response_model=PaginatedTransactionResponse, summary="List all Transactions")
def list_transactions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=1000),
    status_filter: Optional[TransactionStatus] = Query(None, alias="status"),
    db: Session = Depends(get_db)
) -> None:
    """Retrieves a paginated list of all transactions, with optional status filtering."""
    try:
        service = TransactionService(db)
        transactions = service.get_transactions(skip=skip, limit=limit, status=status_filter)
        total = service.count_transactions(status=status_filter)
        return PaginatedTransactionResponse(
            total=total,
            page=skip // limit + 1,
            size=len(transactions),
            items=[TransactionRead.model_validate(t) for t in transactions]
        )
    except Exception as e:
        handle_service_errors(e)

@router.get("/transactions/{transaction_id}", response_model=TransactionRead, summary="Get a Transaction by ID")
def get_transaction(transaction_id: int, db: Session = Depends(get_db)) -> None:
    """Retrieves a single transaction by its ID, including sender and receiver details."""
    try:
        service = TransactionService(db)
        return service.get_transaction(transaction_id)
    except Exception as e:
        handle_service_errors(e)

@router.patch("/transactions/{transaction_id}", response_model=TransactionRead, summary="Update Transaction Status")
def update_transaction(transaction_id: int, transaction_in: TransactionUpdate, db: Session = Depends(get_db)) -> None:
    """Updates the status and/or status detail of an existing transaction."""
    try:
        service = TransactionService(db)
        return service.update_transaction(transaction_id, transaction_in)
    except Exception as e:
        handle_service_errors(e)

@router.delete("/transactions/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a Transaction")
def delete_transaction(transaction_id: int, db: Session = Depends(get_db)) -> None:
    """Deletes a transaction. Only allowed for PENDING, FAILED, or CANCELLED transactions."""
    try:
        service = TransactionService(db)
        service.delete_transaction(transaction_id)
        return
    except Exception as e:
        handle_service_errors(e)

# --- FXRate Endpoints ---

@router.post("/fx-rates", response_model=FXRateRead, status_code=status.HTTP_201_CREATED, summary="Add a new FX Rate")
def create_fx_rate(rate_in: FXRateCreate, db: Session = Depends(get_db)) -> None:
    """Adds a new foreign exchange rate to the system."""
    try:
        service = FXRateService(db)
        return service.create_rate(rate_in)
    except Exception as e:
        handle_service_errors(e)

@router.get("/fx-rates/latest", response_model=FXRateRead, summary="Get the latest FX Rate for a pair")
def get_latest_fx_rate(
    base_currency: str = Query(..., min_length=3, max_length=3),
    target_currency: str = Query(..., min_length=3, max_length=3),
    db: Session = Depends(get_db)
) -> None:
    """Retrieves the most recently recorded FX rate for a given currency pair."""
    if base_currency.upper() == target_currency.upper():
        from models import FXRate as FXRateModel
        from datetime import datetime
        return FXRateRead(
            id=0,
            from_currency=base_currency.upper(),
            to_currency=target_currency.upper(),
            rate=Decimal("1.000000"),
            source="system",
            strategy="same-currency",
            tenant_id="default",
            created_at=datetime.utcnow(),
        )
    try:
        service = FXRateService(db)
        return service.get_latest_rate(base_currency, target_currency)
    except Exception as e:
        handle_service_errors(e)