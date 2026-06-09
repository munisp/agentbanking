import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from . import models, schemas

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Custom Exceptions ---

class TransactionNotFoundError(HTTPException):
    """Custom exception for when a transaction is not found."""
    def __init__(self, detail: str = "Payment transaction not found") -> None:
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)

class TransactionAlreadyExistsError(HTTPException):
    """Custom exception for when a transaction with the same unique ID already exists."""
    def __init__(self, detail: str = "Payment transaction with this PAPSS reference ID already exists") -> None:
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)

class InvalidTransactionStateError(HTTPException):
    """Custom exception for invalid state transitions."""
    def __init__(self, detail: str = "Invalid transaction state transition") -> None:
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

# --- Service Layer ---

class PapssIntegrationService:
    """
    Business logic layer for managing PAPSS Payment Transactions.
    Handles database interactions, validation, and error handling.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def create_transaction(self, transaction_data: schemas.PaymentTransactionCreate) -> models.PaymentTransaction:
        """
        Creates a new payment transaction in the database.
        """
        logger.info(f"Attempting to create new transaction with PAPSS ID: {transaction_data.papss_ref_id}")
        
        # Check for existing transaction with the same unique ID
        existing_transaction = self.db.query(models.PaymentTransaction).filter(
            models.PaymentTransaction.papss_ref_id == transaction_data.papss_ref_id
        ).first()
        
        if existing_transaction:
            logger.warning(f"Transaction creation failed: PAPSS ID {transaction_data.papss_ref_id} already exists.")
            raise TransactionAlreadyExistsError()

        db_transaction = models.PaymentTransaction(**transaction_data.model_dump())
        
        try:
            self.db.add(db_transaction)
            self.db.commit()
            self.db.refresh(db_transaction)
            logger.info(f"Transaction created successfully with ID: {db_transaction.id}")
            return db_transaction
        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Database integrity error during creation: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid data provided for transaction creation.")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error during transaction creation: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred.")

    def get_transaction(self, transaction_id: int) -> models.PaymentTransaction:
        """
        Retrieves a single payment transaction by its primary key ID.
        """
        db_transaction = self.db.query(models.PaymentTransaction).filter(
            models.PaymentTransaction.id == transaction_id
        ).first()
        
        if not db_transaction:
            logger.warning(f"Transaction with ID {transaction_id} not found.")
            raise TransactionNotFoundError()
            
        return db_transaction

    def get_transactions(self, skip: int = 0, limit: int = 100) -> List[models.PaymentTransaction]:
        """
        Retrieves a list of payment transactions with pagination.
        """
        return self.db.query(models.PaymentTransaction).offset(skip).limit(limit).all()

    def update_transaction(self, transaction_id: int, update_data: schemas.PaymentTransactionUpdate) -> models.PaymentTransaction:
        """
        Updates the status and/or error details of an existing transaction.
        """
        db_transaction = self.get_transaction(transaction_id) # Uses get_transaction which handles 404
        
        update_dict = update_data.model_dump(exclude_unset=True)
        
        if not update_dict:
            logger.info(f"No update data provided for transaction ID: {transaction_id}")
            return db_transaction

        # Simple state transition check (can be expanded for complex logic)
        if 'status' in update_dict and db_transaction.status.value in ["SETTLED", "FAILED", "CANCELLED"]:
            new_status = update_dict['status'].value
            if new_status != db_transaction.status.value:
                logger.warning(f"Attempted to change status of final state transaction {transaction_id} from {db_transaction.status.value} to {new_status}")
                raise InvalidTransactionStateError(detail=f"Cannot change status of a final state transaction ({db_transaction.status.value}).")

        logger.info(f"Updating transaction ID {transaction_id} with data: {update_dict}")
        
        for key, value in update_dict.items():
            setattr(db_transaction, key, value)
        
        try:
            self.db.add(db_transaction)
            self.db.commit()
            self.db.refresh(db_transaction)
            logger.info(f"Transaction ID {transaction_id} updated successfully.")
            return db_transaction
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error during transaction update: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred during update.")

    def delete_transaction(self, transaction_id: int) -> None:
        """
        Deletes a payment transaction by its primary key ID.
        """
        db_transaction = self.get_transaction(transaction_id) # Uses get_transaction which handles 404
        
        logger.info(f"Attempting to delete transaction ID: {transaction_id}")
        
        try:
            self.db.delete(db_transaction)
            self.db.commit()
            logger.info(f"Transaction ID {transaction_id} deleted successfully.")
            return {"ok": True}
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error during transaction deletion: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred during deletion.")
