import logging
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from models import CipsTransaction, TransactionStatus
from schemas import CipsTransactionCreate, CipsTransactionUpdate

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# --- Custom Exceptions ---

class ServiceException(Exception):
    """Base exception for service layer errors."""
    def __init__(self, message: str, status_code: int = 500) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

class TransactionNotFoundError(ServiceException):
    """Raised when a transaction is not found."""
    def __init__(self, identifier: str) -> None:
        super().__init__(f"Transaction with identifier '{identifier}' not found.", status_code=404)

class TransactionAlreadyExistsError(ServiceException):
    """Raised when a transaction with the given CIPS ID already exists."""
    def __init__(self, cips_id: str) -> None:
        super().__init__(f"Transaction with CIPS ID '{cips_id}' already exists.", status_code=409)

# --- Service Class ---

class CipsTransactionService:
    """
    Business logic layer for CIPS Transactions.
    Handles all database interactions and business rules.
    """
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_transaction(self, transaction_data: CipsTransactionCreate) -> CipsTransaction:
        """Creates a new CIPS transaction."""
        logger.info(f"Attempting to create transaction with CIPS ID: {transaction_data.cips_transaction_id}")
        
        # Check for existing transaction with the same CIPS ID
        if self.get_transaction_by_cips_id(transaction_data.cips_transaction_id):
            raise TransactionAlreadyExistsError(transaction_data.cips_transaction_id)

        db_transaction = CipsTransaction(
            cips_transaction_id=transaction_data.cips_transaction_id,
            sender_bank_id=transaction_data.sender_bank_id,
            receiver_bank_id=transaction_data.receiver_bank_id,
            amount=transaction_data.amount,
            currency=transaction_data.currency,
            status=TransactionStatus.PENDING # Always start as PENDING
        )
        
        try:
            self.db.add(db_transaction)
            self.db.commit()
            self.db.refresh(db_transaction)
            logger.info(f"Successfully created transaction with ID: {db_transaction.id}")
            return db_transaction
        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Integrity error during transaction creation: {e}")
            raise ServiceException("Database integrity error during creation.", status_code=500)
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error during transaction creation: {e}")
            raise ServiceException("An unexpected error occurred.", status_code=500)

    def get_transaction_by_id(self, transaction_id: int) -> CipsTransaction:
        """Retrieves a transaction by its internal database ID."""
        logger.info(f"Fetching transaction by internal ID: {transaction_id}")
        transaction = self.db.query(CipsTransaction).filter(CipsTransaction.id == transaction_id).first()
        if not transaction:
            raise TransactionNotFoundError(str(transaction_id))
        return transaction

    def get_transaction_by_cips_id(self, cips_id: str) -> Optional[CipsTransaction]:
        """Retrieves a transaction by its CIPS system ID."""
        logger.info(f"Fetching transaction by CIPS ID: {cips_id}")
        return self.db.query(CipsTransaction).filter(CipsTransaction.cips_transaction_id == cips_id).first()

    def list_transactions(self, skip: int = 0, limit: int = 100) -> List[CipsTransaction]:
        """Retrieves a list of transactions with pagination."""
        logger.info(f"Listing transactions (skip: {skip}, limit: {limit})")
        return self.db.query(CipsTransaction).offset(skip).limit(limit).all()

    def update_transaction_status(self, transaction_id: int, update_data: CipsTransactionUpdate) -> CipsTransaction:
        """Updates the status of an existing transaction."""
        logger.info(f"Attempting to update status for transaction ID: {transaction_id} to {update_data.status.value}")
        
        db_transaction = self.get_transaction_by_id(transaction_id)
        
        # Business rule: Cannot update status if already COMPLETED or FAILED
        if db_transaction.status in [TransactionStatus.COMPLETED, TransactionStatus.FAILED]:
            raise ServiceException(
                f"Cannot update status for transaction ID {transaction_id}. Current status is {db_transaction.status.value}.",
                status_code=400
            )

        db_transaction.status = update_data.status
        
        try:
            self.db.commit()
            self.db.refresh(db_transaction)
            logger.info(f"Successfully updated status for transaction ID: {transaction_id}")
            return db_transaction
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error during status update: {e}")
            raise ServiceException("An unexpected error occurred during status update.", status_code=500)

    def delete_transaction(self, transaction_id: int) -> None:
        """Deletes a transaction by its internal database ID."""
        logger.warning(f"Attempting to delete transaction ID: {transaction_id}")
        
        db_transaction = self.get_transaction_by_id(transaction_id)
        
        try:
            self.db.delete(db_transaction)
            self.db.commit()
            logger.warning(f"Successfully deleted transaction ID: {transaction_id}")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error during transaction deletion: {e}")
            raise ServiceException("An unexpected error occurred during deletion.", status_code=500)
