import logging
import uuid
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from models import SCTInstTransaction, TransactionRecall, TransactionStatus, RecallReason, RecallStatus
from schemas import SCTInstTransactionCreate, SCTInstTransactionUpdate, TransactionRecallCreate

# --- Configuration and Logging ---
# Assuming settings is available from config.py, but importing directly for service file
# from config import settings 
# logger = logging.getLogger(settings.SERVICE_NAME) 
# Using a generic logger for now
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# --- Custom Exceptions ---

class ServiceException(Exception):
    """Base class for service-level exceptions."""
    def __init__(self, message: str, status_code: int = 500) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)

class TransactionNotFoundError(ServiceException):
    """Raised when a transaction is not found."""
    def __init__(self, transaction_id: uuid.UUID) -> None:
        super().__init__(f"SCT Inst Transaction with ID {transaction_id} not found.", 404)

class TransactionAlreadyExistsError(ServiceException):
    """Raised when a transaction with the same end-to-end ID already exists."""
    def __init__(self, end_to_end_id: str) -> None:
        super().__init__(f"SCT Inst Transaction with end-to-end ID '{end_to_end_id}' already exists.", 409)

class InvalidTransactionStateError(ServiceException):
    """Raised for invalid state transitions (e.g., trying to update a rejected transaction)."""
    def __init__(self, transaction_id: uuid.UUID, current_status: TransactionStatus, action: str) -> None:
        super().__init__(f"Cannot {action} transaction {transaction_id}. Current status is {current_status.value}.", 400)

class RecallNotAllowedError(ServiceException):
    """Raised when a recall request violates business rules (e.g., time limit)."""
    def __init__(self, message: str) -> None:
        super().__init__(message, 400)

# --- Service Implementation ---

class SCTInstService:
    """
    Business logic layer for SEPA Instant Credit Transfer transactions.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def create_transaction(self, transaction_data: SCTInstTransactionCreate) -> SCTInstTransaction:
        """
        Creates a new SCT Inst Transaction.
        """
        logger.info(f"Attempting to create new transaction with end_to_end_id: {transaction_data.end_to_end_id}")
        
        # 1. Check for existing transaction (uniqueness constraint)
        existing_tx = self.db.query(SCTInstTransaction).filter(
            SCTInstTransaction.end_to_end_id == transaction_data.end_to_end_id
        ).first()
        if existing_tx:
            raise TransactionAlreadyExistsError(transaction_data.end_to_end_id)

        # 2. Simulate instruction_id generation (in a real system, this would come from the payment engine)
        instruction_id = str(uuid.uuid4())

        # 3. Create the model instance
        db_transaction = SCTInstTransaction(
            **transaction_data.model_dump(exclude_unset=True),
            instruction_id=instruction_id,
            transaction_status=TransactionStatus.INITIATED
        )

        try:
            # 4. Transaction management: Add, commit, and refresh
            self.db.add(db_transaction)
            self.db.commit()
            self.db.refresh(db_transaction)
            logger.info(f"Transaction created successfully: {db_transaction.id}")
            return db_transaction
        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Integrity error during transaction creation: {e}")
            raise ServiceException("Database integrity error during transaction creation.", 500)
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"SQLAlchemy error during transaction creation: {e}")
            raise ServiceException("An unexpected database error occurred.", 500)

    def get_transaction_by_id(self, transaction_id: uuid.UUID) -> SCTInstTransaction:
        """
        Retrieves a single transaction by its ID.
        """
        transaction = self.db.query(SCTInstTransaction).filter(SCTInstTransaction.id == transaction_id).first()
        if not transaction:
            raise TransactionNotFoundError(transaction_id)
        return transaction

    def get_all_transactions(self, skip: int = 0, limit: int = 100) -> List[SCTInstTransaction]:
        """
        Retrieves a list of all transactions with pagination.
        """
        return self.db.query(SCTInstTransaction).offset(skip).limit(limit).all()

    def update_transaction_status(self, transaction_id: uuid.UUID, update_data: SCTInstTransactionUpdate) -> SCTInstTransaction:
        """
        Updates the status and related fields of an existing transaction.
        """
        db_transaction = self.get_transaction_by_id(transaction_id)
        
        # Prevent updates on final states (e.g., FAILED, REJECTED, CREDITED)
        final_states = [TransactionStatus.CREDITED, TransactionStatus.REJECTED, TransactionStatus.FAILED]
        if db_transaction.transaction_status in final_states:
            raise InvalidTransactionStateError(transaction_id, db_transaction.transaction_status, "update")

        update_dict = update_data.model_dump(exclude_unset=True)
        
        for key, value in update_dict.items():
            setattr(db_transaction, key, value)

        try:
            self.db.commit()
            self.db.refresh(db_transaction)
            logger.info(f"Transaction {transaction_id} status updated to {db_transaction.transaction_status.value}")
            return db_transaction
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"SQLAlchemy error during transaction update: {e}")
            raise ServiceException("An unexpected database error occurred during update.", 500)

    def delete_transaction(self, transaction_id: uuid.UUID) -> None:
        """
        Deletes a transaction by its ID. (Soft delete is preferred in production, but hard delete for CRUD requirement).
        """
        db_transaction = self.get_transaction_by_id(transaction_id)
        
        # Only allow deletion of transactions in INITIATED or FAILED state
        if db_transaction.transaction_status not in [TransactionStatus.INITIATED, TransactionStatus.FAILED]:
            raise InvalidTransactionStateError(transaction_id, db_transaction.transaction_status, "delete")

        try:
            self.db.delete(db_transaction)
            self.db.commit()
            logger.info(f"Transaction {transaction_id} deleted successfully.")
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"SQLAlchemy error during transaction deletion: {e}")
            raise ServiceException("An unexpected database error occurred during deletion.", 500)

    # --- Recall Logic ---

    def request_recall(self, transaction_id: uuid.UUID, recall_data: TransactionRecallCreate) -> TransactionRecall:
        """
        Initiates a recall request for a given transaction.
        """
        db_transaction = self.get_transaction_by_id(transaction_id)

        # Business Rule 1: Only allow recall on CREDITED transactions
        if db_transaction.transaction_status != TransactionStatus.CREDITED:
            raise InvalidTransactionStateError(transaction_id, db_transaction.transaction_status, "request recall")

        # Business Rule 2: Check for existing pending recall
        if any(r.recall_status == RecallStatus.PENDING for r in db_transaction.recalls):
            raise RecallNotAllowedError(f"Transaction {transaction_id} already has a pending recall request.")

        # Business Rule 3: Simulate 10 Banking Business Days limit (using 14 calendar days for simplicity)
        if db_transaction.execution_timestamp is None or (datetime.utcnow() - db_transaction.execution_timestamp) > timedelta(days=14):
            raise RecallNotAllowedError(f"Recall request for transaction {transaction_id} is outside the 10-day business limit.")

        db_recall = TransactionRecall(
            transaction_id=transaction_id,
            recall_request_date=datetime.utcnow(),
            recall_reason=recall_data.recall_reason
        )

        try:
            self.db.add(db_recall)
            # Update transaction status to RECALLED
            db_transaction.transaction_status = TransactionStatus.RECALLED
            self.db.commit()
            self.db.refresh(db_recall)
            logger.info(f"Recall requested for transaction {transaction_id}. Recall ID: {db_recall.id}")
            return db_recall
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"SQLAlchemy error during recall request: {e}")
            raise ServiceException("An unexpected database error occurred during recall request.", 500)

    def get_recall_by_id(self, recall_id: uuid.UUID) -> TransactionRecall:
        """
        Retrieves a single recall request by its ID.
        """
        recall = self.db.query(TransactionRecall).filter(TransactionRecall.id == recall_id).first()
        if not recall:
            raise TransactionNotFoundError(recall_id) # Reusing TransactionNotFoundError for simplicity
        return recall

    def finalize_recall(self, recall_id: uuid.UUID, status: RecallStatus, return_amount: Optional[float] = None, return_fee: Optional[float] = None) -> TransactionRecall:
        """
        Finalizes a recall request (simulating the Beneficiary Bank's response).
        """
        db_recall = self.get_recall_by_id(recall_id)

        if db_recall.recall_status != RecallStatus.PENDING:
            raise InvalidTransactionStateError(db_recall.id, db_recall.recall_status, "finalize recall")

        db_recall.recall_status = status
        db_recall.response_date = datetime.utcnow()
        
        if status == RecallStatus.RETURNED:
            if return_amount is None:
                raise RecallNotAllowedError("Return amount must be provided for a RETURNED status.")
            db_recall.return_amount = return_amount
            db_recall.return_fee = return_fee if return_fee is not None else 0
        
        try:
            self.db.commit()
            self.db.refresh(db_recall)
            logger.info(f"Recall {recall_id} finalized with status: {status.value}")
            return db_recall
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"SQLAlchemy error during recall finalization: {e}")
            raise ServiceException("An unexpected database error occurred during recall finalization.", 500)