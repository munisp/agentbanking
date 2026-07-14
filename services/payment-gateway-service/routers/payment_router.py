"""
Payment API Router

FastAPI router for payment operations including transaction creation,
status checks, refunds, and utility endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List
import logging

from ..schemas.payment_schemas import (
    PaymentInitiateRequest,
    PaymentInitiateResponse,
    PaymentVerifyRequest,
    PaymentVerifyResponse,
    RefundInitiateRequest,
    RefundInitiateResponse,
    ExchangeRateRequest,
    ExchangeRateResponse,
    FeeCalculationRequest,
    FeeCalculationResponse,
    AccountValidationRequest,
    AccountValidationResponse,
    TransactionListResponse,
    GatewayBalanceResponse,
    SupportedCurrenciesResponse,
    ErrorResponse
)
from ..services.payment_service import PaymentService
from ..services.gateway_factory import GatewayFactory
from ..services.base_gateway import PaymentGatewayError
from ...shared.database import get_db
from ...shared.dependencies.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/payments", tags=["payments"])


# Dependency to get payment service
def get_payment_service(db: Session = Depends(get_db)) -> PaymentService:
    """Get payment service instance."""
    # Production: Load gateway configs from database or config file
    gateway_configs = {
        "paystack": {"is_active": True, "priority": 10},
        "flutterwave": {"is_active": True, "priority": 20},
        "interswitch": {"is_active": True, "priority": 30},
        # ... other gateways
    }
    gateway_factory = GatewayFactory(gateway_configs)
    return PaymentService(db, gateway_factory)


@router.post(
    "/initiate",
    response_model=PaymentInitiateResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        500: {"model": ErrorResponse}
    },
    summary="Initiate a payment transaction",
    description="Create a new payment transaction with the specified gateway or auto-select the best gateway"
)
async def initiate_payment(
    request: PaymentInitiateRequest,
    current_user: dict = Depends(get_current_user),
    payment_service: PaymentService = Depends(get_payment_service)
) -> PaymentInitiateResponse:
    """
    Initiate a new payment transaction.
    
    - **amount**: Transaction amount (must be positive)
    - **currency**: Currency code (ISO 4217)
    - **recipient_id**: Recipient user ID
    - **gateway**: Payment gateway to use (or 'auto' for automatic selection)
    - **transaction_type**: Type of transaction (transfer, deposit, withdrawal)
    
    Returns payment initiation details including transaction ID and payment URL (if applicable).
    """
    try:
        user_id = current_user["user_id"]
        response = await payment_service.initiate_payment(request, user_id)
        return response
    except PaymentGatewayError as e:
        logger.error(f"Payment initiation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "error_code": e.error_code,
                "message": str(e),
                "details": e.details
            }
        )
    except Exception as e:
        logger.error(f"Unexpected error in payment initiation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error_code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred"
            }
        )


@router.post(
    "/verify",
    response_model=PaymentVerifyResponse,
    responses={
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse}
    },
    summary="Verify payment status",
    description="Check the current status of a payment transaction"
)
async def verify_payment(
    request: PaymentVerifyRequest,
    current_user: dict = Depends(get_current_user),
    payment_service: PaymentService = Depends(get_payment_service)
) -> PaymentVerifyResponse:
    """
    Verify the status of a payment transaction.
    
    - **transaction_id**: Transaction ID to verify
    
    Returns current transaction status and details.
    """
    try:
        response = await payment_service.verify_payment(request.transaction_id)
        return response
    except PaymentGatewayError as e:
        if e.error_code == "TRANSACTION_NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "success": False,
                    "error_code": e.error_code,
                    "message": str(e)
                }
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "error_code": e.error_code,
                "message": str(e)
            }
        )


@router.get(
    "/{transaction_id}",
    response_model=PaymentVerifyResponse,
    responses={
        404: {"model": ErrorResponse}
    },
    summary="Get transaction details",
    description="Retrieve details of a specific transaction"
)
async def get_transaction(
    transaction_id: str,
    current_user: dict = Depends(get_current_user),
    payment_service: PaymentService = Depends(get_payment_service)
) -> PaymentVerifyResponse:
    """
    Get details of a specific transaction.
    
    - **transaction_id**: Transaction ID
    
    Returns transaction details.
    """
    try:
        response = await payment_service.verify_payment(transaction_id)
        return response
    except PaymentGatewayError as e:
        if e.error_code == "TRANSACTION_NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "success": False,
                    "error_code": e.error_code,
                    "message": str(e)
                }
            )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/",
    response_model=TransactionListResponse,
    summary="List user transactions",
    description="Get a paginated list of transactions for the current user"
)
async def list_transactions(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: dict = Depends(get_current_user),
    payment_service: PaymentService = Depends(get_payment_service)
) -> TransactionListResponse:
    """
    List transactions for the current user.
    
    - **page**: Page number (starts at 1)
    - **page_size**: Number of items per page (max 100)
    
    Returns paginated list of transactions.
    """
    user_id = current_user["user_id"]
    skip = (page - 1) * page_size
    
    transactions = payment_service.get_user_transactions(user_id, skip, page_size)
    total = payment_service.get_transaction_count(user_id)
    
    transaction_responses = []
    for txn in transactions:
        transaction_responses.append(
            PaymentVerifyResponse(
                success=True,
                transaction_id=txn.transaction_id,
                gateway_reference=txn.gateway_reference,
                status=txn.status.value,
                amount=txn.amount,
                currency=txn.currency,
                fee=txn.fee,
                exchange_rate=txn.exchange_rate,
                sender_id=txn.user_id,
                recipient_id=txn.recipient_id,
                description=txn.description,
                initiated_at=txn.created_at,
                completed_at=txn.completed_at,
                message=None,
                metadata=txn.metadata
            )
        )
    
    return TransactionListResponse(
        success=True,
        transactions=transaction_responses,
        total=total,
        page=page,
        page_size=page_size
    )


@router.post(
    "/refund",
    response_model=RefundInitiateResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse}
    },
    summary="Initiate a refund",
    description="Request a refund for a completed transaction"
)
async def initiate_refund(
    request: RefundInitiateRequest,
    current_user: dict = Depends(get_current_user),
    payment_service: PaymentService = Depends(get_payment_service)
) -> RefundInitiateResponse:
    """
    Initiate a refund for a transaction.
    
    - **transaction_id**: Original transaction ID
    - **amount**: Refund amount (optional, defaults to full refund)
    - **reason**: Reason for refund
    
    Returns refund initiation details.
    """
    try:
        user_id = current_user["user_id"]
        response = await payment_service.initiate_refund(request, user_id)
        return response
    except PaymentGatewayError as e:
        if e.error_code == "TRANSACTION_NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "success": False,
                    "error_code": e.error_code,
                    "message": str(e)
                }
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "error_code": e.error_code,
                "message": str(e)
            }
        )


@router.post(
    "/exchange-rate",
    response_model=ExchangeRateResponse,
    summary="Get exchange rate",
    description="Get the current exchange rate for a currency pair"
)
async def get_exchange_rate(
    request: ExchangeRateRequest,
    payment_service: PaymentService = Depends(get_payment_service)
) -> ExchangeRateResponse:
    """
    Get exchange rate for a currency pair.
    
    - **source_currency**: Source currency code
    - **destination_currency**: Destination currency code
    - **amount**: Amount to convert (optional)
    - **gateway**: Specific gateway to use (optional, defaults to best rate)
    
    Returns exchange rate and converted amount (if amount provided).
    """
    try:
        response = await payment_service.get_exchange_rate(request)
        return response
    except PaymentGatewayError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "error_code": e.error_code,
                "message": str(e)
            }
        )


@router.post(
    "/calculate-fee",
    response_model=FeeCalculationResponse,
    summary="Calculate transaction fee",
    description="Calculate the fee for a transaction"
)
async def calculate_fee(
    request: FeeCalculationRequest,
    payment_service: PaymentService = Depends(get_payment_service)
) -> FeeCalculationResponse:
    """
    Calculate transaction fee.
    
    - **amount**: Transaction amount
    - **currency**: Currency code
    - **gateway**: Specific gateway to use (optional)
    
    Returns calculated fee and total amount.
    """
    try:
        response = await payment_service.calculate_fee(request)
        return response
    except PaymentGatewayError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "error_code": e.error_code,
                "message": str(e)
            }
        )


@router.post(
    "/validate-account",
    response_model=AccountValidationResponse,
    summary="Validate account",
    description="Validate an account number with a payment gateway"
)
async def validate_account(
    request: AccountValidationRequest,
    payment_service: PaymentService = Depends(get_payment_service)
) -> AccountValidationResponse:
    """
    Validate an account.
    
    - **account_number**: Account number to validate
    - **bank_code**: Bank code (if applicable)
    - **gateway**: Gateway to use for validation
    
    Returns validation result and account details (if available).
    """
    try:
        response = await payment_service.validate_account(request)
        return response
    except PaymentGatewayError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "error_code": e.error_code,
                "message": str(e)
            }
        )


@router.get(
    "/gateways/currencies",
    response_model=Dict[str, List[str]],
    summary="Get supported currencies",
    description="Get list of supported currencies for all active gateways"
)
async def get_supported_currencies(
    payment_service: PaymentService = Depends(get_payment_service)
) -> Dict[str, List[str]]:
    """
    Get supported currencies for all active gateways.
    
    Returns dictionary mapping gateway names to currency lists.
    """
    try:
        currencies = await payment_service.gateway_factory.get_supported_currencies_all()
        return currencies
    except Exception as e:
        logger.error(f"Failed to get supported currencies: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error_code": "INTERNAL_ERROR",
                "message": "Failed to retrieve supported currencies"
            }
        )


@router.get(
    "/gateways/health",
    response_model=Dict[str, bool],
    summary="Check gateway health",
    description="Check health status of all active payment gateways"
)
async def check_gateways_health(
    payment_service: PaymentService = Depends(get_payment_service)
) -> Dict[str, bool]:
    """
    Check health of all active gateways.
    
    Returns dictionary mapping gateway names to health status (True/False).
    """
    try:
        health_status = await payment_service.gateway_factory.check_all_gateways_health()
        return health_status
    except Exception as e:
        logger.error(f"Failed to check gateway health: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error_code": "INTERNAL_ERROR",
                "message": "Failed to check gateway health"
            }
        )
