"""
Payment Service Layer

Business logic for payment processing, transaction management,
and gateway orchestration.
"""

from typing import Optional, List, Dict, Any
from decimal import Decimal
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
import logging
import uuid

from ..models.payment_models import (
    PaymentTransaction,
    PaymentRefund,
    PaymentWebhook,
    PaymentGatewayBalance,
    TransactionStatus,
    TransactionType
)
from ..schemas.payment_schemas import (
    PaymentInitiateRequest,
    PaymentInitiateResponse,
    PaymentVerifyResponse,
    RefundInitiateRequest,
    RefundInitiateResponse,
    ExchangeRateRequest,
    ExchangeRateResponse,
    FeeCalculationRequest,
    FeeCalculationResponse,
    AccountValidationRequest,
    AccountValidationResponse,
    PaymentStatusEnum
)
from .gateway_factory import GatewayFactory
from .base_gateway import PaymentGatewayError, PaymentRequest, RefundRequest

logger = logging.getLogger(__name__)


class PaymentService:
    """
    Service layer for payment operations.
    
    Handles business logic for:
    - Payment initiation and processing
    - Transaction verification
    - Refunds
    - Exchange rates
    - Fee calculations
    - Account validation
    """
    
    def __init__(self, db: Session, gateway_factory: GatewayFactory) -> None:
        """
        Initialize payment service.
        
        Args:
            db: Database session
            gateway_factory: Gateway factory instance
        """
        self.db = db
        self.gateway_factory = gateway_factory
    
    async def initiate_payment(
        self,
        request: PaymentInitiateRequest,
        user_id: str
    ) -> PaymentInitiateResponse:
        """
        Initiate a new payment transaction.
        
        Args:
            request: Payment initiation request
            user_id: ID of the user initiating payment
            
        Returns:
            Payment initiation response
            
        Raises:
            PaymentGatewayError: If payment initiation fails
        """
        try:
            # Select gateway
            if request.gateway == "auto":
                gateway = await self.gateway_factory.select_gateway(
                    currency=request.currency,
                    amount=request.amount
                )
                gateway_name = gateway.gateway_name.lower()
            else:
                gateway_name = request.gateway.value
                gateway = self.gateway_factory.get_gateway(gateway_name)
            
            # Calculate fee
            fee = await gateway.calculate_fee(request.amount, request.currency)
            total_amount = request.amount + fee
            
            # Get exchange rate if needed
            exchange_rate = None
            if request.source_currency != request.destination_currency:
                exchange_rate = await gateway.get_exchange_rate(
                    request.source_currency,
                    request.destination_currency
                )
            
            # Create transaction record
            transaction = PaymentTransaction(
                transaction_id=f"txn_{uuid.uuid4().hex[:16]}",
                user_id=user_id,
                recipient_id=request.recipient_id,
                gateway=gateway_name,
                amount=request.amount,
                currency=request.currency,
                source_currency=request.source_currency,
                destination_currency=request.destination_currency,
                fee=fee,
                total_amount=total_amount,
                exchange_rate=exchange_rate,
                transaction_type=request.transaction_type.value,
                status=TransactionStatus.PENDING,
                description=request.description,
                callback_url=request.callback_url,
                metadata=request.metadata or {}
            )
            
            self.db.add(transaction)
            self.db.flush()  # Get transaction ID
            
            # Initiate payment with gateway
            payment_request = PaymentRequest(
                amount=request.amount,
                currency=request.currency,
                recipient_account=request.recipient_account or "",
                reference=transaction.transaction_id,
                callback_url=request.callback_url,
                metadata=request.metadata or {}
            )
            
            payment_response = await gateway.initiate_payment(payment_request)
            
            # Update transaction with gateway response
            transaction.gateway_reference = payment_response.reference
            transaction.gateway_response = payment_response.metadata
            transaction.payment_url = payment_response.payment_url
            
            if payment_response.success:
                transaction.status = TransactionStatus.PROCESSING
            else:
                transaction.status = TransactionStatus.FAILED
                transaction.failure_reason = payment_response.message
            
            self.db.commit()
            
            logger.info(
                f"Payment initiated: {transaction.transaction_id} "
                f"via {gateway_name}"
            )
            
            return PaymentInitiateResponse(
                success=payment_response.success,
                transaction_id=transaction.transaction_id,
                gateway_reference=payment_response.reference,
                gateway=gateway_name,
                status=PaymentStatusEnum(transaction.status.value),
                amount=request.amount,
                currency=request.currency,
                fee=fee,
                total_amount=total_amount,
                exchange_rate=exchange_rate,
                payment_url=payment_response.payment_url,
                message=payment_response.message,
                metadata=payment_response.metadata,
                created_at=transaction.created_at
            )
            
        except PaymentGatewayError as e:
            self.db.rollback()
            logger.error(f"Payment initiation failed: {e}")
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error in payment initiation: {e}")
            raise PaymentGatewayError(
                f"Payment initiation failed: {str(e)}",
                gateway_name=gateway_name if 'gateway_name' in locals() else "unknown",
                error_code="PAYMENT_INITIATION_FAILED"
            )
    
    async def verify_payment(self, transaction_id: str) -> PaymentVerifyResponse:
        """
        Verify payment status.
        
        Args:
            transaction_id: Transaction ID to verify
            
        Returns:
            Payment verification response
            
        Raises:
            PaymentGatewayError: If verification fails
        """
        try:
            # Get transaction from database
            transaction = self.db.query(PaymentTransaction).filter(
                PaymentTransaction.transaction_id == transaction_id
            ).first()
            
            if not transaction:
                raise PaymentGatewayError(
                    f"Transaction not found: {transaction_id}",
                    gateway_name="unknown",
                    error_code="TRANSACTION_NOT_FOUND"
                )
            
            # Get gateway
            gateway = self.gateway_factory.get_gateway(transaction.gateway)
            
            # Verify with gateway
            verification_response = await gateway.verify_payment(
                transaction.gateway_reference or transaction.transaction_id
            )
            
            # Update transaction status
            old_status = transaction.status
            transaction.status = TransactionStatus(verification_response.status.value)
            transaction.gateway_response = verification_response.metadata
            
            if verification_response.status == PaymentStatusEnum.SUCCESS:
                transaction.completed_at = datetime.utcnow()
            elif verification_response.status == PaymentStatusEnum.FAILED:
                transaction.failure_reason = verification_response.message
            
            self.db.commit()
            
            logger.info(
                f"Payment verified: {transaction_id}, "
                f"status: {old_status.value} -> {transaction.status.value}"
            )
            
            return PaymentVerifyResponse(
                success=True,
                transaction_id=transaction.transaction_id,
                gateway_reference=transaction.gateway_reference,
                status=PaymentStatusEnum(transaction.status.value),
                amount=transaction.amount,
                currency=transaction.currency,
                fee=transaction.fee,
                exchange_rate=transaction.exchange_rate,
                sender_id=transaction.user_id,
                recipient_id=transaction.recipient_id,
                description=transaction.description,
                initiated_at=transaction.created_at,
                completed_at=transaction.completed_at,
                message=verification_response.message,
                metadata=transaction.metadata
            )
            
        except PaymentGatewayError:
            raise
        except Exception as e:
            logger.error(f"Payment verification failed: {e}")
            raise PaymentGatewayError(
                f"Payment verification failed: {str(e)}",
                gateway_name=transaction.gateway if 'transaction' in locals() else "unknown",
                error_code="VERIFICATION_FAILED"
            )
    
    async def initiate_refund(
        self,
        request: RefundInitiateRequest,
        user_id: str
    ) -> RefundInitiateResponse:
        """
        Initiate a refund for a transaction.
        
        Args:
            request: Refund initiation request
            user_id: ID of the user requesting refund
            
        Returns:
            Refund initiation response
            
        Raises:
            PaymentGatewayError: If refund initiation fails
        """
        try:
            # Get original transaction
            transaction = self.db.query(PaymentTransaction).filter(
                PaymentTransaction.transaction_id == request.transaction_id
            ).first()
            
            if not transaction:
                raise PaymentGatewayError(
                    f"Transaction not found: {request.transaction_id}",
                    gateway_name="unknown",
                    error_code="TRANSACTION_NOT_FOUND"
                )
            
            # Validate refund
            if transaction.status != TransactionStatus.SUCCESS:
                raise PaymentGatewayError(
                    "Can only refund successful transactions",
                    gateway_name=transaction.gateway,
                    error_code="INVALID_REFUND_STATUS"
                )
            
            # Calculate refund amount
            refund_amount = request.amount or transaction.amount
            
            if refund_amount > transaction.amount:
                raise PaymentGatewayError(
                    "Refund amount cannot exceed transaction amount",
                    gateway_name=transaction.gateway,
                    error_code="INVALID_REFUND_AMOUNT"
                )
            
            # Check existing refunds
            existing_refunds = self.db.query(PaymentRefund).filter(
                PaymentRefund.transaction_id == transaction.transaction_id,
                PaymentRefund.status.in_([TransactionStatus.SUCCESS, TransactionStatus.PROCESSING])
            ).all()
            
            total_refunded = sum(r.refund_amount for r in existing_refunds)
            if total_refunded + refund_amount > transaction.amount:
                raise PaymentGatewayError(
                    "Total refund amount exceeds transaction amount",
                    gateway_name=transaction.gateway,
                    error_code="REFUND_LIMIT_EXCEEDED"
                )
            
            # Create refund record
            refund = PaymentRefund(
                refund_id=f"ref_{uuid.uuid4().hex[:16]}",
                transaction_id=transaction.transaction_id,
                user_id=user_id,
                gateway=transaction.gateway,
                refund_amount=refund_amount,
                currency=transaction.currency,
                reason=request.reason,
                status=TransactionStatus.PENDING,
                metadata=request.metadata or {}
            )
            
            self.db.add(refund)
            self.db.flush()
            
            # Initiate refund with gateway
            gateway = self.gateway_factory.get_gateway(transaction.gateway)
            
            refund_request = RefundRequest(
                transaction_reference=transaction.gateway_reference or transaction.transaction_id,
                amount=refund_amount,
                currency=transaction.currency,
                reason=request.reason,
                metadata=request.metadata or {}
            )
            
            refund_response = await gateway.refund_payment(refund_request)
            
            # Update refund record
            refund.gateway_reference = refund_response.refund_reference
            refund.gateway_response = refund_response.metadata
            
            if refund_response.success:
                refund.status = TransactionStatus.PROCESSING
            else:
                refund.status = TransactionStatus.FAILED
                refund.failure_reason = refund_response.message
            
            self.db.commit()
            
            logger.info(
                f"Refund initiated: {refund.refund_id} "
                f"for transaction {transaction.transaction_id}"
            )
            
            return RefundInitiateResponse(
                success=refund_response.success,
                refund_id=refund.refund_id,
                transaction_id=transaction.transaction_id,
                refund_amount=refund_amount,
                currency=transaction.currency,
                status=PaymentStatusEnum(refund.status.value),
                message=refund_response.message,
                requested_at=refund.created_at,
                metadata=refund_response.metadata
            )
            
        except PaymentGatewayError:
            self.db.rollback()
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"Refund initiation failed: {e}")
            raise PaymentGatewayError(
                f"Refund initiation failed: {str(e)}",
                gateway_name=transaction.gateway if 'transaction' in locals() else "unknown",
                error_code="REFUND_INITIATION_FAILED"
            )
    
    async def get_exchange_rate(
        self,
        request: ExchangeRateRequest
    ) -> ExchangeRateResponse:
        """
        Get exchange rate for currency pair.
        
        Args:
            request: Exchange rate request
            
        Returns:
            Exchange rate response
        """
        try:
            if request.gateway:
                # Use specific gateway
                gateway = self.gateway_factory.get_gateway(request.gateway.value)
                gateway_name = request.gateway.value
            else:
                # Get best rate across all gateways
                gateway_name, rate = await self.gateway_factory.get_best_exchange_rate(
                    request.source_currency,
                    request.destination_currency
                )
                gateway = self.gateway_factory.get_gateway(gateway_name)
            
            rate = await gateway.get_exchange_rate(
                request.source_currency,
                request.destination_currency
            )
            
            converted_amount = None
            if request.amount:
                converted_amount = request.amount * rate
            
            return ExchangeRateResponse(
                success=True,
                source_currency=request.source_currency,
                destination_currency=request.destination_currency,
                exchange_rate=rate,
                converted_amount=converted_amount,
                gateway=gateway_name,
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Exchange rate retrieval failed: {e}")
            raise PaymentGatewayError(
                f"Exchange rate retrieval failed: {str(e)}",
                gateway_name=gateway_name if 'gateway_name' in locals() else "unknown",
                error_code="EXCHANGE_RATE_FAILED"
            )
    
    async def calculate_fee(
        self,
        request: FeeCalculationRequest
    ) -> FeeCalculationResponse:
        """
        Calculate transaction fee.
        
        Args:
            request: Fee calculation request
            
        Returns:
            Fee calculation response
        """
        try:
            if request.gateway:
                gateway = self.gateway_factory.get_gateway(request.gateway.value)
                gateway_name = request.gateway.value
            else:
                # Use default gateway for currency
                gateway = await self.gateway_factory.select_gateway(
                    currency=request.currency,
                    amount=request.amount
                )
                gateway_name = gateway.gateway_name.lower()
            
            fee = await gateway.calculate_fee(request.amount, request.currency)
            total_amount = request.amount + fee
            
            return FeeCalculationResponse(
                success=True,
                amount=request.amount,
                currency=request.currency,
                fee=fee,
                total_amount=total_amount,
                gateway=gateway_name
            )
            
        except Exception as e:
            logger.error(f"Fee calculation failed: {e}")
            raise PaymentGatewayError(
                f"Fee calculation failed: {str(e)}",
                gateway_name=gateway_name if 'gateway_name' in locals() else "unknown",
                error_code="FEE_CALCULATION_FAILED"
            )
    
    async def validate_account(
        self,
        request: AccountValidationRequest
    ) -> AccountValidationResponse:
        """
        Validate an account.
        
        Args:
            request: Account validation request
            
        Returns:
            Account validation response
        """
        try:
            gateway = self.gateway_factory.get_gateway(request.gateway.value)
            
            is_valid = await gateway.validate_account(
                request.account_number,
                request.bank_code
            )
            
            # Try to get account name if validation successful
            account_name = None
            bank_name = None
            if is_valid:
                # Some gateways provide account details
                # This would need to be implemented in each gateway
                pass
            
            return AccountValidationResponse(
                success=True,
                account_number=request.account_number,
                account_name=account_name,
                bank_name=bank_name,
                bank_code=request.bank_code,
                is_valid=is_valid,
                message="Account validated successfully" if is_valid else "Invalid account"
            )
            
        except Exception as e:
            logger.error(f"Account validation failed: {e}")
            raise PaymentGatewayError(
                f"Account validation failed: {str(e)}",
                gateway_name=request.gateway.value,
                error_code="ACCOUNT_VALIDATION_FAILED"
            )
    
    def get_transaction(self, transaction_id: str) -> Optional[PaymentTransaction]:
        """Get transaction by ID."""
        return self.db.query(PaymentTransaction).filter(
            PaymentTransaction.transaction_id == transaction_id
        ).first()
    
    def get_user_transactions(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 20
    ) -> List[PaymentTransaction]:
        """Get transactions for a user."""
        return self.db.query(PaymentTransaction).filter(
            PaymentTransaction.user_id == user_id
        ).order_by(PaymentTransaction.created_at.desc()).offset(skip).limit(limit).all()
    
    def get_transaction_count(self, user_id: str) -> int:
        """Get total transaction count for a user."""
        return self.db.query(PaymentTransaction).filter(
            PaymentTransaction.user_id == user_id
        ).count()
