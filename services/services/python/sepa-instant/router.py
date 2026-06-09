from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from schemas import (
    SCTInstTransactionCreate,
    SCTInstTransactionResponse,
    SCTInstTransactionUpdate,
    TransactionRecallCreate,
    TransactionRecallResponse,
    StatusMessage
)
from service import SCTInstService, ServiceException, TransactionNotFoundError, InvalidTransactionStateError, RecallNotAllowedError

# --- Security Stub ---
# In a production environment, this would handle JWT/OAuth2 token validation
# and return the authenticated user object.
def get_current_user() -> Dict[str, Any]:
    """Placeholder for authentication dependency."""
    # For this task, we assume a successfully authenticated user
    return {"username": "api_user", "roles": ["admin", "processor"]}

# --- Router Definition ---
router = APIRouter(
    prefix="/transactions",
    tags=["SEPA Instant Transactions"],
    dependencies=[Depends(get_current_user)], # Apply security to all routes
    responses={404: {"description": "Not found"}},
)

# --- Service Dependency ---
def get_sct_inst_service(db: Session = Depends(get_db)) -> SCTInstService:
    """Dependency that provides the SCTInstService instance."""
    return SCTInstService(db)

# --- Transaction Endpoints (CRUD) ---

@router.post(
    "/",
    response_model=SCTInstTransactionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new SEPA Instant Credit Transfer (SCT Inst)",
    description="Initiates a new SCT Inst transaction and performs initial validation."
)
def create_transaction(
    transaction: SCTInstTransactionCreate,
    service: SCTInstService = Depends(get_sct_inst_service)
) -> None:
    try:
        return service.create_transaction(transaction)
    except ServiceException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.get(
    "/",
    response_model=List[SCTInstTransactionResponse],
    summary="List all SEPA Instant Credit Transfers",
    description="Retrieves a paginated list of all SCT Inst transactions."
)
def list_transactions(
    skip: int = 0,
    limit: int = 100,
    service: SCTInstService = Depends(get_sct_inst_service)
) -> None:
    return service.get_all_transactions(skip=skip, limit=limit)

@router.get(
    "/{transaction_id}",
    response_model=SCTInstTransactionResponse,
    summary="Get a SEPA Instant Credit Transfer by ID",
    description="Retrieves the details of a specific SCT Inst transaction."
)
def get_transaction(
    transaction_id: UUID,
    service: SCTInstService = Depends(get_sct_inst_service)
) -> None:
    try:
        return service.get_transaction_by_id(transaction_id)
    except TransactionNotFoundError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.put(
    "/{transaction_id}",
    response_model=SCTInstTransactionResponse,
    summary="Update SEPA Instant Credit Transfer status",
    description="Updates the status and related fields of an SCT Inst transaction (e.g., by a payment gateway)."
)
def update_transaction(
    transaction_id: UUID,
    update_data: SCTInstTransactionUpdate,
    service: SCTInstService = Depends(get_sct_inst_service)
) -> None:
    try:
        return service.update_transaction_status(transaction_id, update_data)
    except (TransactionNotFoundError, InvalidTransactionStateError) as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.delete(
    "/{transaction_id}",
    response_model=StatusMessage,
    summary="Delete a SEPA Instant Credit Transfer",
    description="Deletes a transaction. Only allowed for transactions in INITIATED or FAILED state."
)
def delete_transaction(
    transaction_id: UUID,
    service: SCTInstService = Depends(get_sct_inst_service)
) -> None:
    try:
        service.delete_transaction(transaction_id)
        return StatusMessage(
            message=f"Transaction {transaction_id} deleted successfully.",
            id=transaction_id,
            status_code=status.HTTP_200_OK
        )
    except (TransactionNotFoundError, InvalidTransactionStateError) as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

# --- Recall Endpoints ---

@router.post(
    "/{transaction_id}/recall",
    response_model=TransactionRecallResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Request a recall for a transaction",
    description="Initiates a recall request for a successfully credited transaction."
)
def request_recall(
    transaction_id: UUID,
    recall_data: TransactionRecallCreate,
    service: SCTInstService = Depends(get_sct_inst_service)
) -> None:
    try:
        return service.request_recall(transaction_id, recall_data)
    except (TransactionNotFoundError, InvalidTransactionStateError, RecallNotAllowedError) as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.put(
    "/recall/{recall_id}/finalize",
    response_model=TransactionRecallResponse,
    summary="Finalize a transaction recall",
    description="Simulates the Beneficiary Bank's response to a recall request."
)
def finalize_recall(
    recall_id: UUID,
    status_update: TransactionRecallResponse, # Reusing response schema for input, only need status, return_amount, return_fee
    service: SCTInstService = Depends(get_sct_inst_service)
) -> None:
    try:
        return service.finalize_recall(
            recall_id=recall_id,
            status=status_update.recall_status,
            return_amount=status_update.return_amount,
            return_fee=status_update.return_fee
        )
    except (TransactionNotFoundError, InvalidTransactionStateError, RecallNotAllowedError) as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)