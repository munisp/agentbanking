from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from service import CipsTransactionService, TransactionNotFoundError, TransactionAlreadyExistsError, ServiceException
from schemas import CipsTransactionCreate, CipsTransactionUpdate, CipsTransaction, MessageResponse

router = APIRouter(
    prefix="/transactions",
    tags=["CIPS Transactions"],
    responses={404: {"description": "Not found"}},
)

@router.post(
    "/", 
    response_model=CipsTransaction, 
    status_code=status.HTTP_201_CREATED,
    summary="Create a new CIPS Transaction"
)
def create_transaction(transaction: CipsTransactionCreate, db: Session = Depends(get_db)) -> None:
    """
    Creates a new CIPS transaction record in the database.
    The initial status is always set to PENDING.
    """
    try:
        service = CipsTransactionService(db)
        return service.create_transaction(transaction)
    except TransactionAlreadyExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.message)
    except ServiceException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.get(
    "/", 
    response_model=List[CipsTransaction],
    summary="List all CIPS Transactions"
)
def list_transactions(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)) -> None:
    """
    Retrieves a list of all CIPS transactions with optional pagination.
    """
    service = CipsTransactionService(db)
    return service.list_transactions(skip=skip, limit=limit)

@router.get(
    "/{transaction_id}", 
    response_model=CipsTransaction,
    summary="Get a CIPS Transaction by internal ID"
)
def get_transaction(transaction_id: int, db: Session = Depends(get_db)) -> None:
    """
    Retrieves a single CIPS transaction by its internal database ID.
    """
    try:
        service = CipsTransactionService(db)
        return service.get_transaction_by_id(transaction_id)
    except TransactionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)

@router.patch(
    "/{transaction_id}/status", 
    response_model=CipsTransaction,
    summary="Update the status of a CIPS Transaction"
)
def update_transaction_status(
    transaction_id: int, 
    update_data: CipsTransactionUpdate, 
    db: Session = Depends(get_db)
) -> None:
    """
    Updates the status of an existing CIPS transaction.
    """
    try:
        service = CipsTransactionService(db)
        return service.update_transaction_status(transaction_id, update_data)
    except TransactionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    except ServiceException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.delete(
    "/{transaction_id}", 
    response_model=MessageResponse,
    summary="Delete a CIPS Transaction"
)
def delete_transaction(transaction_id: int, db: Session = Depends(get_db)) -> None:
    """
    Deletes a CIPS transaction record by its internal database ID.
    """
    try:
        service = CipsTransactionService(db)
        service.delete_transaction(transaction_id)
        return MessageResponse(message=f"Transaction with ID {transaction_id} successfully deleted.")
    except TransactionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    except ServiceException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
