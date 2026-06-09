from typing import List
from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from schemas import (
    FPSTransaction,
    FPSTransactionCreate,
    FPSTransactionUpdate,
    FPSWebhookIn,
    APIResponse
)
from service import FPSService, TransactionNotFoundException, TransactionAlreadyExistsException, ServiceException
from config import settings

# --- Security Dependency ---

def get_api_key(api_key: str = Depends(lambda x: x.headers.get("X-API-Key"))) -> None:
    """Simple API Key dependency for demonstration."""
    if api_key != settings.SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
        )
    return api_key

# --- Router Setup ---

router = APIRouter(
    prefix="/transactions",
    tags=["FPS Transactions"],
    dependencies=[Depends(get_api_key)], # Apply API key security to all transaction endpoints
    responses={404: {"description": "Not found"}},
)

webhook_router = APIRouter(
    prefix="/webhooks",
    tags=["FPS Webhooks"],
)

# --- Transaction Endpoints (CRUD) ---

@router.post(
    "/",
    response_model=FPSTransaction,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new FPS transaction request",
)
def create_transaction(
    transaction: FPSTransactionCreate, db: Session = Depends(get_db)
) -> None:
    """
    Submits a new transaction request to be processed by the FPS integration.
    """
    try:
        service = FPSService(db)
        return service.create_transaction(transaction)
    except (TransactionAlreadyExistsException, ServiceException) as e:
        raise e

@router.get(
    "/",
    response_model=List[FPSTransaction],
    summary="List all FPS transactions",
)
def list_transactions(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
) -> None:
    """
    Retrieves a list of all FPS transactions with pagination.
    """
    service = FPSService(db)
    return service.list_transactions(skip=skip, limit=limit)

@router.get(
    "/{transaction_id}",
    response_model=FPSTransaction,
    summary="Get a single FPS transaction by ID",
)
def get_transaction(
    transaction_id: int, db: Session = Depends(get_db)
) -> None:
    """
    Retrieves a single transaction by its unique ID.
    """
    try:
        service = FPSService(db)
        return service.get_transaction(transaction_id)
    except TransactionNotFoundException as e:
        raise e

@router.put(
    "/{transaction_id}",
    response_model=FPSTransaction,
    summary="Update an existing FPS transaction",
)
def update_transaction(
    transaction_id: int, update_data: FPSTransactionUpdate, db: Session = Depends(get_db)
) -> None:
    """
    Updates the status or details of an existing transaction.
    """
    try:
        service = FPSService(db)
        return service.update_transaction(transaction_id, update_data)
    except (TransactionNotFoundException, ServiceException) as e:
        raise e

@router.delete(
    "/{transaction_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an FPS transaction",
    response_class=APIResponse,
)
def delete_transaction(
    transaction_id: int, db: Session = Depends(get_db)
) -> None:
    """
    Deletes a transaction from the system.
    """
    try:
        service = FPSService(db)
        service.delete_transaction(transaction_id)
        return APIResponse(message=f"Transaction {transaction_id} deleted successfully.", status_code=status.HTTP_204_NO_CONTENT)
    except (TransactionNotFoundException, ServiceException) as e:
        raise e

# --- Webhook Endpoint ---

@webhook_router.post(
    "/",
    status_code=status.HTTP_200_OK,
    summary="Handle incoming FPS webhook notifications",
    response_model=APIResponse,
)
def handle_fps_webhook(
    webhook_data: FPSWebhookIn, db: Session = Depends(get_db)
) -> None:
    """
    Endpoint for the FPS provider to send status updates and notifications.
    This endpoint does not require the API key for external integration.
    """
    try:
        service = FPSService(db)
        result = service.handle_webhook(webhook_data)
        return APIResponse(message=result["message"], status_code=status.HTTP_200_OK)
    except ServiceException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while processing webhook: {e}"
        )
