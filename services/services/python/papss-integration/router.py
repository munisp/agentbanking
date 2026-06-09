from typing import List
from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session

from . import schemas, service
from .database import get_db

router = APIRouter(
    prefix="/transactions",
    tags=["Payment Transactions"],
    responses={404: {"description": "Not found"}},
)

# Dependency to get the service instance
def get_service(db: Session = Depends(get_db)) -> service.PapssIntegrationService:
    return service.PapssIntegrationService(db)

@router.post(
    "/", 
    response_model=schemas.PaymentTransactionResponse, 
    status_code=status.HTTP_201_CREATED,
    summary="Create a new payment transaction"
)
def create_transaction(
    transaction: schemas.PaymentTransactionCreate,
    service: service.PapssIntegrationService = Depends(get_service)
) -> None:
    """
    Creates a new PAPSS payment transaction record.
    
    - **papss_ref_id**: Unique ID for the transaction.
    - **amount**: The transaction amount (must be > 0).
    - **currency_code**: ISO 4217 currency code.
    """
    try:
        return service.create_transaction(transaction)
    except service.TransactionAlreadyExistsError as e:
        raise e

@router.get(
    "/", 
    response_model=List[schemas.PaymentTransactionResponse],
    summary="List all payment transactions"
)
def list_transactions(
    skip: int = 0, 
    limit: int = 100,
    service: service.PapssIntegrationService = Depends(get_service)
) -> None:
    """
    Retrieves a list of all payment transactions with optional pagination.
    """
    return service.get_transactions(skip=skip, limit=limit)

@router.get(
    "/{transaction_id}", 
    response_model=schemas.PaymentTransactionResponse,
    summary="Get a single payment transaction by ID"
)
def get_transaction(
    transaction_id: int,
    service: service.PapssIntegrationService = Depends(get_service)
) -> None:
    """
    Retrieves a single payment transaction by its internal database ID.
    """
    try:
        return service.get_transaction(transaction_id)
    except service.TransactionNotFoundError as e:
        raise e

@router.put(
    "/{transaction_id}", 
    response_model=schemas.PaymentTransactionResponse,
    summary="Update a payment transaction status/details"
)
def update_transaction(
    transaction_id: int,
    update_data: schemas.PaymentTransactionUpdate,
    service: service.PapssIntegrationService = Depends(get_service)
) -> None:
    """
    Updates the status, error code, or error message of a payment transaction.
    """
    try:
        return service.update_transaction(transaction_id, update_data)
    except service.TransactionNotFoundError as e:
        raise e
    except service.InvalidTransactionStateError as e:
        raise e

@router.delete(
    "/{transaction_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a payment transaction"
)
def delete_transaction(
    transaction_id: int,
    service: service.PapssIntegrationService = Depends(get_service)
) -> Dict[str, Any]:
    """
    Deletes a payment transaction record by its internal database ID.
    """
    try:
        service.delete_transaction(transaction_id)
        return {"ok": True}
    except service.TransactionNotFoundError as e:
        raise e
