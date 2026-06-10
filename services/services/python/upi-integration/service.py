import logging
import random
from typing import List, Optional, Any
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from models import Transaction, Refund, WebhookEvent, TransactionStatus, RefundStatus
import schemas
from config import settings

# --- Logging Setup ---
logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL)

# --- Custom Exceptions ---

class NotFoundException(Exception):
    """Raised when a resource is not found."""
    def __init__(self, detail: str) -> None:
        self.detail = detail

class ConflictException(Exception):
    """Raised when a resource already exists or a conflict occurs."""
    def __init__(self, detail: str) -> None:
        self.detail = detail

class PaymentGatewayException(Exception):
    """Raised when an external Payment Gateway API call fails."""
    def __init__(self, detail: str, status_code: int = 500) -> None:
        self.detail = detail
        self.status_code = status_code

# --- Mock Payment Gateway Interaction ---

def mock_pg_initiate_payment(transaction_data: schemas.TransactionCreate) -> dict:
    """Simulates initiating a payment with an external Payment Gateway."""
    logger.info(f"Mock PG: Initiating payment for order_id: {transaction_data.order_id}")
    
    if random.random() < settings.PG_MOCK_SUCCESS_RATE:
        # Simulate successful initiation
        pg_transaction_id = f"PG_{random.randint(1000000, 9999999)}"
        return {
            "status": "SUCCESS",
            "pg_transaction_id": pg_transaction_id,
            "message": "Payment link generated successfully (Mock)"
        }
    else:
        # Simulate failed initiation
        raise PaymentGatewayException(
            detail="Mock PG: Failed to initiate payment due to external error.",
            status_code=503
        )

def mock_pg_initiate_refund(transaction: Transaction, refund_amount: Decimal) -> dict:
    """Simulates initiating a refund with an external Payment Gateway."""
    logger.info(f"Mock PG: Initiating refund for transaction_id: {transaction.transaction_id} with amount: {refund_amount}")

    if transaction.status != TransactionStatus.SUCCESS and transaction.status != TransactionStatus.REFUNDED:
        raise ConflictException(f"Cannot refund transaction in status: {transaction.status.value}")

    if random.random() < settings.PG_MOCK_REFUND_SUCCESS_RATE:
        # Simulate successful refund initiation
        pg_refund_id = f"R_PG_{random.randint(1000000, 9999999)}"
        return {
            "status": "SUCCESS",
            "pg_refund_id": pg_refund_id,
            "message": "Refund initiated successfully (Mock)"
        }
    else:
        # Simulate failed refund initiation
        raise PaymentGatewayException(
            detail="Mock PG: Failed to initiate refund due to external error.",
            status_code=503
        )

# --- Business Logic Service ---

class UPIService:
    """
    Service layer for UPI Integration business logic.
    Handles database operations, transaction management, and external PG interaction.
    """

    def create_transaction(self, db: Session, transaction_data: schemas.TransactionCreate) -> Transaction:
        """Initiates a new UPI transaction and saves it to the database."""
        logger.info(f"Attempting to create transaction for order_id: {transaction_data.order_id}")
        
        # 1. Check for existing transaction with the same order_id
        if db.query(Transaction).filter(Transaction.order_id == transaction_data.order_id).first():
            raise ConflictException(f"Transaction with order_id '{transaction_data.order_id}' already exists.")

        # 2. Mock PG interaction (In a real app, this would call the PG API)
        try:
            pg_response = mock_pg_initiate_payment(transaction_data)
            
            # 3. Create the database object
            db_transaction = Transaction(
                **transaction_data.model_dump(),
                transaction_id=pg_response.get("pg_transaction_id"),
                status=TransactionStatus.PENDING, # Status is PENDING until webhook confirms payment
                gateway_response=pg_response
            )
            
            db.add(db_transaction)
            db.commit()
            db.refresh(db_transaction)
            logger.info(f"Transaction created successfully with ID: {db_transaction.id}")
            return db_transaction
        
        except IntegrityError as e:
            db.rollback()
            logger.error(f"Database integrity error during transaction creation: {e}")
            raise ConflictException("A transaction with this unique identifier already exists.")
        except PaymentGatewayException as e:
            db.rollback()
            logger.error(f"PG error during transaction creation: {e.detail}")
            raise e
        except Exception as e:
            db.rollback()
            logger.error(f"Unexpected error during transaction creation: {e}")
            raise Exception("An unexpected error occurred during transaction creation.")

    def get_transaction(self, db: Session, transaction_id: int) -> Transaction:
        """Retrieves a transaction by its primary key ID."""
        transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
        if not transaction:
            raise NotFoundException(f"Transaction with ID {transaction_id} not found.")
        return transaction

    def get_transaction_by_order_id(self, db: Session, order_id: str) -> Transaction:
        """Retrieves a transaction by its unique order_id."""
        transaction = db.query(Transaction).filter(Transaction.order_id == order_id).first()
        if not transaction:
            raise NotFoundException(f"Transaction with order_id {order_id} not found.")
        return transaction

    def list_transactions(self, db: Session, skip: int = 0, limit: int = 100) -> List[Transaction]:
        """Retrieves a list of transactions with pagination."""
        return db.query(Transaction).offset(skip).limit(limit).all()

    def count_transactions(self, db: Session) -> int:
        """Counts the total number of transactions."""
        return db.query(Transaction).count()

    def update_transaction_status(self, db: Session, order_id: str, update_data: schemas.TransactionUpdate) -> Transaction:
        """Updates the status of a transaction, typically via a webhook."""
        db_transaction = self.get_transaction_by_order_id(db, order_id)
        
        logger.info(f"Updating transaction {order_id} status from {db_transaction.status.value} to {update_data.status.value}")

        # Update fields
        db_transaction.status = update_data.status
        if update_data.transaction_id:
            db_transaction.transaction_id = update_data.transaction_id
        if update_data.gateway_response:
            db_transaction.gateway_response = update_data.gateway_response

        db.commit()
        db.refresh(db_transaction)
        return db_transaction

    def create_refund(self, db: Session, refund_data: schemas.RefundCreate) -> Refund:
        """Initiates a refund for a successful transaction."""
        db_transaction = self.get_transaction(db, refund_data.transaction_id)

        # 1. Check if transaction is eligible for refund
        if db_transaction.status != TransactionStatus.SUCCESS:
            raise ConflictException(f"Transaction is not successful and cannot be refunded. Current status: {db_transaction.status.value}")
        
        # 2. Check if total refunded amount exceeds transaction amount
        total_refunded = sum(r.amount for r in db_transaction.refunds)
        if total_refunded + refund_data.amount > db_transaction.amount:
            raise ConflictException(f"Refund amount {refund_data.amount} exceeds remaining refundable amount of {db_transaction.amount - total_refunded}.")

        # 3. Mock PG interaction
        try:
            pg_response = mock_pg_initiate_refund(db_transaction, refund_data.amount)
            
            # 4. Create the database object
            db_refund = Refund(
                transaction_id=refund_data.transaction_id,
                amount=refund_data.amount,
                refund_id=pg_response.get("pg_refund_id"),
                status=RefundStatus.PENDING, # Status is PENDING until webhook confirms refund
                gateway_response=pg_response
            )
            
            db.add(db_refund)
            
            # 5. Update transaction status if it's a full refund
            if total_refunded + refund_data.amount == db_transaction.amount:
                db_transaction.status = TransactionStatus.REFUNDED
            
            db.commit()
            db.refresh(db_refund)
            logger.info(f"Refund created successfully with ID: {db_refund.id}")
            return db_refund
        
        except PaymentGatewayException as e:
            db.rollback()
            logger.error(f"PG error during refund creation: {e.detail}")
            raise e
        except Exception as e:
            db.rollback()
            logger.error(f"Unexpected error during refund creation: {e}")
            raise Exception("An unexpected error occurred during refund creation.")

    def get_refund(self, db: Session, refund_id: int) -> Refund:
        """Retrieves a refund by its primary key ID."""
        refund = db.query(Refund).filter(Refund.id == refund_id).first()
        if not refund:
            raise NotFoundException(f"Refund with ID {refund_id} not found.")
        return refund

    def list_refunds_by_transaction(self, db: Session, transaction_id: int) -> List[Refund]:
        """Retrieves a list of refunds for a specific transaction."""
        return db.query(Refund).filter(Refund.transaction_id == transaction_id).all()

    def process_webhook_event(self, db: Session, event_data: schemas.WebhookEventCreate) -> WebhookEvent:
        """Stores and processes an incoming webhook event."""
        logger.info(f"Processing webhook event_id: {event_data.event_id}, type: {event_data.event_type}")

        # 1. Check for duplicate event
        if db.query(WebhookEvent).filter(WebhookEvent.event_id == event_data.event_id).first():
            raise ConflictException(f"Webhook event with ID {event_data.event_id} already processed.")

        # 2. Store the event
        db_event = WebhookEvent(**event_data.model_dump())
        db.add(db_event)
        
        # 3. Process the event (Simplified logic)
        try:
            # Extract relevant info from payload (e.g., order_id, status)
            payload = event_data.payload
            order_id = payload.get("order_id")
            new_status = payload.get("status")
            pg_transaction_id = payload.get("transaction_id")
            
            if order_id and new_status:
                # Attempt to update the transaction status
                update_schema = schemas.TransactionUpdate(
                    status=TransactionStatus(new_status.upper()),
                    transaction_id=pg_transaction_id,
                    gateway_response=payload
                )
                self.update_transaction_status(db, order_id, update_schema)
                db_event.processed = True
                logger.info(f"Webhook processed: Transaction {order_id} status updated to {new_status}")
            
            # Add logic for refund webhooks here if needed
            
            db.commit()
            db.refresh(db_event)
            return db_event

        except NotFoundException:
            db.rollback()
            logger.warning(f"Webhook event received for unknown order_id: {order_id}")
            db_event.processed = False # Still store the event, but mark as not fully processed
            db.commit()
            db.refresh(db_event)
            return db_event
        except Exception as e:
            db.rollback()
            logger.error(f"Error processing webhook event {event_data.event_id}: {e}")
            raise Exception("An unexpected error occurred during webhook processing.")

# Instantiate the service
upi_service = UPIService()