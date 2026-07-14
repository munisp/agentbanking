import logging
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query
from pydantic import BaseModel, Field, validator

# --- Configuration and Dependencies ---

# Basic logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Dummy dependencies for demonstration
async def get_current_user(token: str = Query(..., description="Bearer token for authentication")) -> str:
    """A dummy dependency to simulate user authentication."""
    if token != "valid_token":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return "user_id_123"

async def rate_limiter() -> None:
    """A dummy dependency to simulate rate limiting."""
    # In a real application, this would check a cache (e.g., Redis)
    # for the number of requests from the client/user in a given time window.
    # For demonstration, we'll just pass.
    pass

async def get_cips_service() -> None:
    """A dummy dependency for service injection."""
    class CipsService:
        async def initiate_payment(self, payment_request: "PaymentInitiationRequest") -> "PaymentStatusResponse":
            # Simulate service logic
            logger.info(f"Initiating payment for user: {payment_request.beneficiary_name}")
            return PaymentStatusResponse(
                payment_id="CIPS-1234567890",
                status="PENDING",
                timestamp=datetime.now(),
                amount=payment_request.amount,
                currency=payment_request.currency
            )

        async def get_payment_status(self, payment_id: str) -> "PaymentStatusResponse":
            # Simulate service logic
            if payment_id == "CIPS-999":
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
            return PaymentStatusResponse(
                payment_id=payment_id,
                status="COMPLETED",
                timestamp=datetime.now(),
                amount=100.00,
                currency="CNY"
            )

        async def cancel_payment(self, payment_id: str) -> "PaymentStatusResponse":
            # Simulate service logic
            if payment_id == "CIPS-999":
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
            return PaymentStatusResponse(
                payment_id=payment_id,
                status="CANCELLED",
                timestamp=datetime.now(),
                amount=50.00,
                currency="CNY"
            )

        async def get_settlement_status(self, settlement_id: str) -> "SettlementStatusResponse":
            # Simulate service logic
            if settlement_id == "SETTLE-999":
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Settlement not found")
            return SettlementStatusResponse(
                settlement_id=settlement_id,
                status="SETTLED",
                settlement_date=datetime.now().date(),
                total_amount=10000.00,
                currency="CNY",
                payment_count=50
            )

        async def list_payments(self, skip: int, limit: int, sort_by: str, filter_status: Optional[str]) -> "PaginatedPaymentsResponse":
            # Simulate service logic
            payments = [
                PaymentStatusResponse(payment_id=f"CIPS-{i}", status="COMPLETED", timestamp=datetime.now(), amount=100.00, currency="CNY")
                for i in range(skip, skip + limit)
            ]
            return PaginatedPaymentsResponse(
                total=1000,
                skip=skip,
                limit=limit,
                data=payments
            )

    return CipsService()

# --- Pydantic Models ---

class PaymentInitiationRequest(BaseModel):
    """Request model for initiating a CIPS payment."""
    amount: float = Field(..., gt=0, description="The amount of the payment.")
    currency: str = Field(..., pattern="^[A-Z]{3}$", description="The currency code (e.g., CNY).")
    beneficiary_account: str = Field(..., description="The beneficiary's CIPS account number.")
    beneficiary_name: str = Field(..., description="The beneficiary's name.")
    reference_id: str = Field(..., description="A unique reference ID for the payment.")

    @validator('amount')
    def validate_amount_precision(cls, v) -> None:
        if round(v, 2) != v:
            raise ValueError('Amount must have at most two decimal places.')
        return v

class PaymentStatusResponse(BaseModel):
    """Response model for payment status."""
    payment_id: str = Field(..., description="The unique CIPS payment identifier.")
    status: str = Field(..., description="The current status of the payment (e.g., PENDING, COMPLETED, FAILED, CANCELLED).")
    timestamp: datetime = Field(..., description="The time of the last status update.")
    amount: float = Field(..., description="The amount of the payment.")
    currency: str = Field(..., description="The currency code.")

class PaginatedPaymentsResponse(BaseModel):
    """Paginated response model for a list of payments."""
    total: int = Field(..., description="Total number of payments matching the criteria.")
    skip: int = Field(..., description="Number of items skipped.")
    limit: int = Field(..., description="Maximum number of items returned.")
    data: List[PaymentStatusResponse] = Field(..., description="List of payment status records.")

class SettlementStatusResponse(BaseModel):
    """Response model for settlement status."""
    settlement_id: str = Field(..., description="The unique CIPS settlement identifier.")
    status: str = Field(..., description="The current status of the settlement (e.g., SETTLED, PENDING, FAILED).")
    settlement_date: datetime.date = Field(..., description="The date of the settlement.")
    total_amount: float = Field(..., description="The total amount settled.")
    currency: str = Field(..., description="The currency code.")
    payment_count: int = Field(..., description="The number of payments included in the settlement.")

# --- Background Task Function ---

def process_payment_async(payment_id: str) -> None:
    """Simulates a long-running background task for payment processing."""
    logger.info(f"Background task started for payment ID: {payment_id}")
    # In a real application, this would involve calling external CIPS APIs,
    # updating database records, etc.
    import time
    time.sleep(5) # Simulate work
    logger.info(f"Background task finished for payment ID: {payment_id}. Status updated to COMPLETED.")

# --- API Router ---

router = APIRouter(
    prefix="/cips/payments",
    tags=["CIPS Payments"],
    dependencies=[Depends(rate_limiter)], # Apply rate limiting to all endpoints
)

@router.post(
    "/initiate",
    response_model=PaymentStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Initiate a new CIPS payment",
    description="Submits a request to initiate a new CIPS cross-border payment. The payment is processed asynchronously."
)
async def initiate_payment(
    payment_request: PaymentInitiationRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user),
    cips_service: get_cips_service = Depends(get_cips_service)
) -> None:
    """
    Initiates a new CIPS payment.

    - **payment_request**: Details of the payment to be initiated.
    - **user_id**: Authenticated user ID (from dependency).
    - **cips_service**: Dependency-injected CIPS service instance.
    - **background_tasks**: Used to run the actual payment processing asynchronously.

    Returns a PENDING status immediately and starts a background task for processing.
    """
    logger.info(f"User {user_id} initiating payment: {payment_request.reference_id}")

    # 1. Validate input (handled by Pydantic)
    # 2. Persist initial record in DB (simulated by service call)
    initial_response = await cips_service.initiate_payment(payment_request)

    # 3. Start asynchronous processing
    background_tasks.add_task(process_payment_async, initial_response.payment_id)

    return initial_response

@router.get(
    "/{payment_id}",
    response_model=PaymentStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get the status of a specific payment",
    description="Retrieves the current status and details of a CIPS payment using its unique ID."
)
async def get_payment_status(
    payment_id: str = Field(..., description="The unique CIPS payment identifier."),
    user_id: str = Depends(get_current_user),
    cips_service: get_cips_service = Depends(get_cips_service)
) -> None:
    """
    Retrieves the current status of a CIPS payment.

    - **payment_id**: The ID of the payment to check.
    - **user_id**: Authenticated user ID.
    - **cips_service**: Dependency-injected CIPS service instance.

    Raises 404 if the payment is not found.
    """
    logger.info(f"User {user_id} requesting status for payment ID: {payment_id}")
    return await cips_service.get_payment_status(payment_id)

@router.get(
    "/",
    response_model=PaginatedPaymentsResponse,
    status_code=status.HTTP_200_OK,
    summary="List all payments with pagination, filtering, and sorting",
    description="Retrieves a paginated list of CIPS payments, allowing for filtering by status and sorting."
)
async def list_payments(
    skip: int = Query(0, ge=0, description="Number of items to skip (for pagination)."),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of items to return."),
    sort_by: str = Query("timestamp", description="Field to sort by (e.g., 'timestamp', 'amount')."),
    filter_status: Optional[str] = Query(None, description="Filter payments by status (e.g., 'COMPLETED', 'PENDING')."),
    user_id: str = Depends(get_current_user),
    cips_service: get_cips_service = Depends(get_cips_service)
) -> None:
    """
    Lists payments with support for pagination, filtering, and sorting.

    - **skip**: The offset for pagination.
    - **limit**: The maximum number of results to return.
    - **sort_by**: The field to sort the results by.
    - **filter_status**: Optional status to filter the results.
    - **user_id**: Authenticated user ID.
    - **cips_service**: Dependency-injected CIPS service instance.
    """
    logger.info(f"User {user_id} listing payments: skip={skip}, limit={limit}, sort_by={sort_by}, filter_status={filter_status}")
    return await cips_service.list_payments(skip, limit, sort_by, filter_status)

@router.put(
    "/{payment_id}/cancel",
    response_model=PaymentStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel an existing CIPS payment",
    description="Requests the cancellation of a CIPS payment. Only payments in PENDING status can typically be cancelled."
)
async def cancel_payment(
    payment_id: str = Field(..., description="The unique CIPS payment identifier."),
    user_id: str = Depends(get_current_user),
    cips_service: get_cips_service = Depends(get_cips_service)
) -> None:
    """
    Requests the cancellation of a CIPS payment.

    - **payment_id**: The ID of the payment to cancel.
    - **user_id**: Authenticated user ID.
    - **cips_service**: Dependency-injected CIPS service instance.

    Raises 404 if the payment is not found or 400 if the payment is not cancellable.
    """
    logger.warning(f"User {user_id} attempting to cancel payment ID: {payment_id}")
    # In a real scenario, the service would check if the payment is cancellable (e.g., status is PENDING)
    # If not cancellable: raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payment is not in a cancellable state.")
    return await cips_service.cancel_payment(payment_id)

@router.get(
    "/settlements/{settlement_id}",
    response_model=SettlementStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get the status of a specific settlement",
    description="Retrieves the current status and details of a CIPS settlement using its unique ID."
)
async def get_settlement_status(
    settlement_id: str = Field(..., description="The unique CIPS settlement identifier."),
    user_id: str = Depends(get_current_user),
    cips_service: get_cips_service = Depends(get_cips_service)
) -> None:
    """
    Retrieves the current status of a CIPS settlement.

    - **settlement_id**: The ID of the settlement to check.
    - **user_id**: Authenticated user ID.
    - **cips_service**: Dependency-injected CIPS service instance.

    Raises 404 if the settlement is not found.
    """
    logger.info(f"User {user_id} requesting status for settlement ID: {settlement_id}")
    return await cips_service.get_settlement_status(settlement_id)

# Total endpoints: 5
# 1. POST /cips/payments/initiate
# 2. GET /cips/payments/{payment_id}
# 3. GET /cips/payments/
# 4. PUT /cips/payments/{payment_id}/cancel
# 5. GET /cips/payments/settlements/{settlement_id}
