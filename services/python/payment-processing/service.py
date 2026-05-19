import uuid
import logging
from typing import List, Optional
from decimal import Decimal
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.exc import IntegrityError

from models import Merchant, PaymentMethod, Transaction, Refund, TransactionStatus, PaymentMethodType
from schemas import (
    MerchantCreate, MerchantUpdate, PaymentMethodCreate, TransactionCreate, RefundCreate,
    TransactionFilter
)
from config import settings

# --- Setup Logging ---
logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL)

# --- Custom Exceptions ---

class ServiceException(Exception):
    """Base exception for service layer errors."""
    def __init__(self, message: str, status_code: int = 500) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)

class NotFoundException(ServiceException):
    """Raised when a requested resource is not found."""
    def __init__(self, resource_name: str, resource_id: uuid.UUID) -> None:
        message = f"{resource_name} with ID {resource_id} not found."
        super().__init__(message, status_code=404)

class ConflictException(ServiceException):
    """Raised when a resource creation conflicts with an existing resource."""
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=409)

class InvalidOperationException(ServiceException):
    """Raised when a business logic rule is violated."""
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=400)

class PSPException(ServiceException):
    """Raised for errors from the external Payment Service Provider."""
    def __init__(self, message: str) -> None:
        super().__init__(f"PSP Error: {message}", status_code=503)

# --- Simulated External PSP Client ---

class SimulatedPSPClient:
    """
    A simulated client for an external Payment Service Provider (PSP).
    In a real application, this would handle HTTP requests to Stripe, PayPal, etc.
    """
    def __init__(self) -> None:
        logger.info(f"Simulated PSP Client initialized for {settings.PSP_BASE_URL}")

    async def process_payment(self, token: str, amount: Decimal, currency: str) -> dict:
        """Simulates processing a payment."""
        logger.info(f"Simulating payment for {amount} {currency} using token {token[:4]}...")
        
        # Simple simulation logic
        if amount > Decimal("10000.00"):
            raise PSPException("Transaction amount exceeds limit.")
        if token.endswith("FAIL"):
            raise PSPException("Simulated token failure.")
        
        # Simulate success
        return {
            "status": "SUCCESS",
            "processor_transaction_id": f"txn_{uuid.uuid4().hex[:12]}",
            "fee_rate": Decimal("0.029") + Decimal("0.30") / amount if amount > 0 else Decimal("0.00"),
            "fee": amount * Decimal("0.029") + Decimal("0.30") # 2.9% + 30 cents
        }

    async def process_refund(self, processor_transaction_id: str, amount: Decimal) -> dict:
        """Simulates processing a refund."""
        logger.info(f"Simulating refund of {amount} for transaction {processor_transaction_id}...")
        
        # Simple simulation logic
        if processor_transaction_id.endswith("FAIL"):
            raise PSPException("Simulated refund failure.")
            
        # Simulate success
        return {
            "status": "SUCCESS",
            "processor_refund_id": f"ref_{uuid.uuid4().hex[:12]}",
        }

# --- Service Layer ---

class PaymentService:
    """
    Business logic layer for the payment processing service.
    Handles database interactions and external PSP communication.
    """
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.psp_client = SimulatedPSPClient()
        # In a real app, use a proper hashing library like passlib
        self.hash_func = lambda x: f"HASHED_{x}" 

    # --- Merchant Operations ---

    async def create_merchant(self, merchant_in: MerchantCreate) -> Merchant:
        """Creates a new merchant and generates a simulated API key."""
        try:
            # Simulate API key generation and hashing
            simulated_api_key = f"sk_live_{uuid.uuid4().hex}"
            api_key_hash = self.hash_func(simulated_api_key)
            
            new_merchant = Merchant(
                name=merchant_in.name,
                api_key_hash=api_key_hash,
                is_active=merchant_in.is_active
            )
            self.db.add(new_merchant)
            await self.db.commit()
            await self.db.refresh(new_merchant)
            logger.info(f"Merchant created: {new_merchant.id}")
            
            # NOTE: In a real system, the unhashed API key would be returned here 
            # and only here, as it cannot be retrieved later.
            # For this exercise, we'll just return the merchant object.
            return new_merchant
        except IntegrityError as e:
            await self.db.rollback()
            logger.error(f"Integrity error creating merchant: {e}")
            raise ConflictException(f"Merchant with name '{merchant_in.name}' already exists.")
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Unexpected error creating merchant: {e}")
            raise ServiceException(f"Failed to create merchant: {e}")

    async def get_merchant(self, merchant_id: uuid.UUID) -> Merchant:
        """Retrieves a merchant by ID."""
        stmt = select(Merchant).where(Merchant.id == merchant_id)
        result = await self.db.execute(stmt)
        merchant = result.scalar_one_or_none()
        if not merchant:
            raise NotFoundException("Merchant", merchant_id)
        return merchant

    async def update_merchant(self, merchant_id: uuid.UUID, merchant_in: MerchantUpdate) -> Merchant:
        """Updates an existing merchant."""
        merchant = await self.get_merchant(merchant_id)
        
        update_data = merchant_in.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(merchant, key, value)
        
        await self.db.commit()
        await self.db.refresh(merchant)
        logger.info(f"Merchant updated: {merchant_id}")
        return merchant

    async def delete_merchant(self, merchant_id: uuid.UUID) -> None:
        """Deletes a merchant."""
        merchant = await self.get_merchant(merchant_id)
        await self.db.delete(merchant)
        await self.db.commit()
        logger.info(f"Merchant deleted: {merchant_id}")

    # --- Payment Method Operations ---

    async def create_payment_method(self, pm_in: PaymentMethodCreate) -> PaymentMethod:
        """Creates a new tokenized payment method."""
        try:
            new_pm = PaymentMethod(
                user_id=pm_in.user_id,
                type=pm_in.type.value,
                last_four=pm_in.last_four,
                token=pm_in.token,
                is_default=pm_in.is_default
            )
            self.db.add(new_pm)
            await self.db.commit()
            await self.db.refresh(new_pm)
            logger.info(f"Payment Method created: {new_pm.id}")
            return new_pm
        except IntegrityError as e:
            await self.db.rollback()
            logger.error(f"Integrity error creating payment method: {e}")
            raise ConflictException("Payment method token already exists.")
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Unexpected error creating payment method: {e}")
            raise ServiceException(f"Failed to create payment method: {e}")

    async def get_payment_method(self, pm_id: uuid.UUID) -> PaymentMethod:
        """Retrieves a payment method by ID."""
        stmt = select(PaymentMethod).where(PaymentMethod.id == pm_id)
        result = await self.db.execute(stmt)
        pm = result.scalar_one_or_none()
        if not pm:
            raise NotFoundException("PaymentMethod", pm_id)
        return pm

    # --- Transaction Operations ---

    async def create_transaction(self, transaction_in: TransactionCreate) -> Transaction:
        """
        Processes a payment through the external PSP and records the transaction.
        This operation is atomic (transactional).
        """
        merchant = await self.get_merchant(transaction_in.merchant_id)
        if not merchant.is_active:
            raise InvalidOperationException("Merchant is not active and cannot process transactions.")

        payment_method = await self.get_payment_method(transaction_in.payment_method_id)
        
        # 1. Simulate PSP interaction
        try:
            psp_result = await self.psp_client.process_payment(
                token=payment_method.token,
                amount=transaction_in.amount,
                currency=transaction_in.currency
            )
        except PSPException as e:
            # Record a failed transaction before raising the error
            failed_txn = Transaction(
                merchant_id=transaction_in.merchant_id,
                payment_method_id=transaction_in.payment_method_id,
                amount=transaction_in.amount,
                currency=transaction_in.currency,
                status=TransactionStatus.FAILED.value,
                fee=Decimal("0.00"),
                net_amount=transaction_in.amount, # No fee on failed txn
                processor_transaction_id=None
            )
            self.db.add(failed_txn)
            await self.db.commit()
            await self.db.refresh(failed_txn)
            logger.warning(f"Transaction failed at PSP level: {e.message}. Recorded as FAILED: {failed_txn.id}")
            raise InvalidOperationException(f"Payment failed: {e.message}")
        
        # 2. Calculate fees and net amount
        fee = psp_result.get("fee", Decimal("0.00"))
        net_amount = transaction_in.amount - fee
        
        # 3. Record successful transaction in the database (atomic)
        try:
            new_transaction = Transaction(
                merchant_id=transaction_in.merchant_id,
                payment_method_id=transaction_in.payment_method_id,
                amount=transaction_in.amount,
                currency=transaction_in.currency,
                status=TransactionStatus.SUCCESS.value,
                processor_transaction_id=psp_result["processor_transaction_id"],
                fee=fee,
                net_amount=net_amount
            )
            self.db.add(new_transaction)
            await self.db.commit()
            await self.db.refresh(new_transaction)
            logger.info(f"Transaction successful: {new_transaction.id}")
            return new_transaction
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Database error after successful PSP call. Manual reconciliation needed: {e}")
            # CRITICAL: In a real system, this would trigger an alert for manual reconciliation
            raise ServiceException("Payment processed but failed to record in database. System alert triggered.")

    async def get_transaction(self, transaction_id: uuid.UUID) -> Transaction:
        """Retrieves a transaction by ID."""
        stmt = select(Transaction).where(Transaction.id == transaction_id)
        result = await self.db.execute(stmt)
        transaction = result.scalar_one_or_none()
        if not transaction:
            raise NotFoundException("Transaction", transaction_id)
        return transaction

    async def list_transactions(self, filters: TransactionFilter, skip: int = 0, limit: int = 100) -> List[Transaction]:
        """Lists transactions with optional filtering."""
        stmt = select(Transaction)
        
        # Apply filters
        conditions = []
        if filters.merchant_id:
            conditions.append(Transaction.merchant_id == filters.merchant_id)
        if filters.status:
            conditions.append(Transaction.status == filters.status.value)
        if filters.start_date:
            conditions.append(Transaction.created_at >= filters.start_date)
        if filters.end_date:
            conditions.append(Transaction.created_at <= filters.end_date)
            
        if conditions:
            stmt = stmt.where(or_(*conditions))
            
        # Apply pagination and ordering
        stmt = stmt.order_by(Transaction.created_at.desc()).offset(skip).limit(limit)
        
        result = await self.db.execute(stmt)
        return result.scalars().all()

    # --- Refund Operations ---

    async def create_refund(self, refund_in: RefundCreate) -> Refund:
        """
        Processes a refund through the external PSP and records the refund.
        This operation is atomic (transactional).
        """
        original_txn = await self.get_transaction(refund_in.transaction_id)

        if original_txn.status != TransactionStatus.SUCCESS.value:
            raise InvalidOperationException(f"Cannot refund a transaction with status: {original_txn.status}")
        
        # Calculate already refunded amount
        refunded_amount_stmt = select(func.sum(Refund.amount)).where(
            Refund.transaction_id == original_txn.id,
            Refund.status == TransactionStatus.SUCCESS.value
        )
        already_refunded = (await self.db.execute(refunded_amount_stmt)).scalar() or Decimal("0.00")
        
        if already_refunded + refund_in.amount > original_txn.amount:
            raise InvalidOperationException(
                f"Refund amount {refund_in.amount} exceeds remaining refundable amount "
                f"({original_txn.amount - already_refunded})."
            )

        # 1. Simulate PSP interaction
        try:
            psp_result = await self.psp_client.process_refund(
                processor_transaction_id=original_txn.processor_transaction_id,
                amount=refund_in.amount
            )
        except PSPException as e:
            # Record a failed refund before raising the error
            failed_refund = Refund(
                transaction_id=original_txn.id,
                amount=refund_in.amount,
                status=TransactionStatus.FAILED.value,
                processor_refund_id=None
            )
            self.db.add(failed_refund)
            await self.db.commit()
            await self.db.refresh(failed_refund)
            logger.warning(f"Refund failed at PSP level: {e.message}. Recorded as FAILED: {failed_refund.id}")
            raise InvalidOperationException(f"Refund failed: {e.message}")

        # 2. Record successful refund and update original transaction status
        try:
            new_refund = Refund(
                transaction_id=original_txn.id,
                amount=refund_in.amount,
                status=TransactionStatus.SUCCESS.value,
                processor_refund_id=psp_result["processor_refund_id"]
            )
            self.db.add(new_refund)
            
            # Update original transaction status if fully refunded
            total_refunded = already_refunded + refund_in.amount
            if total_refunded == original_txn.amount:
                original_txn.status = TransactionStatus.REFUNDED.value
            
            await self.db.commit()
            await self.db.refresh(new_refund)
            logger.info(f"Refund successful: {new_refund.id}")
            return new_refund
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Database error after successful PSP refund call. Manual reconciliation needed: {e}")
            # CRITICAL: In a real system, this would trigger an alert for manual reconciliation
            raise ServiceException("Refund processed but failed to record in database. System alert triggered.")

    async def get_refund(self, refund_id: uuid.UUID) -> Refund:
        """Retrieves a refund by ID."""
        stmt = select(Refund).where(Refund.id == refund_id)
        result = await self.db.execute(stmt)
        refund = result.scalar_one_or_none()
        if not refund:
            raise NotFoundException("Refund", refund_id)
        return refund
