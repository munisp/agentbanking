from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import schemas
from database import get_db
from service import upi_service, NotFoundException, ConflictException, PaymentGatewayException

router = APIRouter(
    prefix="/api/v1/upi",
    tags=["UPI Transactions"],
)

# --- Dependency for Service ---
def get_upi_service() -> None:
    return upi_service

# --- Transaction Endpoints ---

@router.post(
    "/transactions",
    response_model=schemas.TransactionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Initiate a new UPI Transaction"
)
def create_transaction(
    transaction_data: schemas.TransactionCreate,
    db: Session = Depends(get_db),
    service=Depends(get_upi_service)
) -> None:
    """
    Initiate a new UPI transaction. This will create a record in the database
    and attempt to initiate the payment with the external Payment Gateway.
    """
    try:
        return service.create_transaction(db, transaction_data)
    except ConflictException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except PaymentGatewayException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get(
    "/transactions/{order_id}",
    response_model=schemas.TransactionResponse,
    summary="Get Transaction Details by Order ID"
)
def get_transaction_by_order_id(
    order_id: str,
    db: Session = Depends(get_db),
    service=Depends(get_upi_service)
) -> None:
    """
    Retrieve the details of a specific transaction using the merchant's Order ID.
    """
    try:
        return service.get_transaction_by_order_id(db, order_id)
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@router.get(
    "/transactions",
    response_model=schemas.TransactionListResponse,
    summary="List all Transactions"
)
def list_transactions(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    service=Depends(get_upi_service)
) -> None:
    """
    Retrieve a list of all transactions with pagination.
    """
    transactions = service.list_transactions(db, skip=skip, limit=limit)
    total = service.count_transactions(db)
    return schemas.TransactionListResponse(total=total, transactions=transactions)

# --- Refund Endpoints ---

@router.post(
    "/refunds",
    response_model=schemas.RefundResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Initiate a Refund"
)
def create_refund(
    refund_data: schemas.RefundCreate,
    db: Session = Depends(get_db),
    service=Depends(get_upi_service)
) -> None:
    """
    Initiate a refund for a successful transaction.
    """
    try:
        return service.create_refund(db, refund_data)
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ConflictException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except PaymentGatewayException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get(
    "/transactions/{transaction_id}/refunds",
    response_model=List[schemas.RefundResponse],
    summary="List Refunds for a Transaction"
)
def list_refunds_for_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    service=Depends(get_upi_service)
) -> None:
    """
    Retrieve a list of all refunds associated with a specific transaction ID.
    """
    return service.list_refunds_by_transaction(db, transaction_id)

# --- Webhook Endpoint (Internal/PG Only) ---

@router.post(
    "/webhooks",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Receive and Process Webhook Events from Payment Gateway"
)
def receive_webhook(
    event_data: schemas.WebhookEventCreate,
    db: Session = Depends(get_db),
    service=Depends(get_upi_service)
) -> Dict[str, Any]:
    """
    Endpoint for the Payment Gateway to send transaction status updates.
    This endpoint should be secured with appropriate authentication/signature verification
    in a production environment.
    """
    try:
        # Note: In a real-world scenario, we would add signature verification middleware here.
        service.process_webhook_event(db, event_data)
        return {"message": "Webhook received and processing initiated."}
    except ConflictException as e:
        # Return 200/202 for duplicate webhooks to prevent PG from retrying
        return {"message": f"Webhook already processed: {str(e)}"}
    except Exception as e:
        # Log the error but return a success status to the PG to prevent excessive retries
        # The internal error should be handled by monitoring/alerting
        print(f"Internal error processing webhook: {e}")
        return {"message": "Webhook received, but internal processing failed."}