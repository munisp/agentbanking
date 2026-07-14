import logging
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Mock rate limiting decorator
def rate_limit(limit: int, period: int) -> None:
    def decorator(func) -> None:
        # In a real application, this would implement rate limiting logic
        # For this mock, it just passes through
        return func
    return decorator

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Imports from the service file ---
from papss_models_and_service import (
    InitiateTransferRequest,
    TransferResponse,
    GetTransferStatusRequest,
    TransferStatusResponse,
    ReconcileTransactionsRequest,
    ReconciliationReportResponse,
    GetFeesRequest,
    FeesResponse,
    PAPSSService,
    get_papss_service,
    get_current_user,
    TransactionStatus
)

# --- Router Setup ---
router = APIRouter(
    prefix="/papss",
    tags=["PAPSS Services"],
    dependencies=[Depends(get_current_user)], # Apply authentication globally
    responses={404: {"description": "Not found"}},
)

# --- Background Task Placeholder ---
def process_transfer_async(transfer_id: str) -> None:
    """Placeholder for a background task to process the transfer."""
    logger.info(f"Starting background processing for transfer ID: {transfer_id}")
    # In a real system, this would involve calling external PAPSS APIs,
    # updating database status, sending notifications, etc.
    # time.sleep(5) # Simulate work
    logger.info(f"Finished background processing for transfer ID: {transfer_id}")

# --- Endpoints ---

@router.post(
    "/transfer/initiate",
    response_model=TransferResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Initiate a new PAPSS transfer",
    description="Initiates a new cross-border payment transfer via PAPSS. The transfer is processed asynchronously."
)
@rate_limit(limit=5, period=60)
async def initiate_transfer(
    request: InitiateTransferRequest,
    background_tasks: BackgroundTasks,
    papss_service: PAPSSService = Depends(get_papss_service),
    current_user: str = Depends(get_current_user)
) -> None:
    """
    Initiate a new PAPSS transfer.

    - **Input Validation**: Handled by Pydantic model `InitiateTransferRequest`.
    - **Authentication**: Handled by `get_current_user` dependency.
    - **Service Logic**: Handled by `papss_service.initiate_transfer`.
    - **Asynchronous Processing**: The core transfer processing is delegated to a background task.
    """
    logger.info(f"User {current_user} initiating transfer with reference: {request.reference_id}")

    try:
        # 1. Initial validation and record creation
        transfer_response = await papss_service.initiate_transfer(request)

        # 2. Delegate long-running process to background task
        background_tasks.add_task(process_transfer_async, transfer_response.papss_transfer_id)

        return transfer_response
    except Exception as e:
        logger.error(f"Error initiating transfer: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initiate transfer due to an internal error."
        )

@router.get(
    "/transfer/status",
    response_model=TransferStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get transfer status",
    description="Retrieves the current status and details of a specific transfer using either the PAPSS ID or the client reference ID."
)
@rate_limit(limit=10, period=60)
async def get_transfer_status(
    papss_transfer_id: Optional[str] = Query(None, description="PAPSS system transfer ID."),
    client_reference_id: Optional[str] = Query(None, description="Client's unique reference ID."),
    papss_service: PAPSSService = Depends(get_papss_service),
    current_user: str = Depends(get_current_user)
) -> None:
    """
    Retrieve the status of a transfer.

    - **Input Validation**: Ensures at least one ID is provided.
    - **Authentication**: Handled by `get_current_user` dependency.
    """
    if not papss_transfer_id and not client_reference_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide either 'papss_transfer_id' or 'client_reference_id'."
        )

    logger.info(f"User {current_user} querying status for PAPSS ID: {papss_transfer_id} or Ref ID: {client_reference_id}")

    try:
        status_response = await papss_service.get_transfer_status(papss_transfer_id, client_reference_id)
        return status_response
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error retrieving transfer status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve transfer status due to an internal error."
        )

@router.get(
    "/transactions/reconcile",
    response_model=ReconciliationReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Reconcile transactions",
    description="Retrieves a paginated, filterable, and sortable list of transactions for reconciliation."
)
@rate_limit(limit=2, period=300) # Lower rate limit for heavy report endpoint
async def reconcile_transactions(
    start_date: datetime = Query(..., description="Start date for the reconciliation period (ISO 8601 format)."),
    end_date: datetime = Query(..., description="End date for the reconciliation period (ISO 8601 format)."),
    status_filter: Optional[TransactionStatus] = Query(None, description="Filter by transaction status."),
    page: int = Query(1, ge=1, description="Page number for pagination."),
    page_size: int = Query(10, ge=1, le=100, description="Number of records per page."),
    sort_by: str = Query("created_at", description="Field to sort by (e.g., 'amount', 'created_at')."),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Sort order ('asc' or 'desc')."),
    papss_service: PAPSSService = Depends(get_papss_service),
    current_user: str = Depends(get_current_user)
) -> None:
    """
    Generate a paginated and filtered reconciliation report.

    - **Filtering**: By `start_date`, `end_date`, and optional `status_filter`.
    - **Pagination**: By `page` and `page_size`.
    - **Sorting**: By `sort_by` field and `sort_order`.
    """
    if start_date >= end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start date must be before end date."
        )

    logger.info(f"User {current_user} requesting reconciliation report from {start_date} to {end_date}")

    request_model = ReconcileTransactionsRequest(
        start_date=start_date,
        end_date=end_date,
        status_filter=status_filter,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order
    )

    try:
        report = await papss_service.reconcile_transactions(request_model)
        return report
    except Exception as e:
        logger.error(f"Error generating reconciliation report: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate report due to an internal error."
        )

@router.get(
    "/fees",
    response_model=FeesResponse,
    status_code=status.HTTP_200_OK,
    summary="Get transfer fees",
    description="Calculates and returns the estimated fees for a potential transfer based on amount, currency, and corridors."
)
@rate_limit(limit=20, period=60)
async def get_fees(
    amount: float = Query(..., gt=0, description="Amount for which to calculate fees."),
    currency: str = Query(..., max_length=3, min_length=3, description="Currency code (e.g., 'USD')."),
    source_country: str = Query(..., max_length=3, min_length=3, description="Source country code."),
    destination_country: str = Query(..., max_length=3, min_length=3, description="Destination country code."),
    papss_service: PAPSSService = Depends(get_papss_service),
    current_user: str = Depends(get_current_user)
) -> None:
    """
    Calculate the fees for a potential transfer.

    - **Input Validation**: Handled by Query parameters (e.g., `gt=0`, `max_length=3`).
    """
    logger.info(f"User {current_user} querying fees for {amount} {currency} from {source_country} to {destination_country}")

    request_model = GetFeesRequest(
        amount=amount,
        currency=currency,
        source_country=source_country,
        destination_country=destination_country
    )

    try:
        fees_response = await papss_service.get_fees(request_model)
        return fees_response
    except Exception as e:
        logger.error(f"Error calculating fees: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to calculate fees due to an internal error."
        )

# --- Additional Endpoints (PUT/DELETE for completeness, though not explicitly required by core PAPSS functions) ---

@router.put(
    "/transfer/{papss_transfer_id}/cancel",
    response_model=TransferResponse,
    status_code=status.HTTP_200_OK,
    summary="Request to cancel a pending transfer",
    description="Requests the cancellation of a transfer that is still in a pending state. Actual cancellation is not guaranteed."
)
@rate_limit(limit=5, period=60)
async def cancel_transfer(
    papss_transfer_id: str,
    papss_service: PAPSSService = Depends(get_papss_service),
    current_user: str = Depends(get_current_user)
) -> None:
    """
    Request to cancel a pending transfer.
    """
    logger.info(f"User {current_user} requesting cancellation for transfer ID: {papss_transfer_id}")
    # Mock cancellation logic
    try:
        # In a real service, this would call a cancellation method
        mock_response = await papss_service.get_transfer_status(papss_transfer_id, None)
        if mock_response.status == TransactionStatus.PENDING:
            mock_response.status = TransactionStatus.REVERSED
            mock_response.status_description = "Cancellation requested and successful (Mock)."
            return mock_response
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Transfer is not in a cancellable state."
            )
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transfer not found.")
    except Exception as e:
        logger.error(f"Error cancelling transfer: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to request cancellation due to an internal error."
        )

@router.delete(
    "/transfer/{papss_transfer_id}/data",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete transfer data (Administrative)",
    description="**ADMINISTRATIVE**: Deletes the record of a transfer. Requires elevated privileges."
)
@rate_limit(limit=1, period=3600)
async def delete_transfer_data(
    papss_transfer_id: str,
    current_user: str = Depends(get_current_user)
) -> None:
    """
    Deletes the record of a transfer.
    """
    # In a real application, this would check for admin privileges
    if current_user != "authenticated_user": # Mock check
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient privileges.")

    logger.warning(f"Admin user {current_user} deleting transfer data for ID: {papss_transfer_id}")
    # Mock deletion logic
    # In a real service, this would delete the record from the database
    return status.HTTP_204_NO_CONTENT
