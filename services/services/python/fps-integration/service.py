import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from models import FPSTransaction, FPSWebhookLog
from schemas import FPSTransactionCreate, FPSTransactionUpdate, FPSWebhookIn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Custom Exceptions ---

class ServiceException(HTTPException):
    """Base exception for service-layer errors."""
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(status_code=status_code, detail=detail)

class TransactionNotFoundException(ServiceException):
    """Raised when a transaction is not found."""
    def __init__(self, transaction_id: Optional[int] = None, transaction_ref: Optional[str] = None) -> None:
        detail = f"Transaction not found."
        if transaction_id:
            detail = f"Transaction with ID {transaction_id} not found."
        elif transaction_ref:
            detail = f"Transaction with reference {transaction_ref} not found."
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)

class TransactionAlreadyExistsException(ServiceException):
    """Raised when a transaction with the same unique reference already exists."""
    def __init__(self, transaction_ref: str) -> None:
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Transaction with reference '{transaction_ref}' already exists."
        )

class FPSService:
    """
    Business logic layer for the FPS Integration service.
    Handles CRUD operations for transactions and webhook processing.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def create_transaction(self, transaction_data: FPSTransactionCreate) -> FPSTransaction:
        """Creates a new FPS transaction in the database."""
        logger.info(f"Attempting to create new transaction: {transaction_data.transaction_ref}")
        
        # Check for existing transaction with the same reference
        if self.get_transaction_by_ref(transaction_data.transaction_ref):
            raise TransactionAlreadyExistsException(transaction_data.transaction_ref)

        db_transaction = FPSTransaction(**transaction_data.model_dump())
        
        try:
            self.db.add(db_transaction)
            self.db.commit()
            self.db.refresh(db_transaction)
            logger.info(f"Successfully created transaction ID: {db_transaction.id}")
            return db_transaction
        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Integrity error during transaction creation: {e}")
            raise ServiceException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database integrity error during creation."
            )
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error during transaction creation: {e}")
            raise ServiceException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred during transaction creation."
            )

    def get_transaction(self, transaction_id: int) -> FPSTransaction:
        """Retrieves a transaction by its primary key ID."""
        transaction = self.db.query(FPSTransaction).filter(FPSTransaction.id == transaction_id).first()
        if not transaction:
            raise TransactionNotFoundException(transaction_id=transaction_id)
        return transaction

    def get_transaction_by_ref(self, transaction_ref: str) -> Optional[FPSTransaction]:
        """Retrieves a transaction by its unique reference."""
        return self.db.query(FPSTransaction).filter(FPSTransaction.transaction_ref == transaction_ref).first()

    def list_transactions(self, skip: int = 0, limit: int = 100) -> List[FPSTransaction]:
        """Lists all transactions with pagination."""
        return self.db.query(FPSTransaction).offset(skip).limit(limit).all()

    def update_transaction(self, transaction_id: int, update_data: FPSTransactionUpdate) -> FPSTransaction:
        """Updates an existing transaction."""
        db_transaction = self.get_transaction(transaction_id)
        
        update_data_dict = update_data.model_dump(exclude_unset=True)
        
        for key, value in update_data_dict.items():
            setattr(db_transaction, key, value)
        
        try:
            self.db.commit()
            self.db.refresh(db_transaction)
            logger.info(f"Successfully updated transaction ID: {db_transaction.id}")
            return db_transaction
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating transaction ID {transaction_id}: {e}")
            raise ServiceException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred during transaction update."
            )

    def delete_transaction(self, transaction_id: int) -> None:
        """Deletes a transaction by its ID."""
        db_transaction = self.get_transaction(transaction_id)
        
        try:
            self.db.delete(db_transaction)
            self.db.commit()
            logger.info(f"Successfully deleted transaction ID: {transaction_id}")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error deleting transaction ID {transaction_id}: {e}")
            raise ServiceException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred during transaction deletion."
            )

    def handle_webhook(self, webhook_data: FPSWebhookIn) -> Dict[str, Any]:
        """
        Processes an incoming webhook from the FPS provider.
        This is a critical function that updates transaction status based on external events.
        """
        transaction_ref = webhook_data.transaction_ref
        logger.info(f"Received webhook for transaction ref: {transaction_ref}, event: {webhook_data.event_type}")

        db_transaction = self.get_transaction_by_ref(transaction_ref)
        
        # Log the webhook regardless of whether a transaction is found
        # This is crucial for auditing and debugging
        transaction_id = db_transaction.id if db_transaction else None
        db_webhook_log = FPSWebhookLog(
            transaction_id=transaction_id,
            event_type=webhook_data.event_type,
            payload=str(webhook_data.payload) # Store payload as string/text
        )
        
        try:
            self.db.add(db_webhook_log)
            self.db.commit()
            self.db.refresh(db_webhook_log)
            logger.info(f"Webhook log created with ID: {db_webhook_log.id}")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to log webhook: {e}")
            # Continue processing even if logging fails, but raise a server error
            raise ServiceException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to log incoming webhook."
            )

        if not db_transaction:
            logger.warning(f"Webhook received for unknown transaction ref: {transaction_ref}. Logged but no transaction updated.")
            # Return a 200 OK to the webhook sender to prevent retries, but log the issue
            return {"message": "Webhook logged, but no matching transaction found."}

        # --- Business Logic for Status Update ---
        new_status = db_transaction.status
        status_detail = f"Webhook event: {webhook_data.event_type}"

        if webhook_data.event_type == "PAYMENT_SUCCESS":
            new_status = "COMPLETED"
            # Assuming the payload contains the FPS provider's ID
            fps_id = webhook_data.payload.get("fps_payment_id") if isinstance(webhook_data.payload, dict) else None
            if fps_id:
                db_transaction.fps_payment_id = fps_id
                status_detail += f", FPS ID: {fps_id}"
        elif webhook_data.event_type == "PAYMENT_FAILED":
            new_status = "FAILED"
            status_detail += f", Reason: {webhook_data.payload.get('reason', 'Unknown')}"
        elif webhook_data.event_type == "PAYMENT_PROCESSING":
            new_status = "PROCESSING"
        
        # Only update if the status has changed or if it's a success/failure event
        if new_status != db_transaction.status or new_status in ["COMPLETED", "FAILED"]:
            db_transaction.status = new_status
            db_transaction.status_detail = status_detail
            
            try:
                self.db.commit()
                self.db.refresh(db_transaction)
                logger.info(f"Transaction {db_transaction.id} status updated to {new_status}")
            except Exception as e:
                self.db.rollback()
                logger.error(f"Failed to update transaction status for ID {db_transaction.id}: {e}")
                raise ServiceException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to update transaction status after webhook."
                )

        return {"message": f"Transaction {db_transaction.id} processed. Status: {db_transaction.status}"}
