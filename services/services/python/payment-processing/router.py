import uuid
from typing import List, Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from service import PaymentService, NotFoundException, ConflictException, InvalidOperationException, ServiceException
from schemas import (
    MerchantCreate, MerchantUpdate, MerchantOut,
    PaymentMethodCreate, PaymentMethodOut,
    TransactionCreate, TransactionOut, TransactionFilter,
    RefundCreate, RefundOut,
    ListResponse
)
from models import Transaction

# --- Dependencies ---

def get_payment_service(db: Annotated[AsyncSession, Depends(get_db)]) -> PaymentService:
    """Dependency to get the PaymentService instance."""
    return PaymentService(db)

# Simulated Authentication Dependency
# In a real system, this would validate a header (e.g., X-API-Key) against the Merchant.api_key_hash
async def authenticate_merchant(merchant_id: Annotated[uuid.UUID, Query(description="The ID of the merchant making the request.")]) -> uuid.UUID:
    """Simulated merchant authentication."""
    # For simplicity, we just return the merchant_id, assuming it's valid for now.
    # A real implementation would check the API key and return the associated merchant ID.
    return merchant_id

# --- Routers ---

router = APIRouter(
    prefix="/api/v1",
    tags=["payment-processing"],
)

# --- Exception Handling Helper ---

def handle_service_exception(e: ServiceException) -> None:
    """Maps service exceptions to appropriate HTTP exceptions."""
    if isinstance(e, NotFoundException):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    elif isinstance(e, ConflictException):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.message)
    elif isinstance(e, InvalidOperationException):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)
    else:
        raise HTTPException(status_code=e.status_code, detail=e.message)

# --- Merchant Endpoints ---

@router.post("/merchants", response_model=MerchantOut, status_code=status.HTTP_201_CREATED, summary="Create a new Merchant")
async def create_merchant(
    merchant_in: MerchantCreate,
    service: Annotated[PaymentService, Depends(get_payment_service)]
) -> None:
    """Registers a new merchant account."""
    try:
        return await service.create_merchant(merchant_in)
    except ServiceException as e:
        handle_service_exception(e)

@router.get("/merchants/{merchant_id}", response_model=MerchantOut, summary="Get Merchant details")
async def get_merchant(
    merchant_id: uuid.UUID,
    service: Annotated[PaymentService, Depends(get_payment_service)]
) -> None:
    """Retrieves details for a specific merchant."""
    try:
        return await service.get_merchant(merchant_id)
    except ServiceException as e:
        handle_service_exception(e)

@router.put("/merchants/{merchant_id}", response_model=MerchantOut, summary="Update Merchant details")
async def update_merchant(
    merchant_id: uuid.UUID,
    merchant_in: MerchantUpdate,
    service: Annotated[PaymentService, Depends(get_payment_service)]
) -> None:
    """Updates details for a specific merchant."""
    try:
        return await service.update_merchant(merchant_id, merchant_in)
    except ServiceException as e:
        handle_service_exception(e)

@router.delete("/merchants/{merchant_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a Merchant")
async def delete_merchant(
    merchant_id: uuid.UUID,
    service: Annotated[PaymentService, Depends(get_payment_service)]
) -> None:
    """Deletes a merchant account."""
    try:
        await service.delete_merchant(merchant_id)
        return
    except ServiceException as e:
        handle_service_exception(e)

# --- Payment Method Endpoints ---

@router.post("/payment-methods", response_model=PaymentMethodOut, status_code=status.HTTP_201_CREATED, summary="Store a new Payment Method token")
async def create_payment_method(
    pm_in: PaymentMethodCreate,
    service: Annotated[PaymentService, Depends(get_payment_service)]
) -> None:
    """Stores a new tokenized payment method for future use."""
    try:
        return await service.create_payment_method(pm_in)
    except ServiceException as e:
        handle_service_exception(e)

@router.get("/payment-methods/{pm_id}", response_model=PaymentMethodOut, summary="Get Payment Method details")
async def get_payment_method(
    pm_id: uuid.UUID,
    service: Annotated[PaymentService, Depends(get_payment_service)]
) -> None:
    """Retrieves details for a specific payment method."""
    try:
        return await service.get_payment_method(pm_id)
    except ServiceException as e:
        handle_service_exception(e)

# --- Transaction Endpoints ---

@router.post("/transactions", response_model=TransactionOut, status_code=status.HTTP_201_CREATED, summary="Process a new Transaction (Payment)")
async def create_transaction(
    transaction_in: TransactionCreate,
    service: Annotated[PaymentService, Depends(get_payment_service)],
    # merchant_id: Annotated[uuid.UUID, Depends(authenticate_merchant)] # Use this for real auth
) -> None:
    """Processes a new payment transaction using a stored payment method."""
    try:
        # transaction_in.merchant_id = merchant_id # Set merchant_id from auth
        return await service.create_transaction(transaction_in)
    except ServiceException as e:
        handle_service_exception(e)

@router.get("/transactions/{transaction_id}", response_model=TransactionOut, summary="Get Transaction details")
async def get_transaction(
    transaction_id: uuid.UUID,
    service: Annotated[PaymentService, Depends(get_payment_service)]
) -> None:
    """Retrieves details for a specific transaction."""
    try:
        return await service.get_transaction(transaction_id)
    except ServiceException as e:
        handle_service_exception(e)

@router.get("/transactions", response_model=List[TransactionOut], summary="List Transactions with Filters")
async def list_transactions(
    service: Annotated[PaymentService, Depends(get_payment_service)],
    merchant_id: Optional[uuid.UUID] = Query(None, description="Filter by Merchant ID"),
    status: Optional[str] = Query(None, description="Filter by Transaction Status (e.g., SUCCESS, FAILED)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=100)
) -> None:
    """Lists transactions based on provided filters and pagination."""
    filters = TransactionFilter(
        merchant_id=merchant_id,
        status=status,
        # start_date and end_date can be added to the query parameters if needed
    )
    try:
        transactions = await service.list_transactions(filters, skip=skip, limit=limit)
        # Note: A proper ListResponse schema would include total count, but we return a simple list for brevity
        return transactions
    except ServiceException as e:
        handle_service_exception(e)

# --- Refund Endpoints ---

@router.post("/refunds", response_model=RefundOut, status_code=status.HTTP_201_CREATED, summary="Process a new Refund")
async def create_refund(
    refund_in: RefundCreate,
    service: Annotated[PaymentService, Depends(get_payment_service)],
    # merchant_id: Annotated[uuid.UUID, Depends(authenticate_merchant)] # Use this for real auth
) -> None:
    """Processes a refund for a successful transaction."""
    try:
        # Logic to ensure the transaction belongs to the authenticated merchant would go here
        return await service.create_refund(refund_in)
    except ServiceException as e:
        handle_service_exception(e)

@router.get("/refunds/{refund_id}", response_model=RefundOut, summary="Get Refund details")
async def get_refund(
    refund_id: uuid.UUID,
    service: Annotated[PaymentService, Depends(get_payment_service)]
) -> None:
    """Retrieves details for a specific refund."""
    try:
        return await service.get_refund(refund_id)
    except ServiceException as e:
        handle_service_exception(e)
