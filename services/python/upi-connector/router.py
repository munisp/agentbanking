from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from service import UPITransactionService, TransactionNotFound, TransactionUpdateError, UPIServiceException
from schemas import UPITransactionCreate, UPITransactionRead, UPITransactionUpdate, UPITransactionList, ErrorResponse

router = APIRouter(
    prefix="/transactions",
    tags=["UPI Transactions"],
    responses={404: {"description": "Not found"}},
)

# Dependency to get the service instance
def get_upi_service(db: Session = Depends(get_db)) -> UPITransactionService:
    return UPITransactionService(db)

@router.post(
    "/", 
    response_model=UPITransactionRead, 
    status_code=status.HTTP_201_CREATED,
    summary="Initiate a new UPI Transaction",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid input or transaction creation failed"}
    }
)
def create_transaction(
    transaction_in: UPITransactionCreate,
    service: UPITransactionService = Depends(get_upi_service)
) -> None:
    """
    Initiates a new UPI transaction request. This typically sends a request to the PSP/Bank 
    and records the initial PENDING state in the database.
    """
    try:
        db_transaction = service.create_transaction(transaction_in)
        return db_transaction
    except UPIServiceException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

@router.get(
    "/{transaction_id}", 
    response_model=UPITransactionRead,
    summary="Get a transaction by its external ID",
    responses={
        404: {"model": ErrorResponse, "description": "Transaction not found"}
    }
)
def read_transaction(
    transaction_id: str,
    service: UPITransactionService = Depends(get_upi_service)
) -> None:
    """
    Retrieves the details of a UPI transaction using the external `transaction_id`.
    """
    try:
        db_transaction = service.get_transaction_by_id(transaction_id)
        return db_transaction
    except TransactionNotFound as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

@router.get(
    "/", 
    response_model=UPITransactionList,
    summary="List all transactions",
)
def list_transactions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=1000),
    service: UPITransactionService = Depends(get_upi_service)
) -> None:
    """
    Retrieves a list of all UPI transactions with pagination.
    """
    transactions = service.list_transactions(skip=skip, limit=limit)
    return UPITransactionList(transactions=transactions, total=len(transactions))

@router.patch(
    "/{transaction_id}", 
    response_model=UPITransactionRead,
    summary="Update transaction status (e.g., via webhook)",
    responses={
        404: {"model": ErrorResponse, "description": "Transaction not found"},
        400: {"model": ErrorResponse, "description": "Invalid update or final status reached"}
    }
)
def update_transaction(
    transaction_id: str,
    transaction_update: UPITransactionUpdate,
    service: UPITransactionService = Depends(get_upi_service)
) -> None:
    """
    Updates the status and details of an existing transaction. 
    This endpoint is typically used by webhooks from the PSP/Bank to notify of status changes.
    """
    try:
        db_transaction = service.update_transaction_status(transaction_id, transaction_update)
        return db_transaction
    except TransactionNotFound as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except TransactionUpdateError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

@router.delete(
    "/{transaction_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a transaction",
    responses={
        404: {"model": ErrorResponse, "description": "Transaction not found"}
    }
)
def delete_transaction(
    transaction_id: str,
    service: UPITransactionService = Depends(get_upi_service)
) -> Dict[str, Any]:
    """
    Deletes a transaction record. This should be used cautiously and typically only for cleanup or administrative purposes.
    """
    try:
        service.delete_transaction(transaction_id)
        return {"ok": True}
    except TransactionNotFound as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except UPIServiceException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)