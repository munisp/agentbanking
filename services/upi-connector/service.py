import logging
import uuid
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from models import UPITransaction, TransactionStatus
from schemas import UPITransactionCreate, UPITransactionUpdate

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Custom Exceptions ---

class UPIServiceException(Exception):
    """Base exception for UPI Service errors."""
    def __init__(self, detail: str, status_code: int = 400) -> None:
        self.detail = detail
        self.status_code = status_code

class TransactionNotFound(UPIServiceException):
    """Raised when a transaction is not found."""
    def __init__(self, identifier: str) -> None:
        super().__init__(detail=f"Transaction with identifier '{identifier}' not found.", status_code=404)

class TransactionUpdateError(UPIServiceException):
    """Raised when a transaction update fails due to business logic or database error."""
    def __init__(self, detail: str) -> None:
        super().__init__(detail=detail, status_code=400)

# --- Service Class ---

class UPITransactionService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_transaction(self, transaction_in: UPITransactionCreate) -> UPITransaction:
        """Creates a new UPI transaction record."""
        # Generate a unique external transaction ID
        new_transaction_id = str(uuid.uuid4())
        
        db_transaction = UPITransaction(
            transaction_id=new_transaction_id,
            reference_id=transaction_in.reference_id,
            vpa=transaction_in.vpa,
            amount=transaction_in.amount,
            currency=transaction_in.currency,
            transaction_type=transaction_in.transaction_type,
            status=TransactionStatus.PENDING,
        )
        
        try:
            self.db.add(db_transaction)
            self.db.commit()
            self.db.refresh(db_transaction)
            logger.info(f"Created new transaction: {db_transaction.transaction_id} for reference: {db_transaction.reference_id}")
            return db_transaction
        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Integrity error during transaction creation: {e}")
            raise TransactionUpdateError(detail="A transaction with this reference ID might already exist or a unique constraint was violated.")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error during transaction creation: {e}")
            raise UPIServiceException(detail="Failed to create transaction due to an internal error.")

    def get_transaction_by_id(self, transaction_id: str) -> UPITransaction:
        """Retrieves a transaction by its external transaction_id."""
        db_transaction = self.db.query(UPITransaction).filter(UPITransaction.transaction_id == transaction_id).first()
        if not db_transaction:
            raise TransactionNotFound(identifier=transaction_id)
        return db_transaction

    def get_transaction_by_reference(self, reference_id: str) -> UPITransaction:
        """Retrieves a transaction by its internal reference_id."""
        db_transaction = self.db.query(UPITransaction).filter(UPITransaction.reference_id == reference_id).first()
        if not db_transaction:
            raise TransactionNotFound(identifier=reference_id)
        return db_transaction

    def list_transactions(self, skip: int = 0, limit: int = 100) -> List[UPITransaction]:
        """Lists all transactions with pagination."""
        return self.db.query(UPITransaction).offset(skip).limit(limit).all()

    def update_transaction_status(self, transaction_id: str, update_in: UPITransactionUpdate) -> UPITransaction:
        """Updates the status and details of an existing transaction."""
        db_transaction = self.get_transaction_by_id(transaction_id)
        
        # Prevent updating a final status (SUCCESS, FAILED, REFUNDED)
        if db_transaction.status in [TransactionStatus.SUCCESS, TransactionStatus.FAILED, TransactionStatus.REFUNDED]:
            logger.warning(f"Attempted to update final status for transaction {transaction_id}. Current status: {db_transaction.status.value}")
            raise TransactionUpdateError(detail=f"Cannot update a transaction with final status: {db_transaction.status.value}")

        # Apply updates
        update_data = update_in.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_transaction, key, value)
        
        try:
            self.db.add(db_transaction)
            self.db.commit()
            self.db.refresh(db_transaction)
            logger.info(f"Updated transaction {transaction_id} to status: {db_transaction.status.value}")
            return db_transaction
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating transaction {transaction_id}: {e}")
            raise TransactionUpdateError(detail="Failed to update transaction status due to an internal error.")

    def delete_transaction(self, transaction_id: str) -> None:
        """Deletes a transaction by its external transaction_id."""
        db_transaction = self.get_transaction_by_id(transaction_id)
        
        try:
            self.db.delete(db_transaction)
            self.db.commit()
            logger.info(f"Deleted transaction: {transaction_id}")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error deleting transaction {transaction_id}: {e}")
            raise UPIServiceException(detail="Failed to delete transaction due to an internal error.")

# Dependency to get the service instance
def get_upi_service(db: Session) -> UPITransactionService:
    return UPITransactionService(db)