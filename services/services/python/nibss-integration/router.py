from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from database import get_db
from schemas import (
    Transaction,
    TransactionCreate,
    TransactionUpdate,
    TransactionListResponse,
    NameEnquiryRequest,
    NameEnquiryResponse,
    Bank,
)
from service import (
    NIBSSService,
    get_nibss_service,
    TransactionNotFound,
    BankNotFound,
    ServiceException,
)

router = APIRouter(
    prefix="/api/v1",
    tags=["NIBSS Integration"],
)

# --- Exception Handlers ---

def handle_service_exception(e: ServiceException) -> None:
    """Converts a ServiceException into an HTTPException."""
    raise HTTPException(status_code=e.status_code, detail=e.message)

# --- Banks Endpoints ---

@router.get(
    "/banks/",
    response_model=List[Bank],
    summary="List all active NIBSS banks",
    description="Retrieves a list of all active banks and their NIBSS codes."
)
def list_banks(
    service: NIBSSService = Depends(get_nibss_service)
) -> None:
    """
    Retrieves a list of all active banks.
    """
    try:
        return service.get_all_banks()
    except ServiceException as e:
        handle_service_exception(e)

# --- Name Enquiry Endpoints ---

@router.post(
    "/name-enquiry/",
    response_model=NameEnquiryResponse,
    status_code=status.HTTP_200_OK,
    summary="Perform Account Name Enquiry",
    description="Validates an account number and bank code against the NIBSS Name Enquiry service."
)
def name_enquiry(
    request: NameEnquiryRequest,
    service: NIBSSService = Depends(get_nibss_service)
) -> None:
    """
    Performs a name enquiry and returns the account details.
    """
    try:
        return service.perform_name_enquiry(request)
    except BankNotFound as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)
    except ServiceException as e:
        handle_service_exception(e)

# --- Transaction Endpoints ---

@router.post(
    "/transactions/",
    response_model=Transaction,
    status_code=status.HTTP_201_CREATED,
    summary="Initiate NIBSS Instant Payment (NIP) Transaction",
    description="Creates a new transaction record and attempts to initiate the NIP transfer via the NIBSS API."
)
def create_transaction(
    transaction_data: TransactionCreate,
    service: NIBSSService = Depends(get_nibss_service)
) -> None:
    """
    Initiates a new NIP transaction.
    """
    try:
        return service.create_transaction(transaction_data)
    except BankNotFound as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)
    except ServiceException as e:
        handle_service_exception(e)

@router.get(
    "/transactions/",
    response_model=TransactionListResponse,
    summary="List Transactions",
    description="Retrieves a paginated list of all transactions."
)
def list_transactions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=1000),
    service: NIBSSService = Depends(get_nibss_service)
) -> None:
    """
    Retrieves a paginated list of transactions.
    """
    try:
        transactions, total = service.list_transactions(skip=skip, limit=limit)
        return TransactionListResponse(total=total, page=skip // limit + 1, size=len(transactions), items=transactions)
    except ServiceException as e:
        handle_service_exception(e)

@router.get(
    "/transactions/{transaction_ref}",
    response_model=Transaction,
    summary="Get Transaction Details",
    description="Retrieves the details of a specific transaction using its unique reference."
)
def get_transaction(
    transaction_ref: str,
    service: NIBSSService = Depends(get_nibss_service)
) -> None:
    """
    Retrieves a single transaction by reference.
    """
    try:
        return service.get_transaction_by_ref(transaction_ref)
    except TransactionNotFound as e:
        handle_service_exception(e)
    except ServiceException as e:
        handle_service_exception(e)

@router.put(
    "/transactions/{transaction_ref}",
    response_model=Transaction,
    summary="Update Transaction Status (Webhook/Internal)",
    description="Updates the status of a transaction. Primarily for internal use or NIBSS webhook integration."
)
def update_transaction(
    transaction_ref: str,
    update_data: TransactionUpdate,
    service: NIBSSService = Depends(get_nibss_service)
) -> None:
    """
    Updates a transaction's status and response details.
    """
    try:
        return service.update_transaction_status(transaction_ref, update_data)
    except TransactionNotFound as e:
        handle_service_exception(e)
    except ServiceException as e:
        handle_service_exception(e)

@router.delete(
    "/transactions/{transaction_ref}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Transaction",
    description="Deletes a transaction record. **Caution: Financial records are rarely deleted.**"
)
def delete_transaction(
    transaction_ref: str,
    service: NIBSSService = Depends(get_nibss_service)
) -> None:
    """
    Deletes a transaction by reference.
    """
    try:
        service.delete_transaction(transaction_ref)
        return
    except TransactionNotFound as e:
        handle_service_exception(e)
    except ServiceException as e:
        handle_service_exception(e)
