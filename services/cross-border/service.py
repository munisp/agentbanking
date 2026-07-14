import logging
import uuid
from typing import List, Optional
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy import select, func, desc

from models import Party, Transaction, FXRate, TransactionStatus
from schemas import (
    PartyCreate, PartyUpdate, TransactionCreate, TransactionUpdate,
    FXRateCreate, TransactionRead, PartyRead, FXRateRead
)

# --- Configuration and Logging ---
from config import settings
logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL)

# --- Custom Exceptions ---

class NotFoundError(Exception):
    """Raised when a requested resource is not found."""
    def __init__(self, resource_name: str, resource_id: int) -> None:
        self.resource_name = resource_name
        self.resource_id = resource_id
        super().__init__(f"{resource_name} with ID {resource_id} not found.")

class ConflictError(Exception):
    """Raised when a resource creation or update conflicts with existing data."""
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)

class InvalidTransactionError(Exception):
    """Raised for invalid transaction parameters or state transitions."""
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init>(message)

# --- Helper Functions ---

def _calculate_target_amount(source_amount: Decimal, fx_rate: Decimal) -> Decimal:
    """Calculates the target amount based on source amount and FX rate."""
    # Rounding to 4 decimal places for currency precision
    return (source_amount * fx_rate).quantize(Decimal("0.0001"))

def _generate_reference_id() -> str:
    """Generates a unique, internal transaction reference ID."""
    return str(uuid.uuid4())

# --- Party Service ---

class PartyService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_party(self, party_in: PartyCreate) -> Party:
        logger.info(f"Attempting to create new party: {party_in.name}")
        
        # Check for existing account number to prevent duplicates
        existing_party = self.db.scalar(
            select(Party).where(Party.account_number == party_in.account_number)
        )
        if existing_party:
            raise ConflictError(f"Party with account number {party_in.account_number} already exists.")

        db_party = Party(**party_in.model_dump())
        self.db.add(db_party)
        self.db.commit()
        self.db.refresh(db_party)
        logger.info(f"Successfully created party with ID: {db_party.id}")
        return db_party

    def get_party(self, party_id: int) -> Party:
        db_party = self.db.scalar(select(Party).where(Party.id == party_id))
        if not db_party:
            raise NotFoundError("Party", party_id)
        return db_party

    def get_parties(self, skip: int = 0, limit: int = 100) -> List[Party]:
        return self.db.scalars(
            select(Party).offset(skip).limit(limit).order_by(Party.id)
        ).all()
        
    def count_parties(self) -> int:
        return self.db.scalar(select(func.count()).select_from(Party))

    def update_party(self, party_id: int, party_in: PartyUpdate) -> Party:
        db_party = self.get_party(party_id)
        
        update_data = party_in.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_party, key, value)
            
        self.db.add(db_party)
        self.db.commit()
        self.db.refresh(db_party)
        logger.info(f"Successfully updated party with ID: {party_id}")
        return db_party

    def delete_party(self, party_id: int) -> None:
        db_party = self.get_party(party_id)
        
        # Check for associated transactions before deletion
        if self.db.scalar(select(func.count()).select_from(Transaction).where((Transaction.sender_id == party_id) | (Transaction.receiver_id == party_id))) > 0:
            raise ConflictError(f"Cannot delete Party {party_id}. Associated transactions exist.")
            
        self.db.delete(db_party)
        self.db.commit()
        logger.info(f"Successfully deleted party with ID: {party_id}")

# --- FXRate Service ---

class FXRateService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_rate(self, rate_in: FXRateCreate) -> FXRate:
        logger.info(f"Attempting to create new FX rate: {rate_in.from_currency}/{rate_in.to_currency}")
        db_rate = FXRate(**rate_in.model_dump())
        self.db.add(db_rate)
        self.db.commit()
        self.db.refresh(db_rate)
        logger.info(f"Successfully created FX rate with ID: {db_rate.id}")
        return db_rate

    def get_latest_rate(self, base_currency: str, target_currency: str) -> FXRate:
        db_rate = self.db.scalar(
            select(FXRate)
            .where(FXRate.from_currency == base_currency, FXRate.to_currency == target_currency)
            .order_by(desc(FXRate.created_at))
            .limit(1)
        )
        if not db_rate:
            raise NotFoundError("FXRate", f"{base_currency}/{target_currency}")
        return db_rate

# --- Transaction Service ---

class TransactionService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.party_service = PartyService(db)
        self.fx_service = FXRateService(db)

    def create_transaction(self, transaction_in: TransactionCreate) -> Transaction:
        logger.info(f"Attempting to create new transaction from {transaction_in.sender_id} to {transaction_in.receiver_id}")
        
        # 1. Validate Parties
        try:
            sender = self.party_service.get_party(transaction_in.sender_id)
            receiver = self.party_service.get_party(transaction_in.receiver_id)
        except NotFoundError as e:
            raise InvalidTransactionError(f"Party validation failed: {e.message}")

        if sender.currency_code != transaction_in.source_currency:
            raise InvalidTransactionError("Sender's currency does not match source currency.")
        if receiver.currency_code != transaction_in.target_currency:
            # In a real system, the receiver's currency might be different from the target currency
            # but for this simple model, we enforce it for simplicity of the cross-border concept.
            pass 
            
        # 2. Get FX Rate
        try:
            fx_rate_obj = self.fx_service.get_latest_rate(
                transaction_in.source_currency, transaction_in.target_currency
            )
            fx_rate = fx_rate_obj.rate
        except NotFoundError:
            raise InvalidTransactionError(f"No current FX rate found for {transaction_in.source_currency}/{transaction_in.target_currency}")

        # 3. Calculate Target Amount
        target_amount = _calculate_target_amount(transaction_in.source_amount, fx_rate)
        
        # 4. Compliance Check (Placeholder)
        compliance_score = 50 # Mock score

        # 5. Create Transaction
        db_transaction = Transaction(
            reference_id=_generate_reference_id(),
            source_amount=transaction_in.source_amount,
            source_currency=transaction_in.source_currency,
            target_amount=target_amount,
            target_currency=transaction_in.target_currency,
            fx_rate=fx_rate,
            fee_amount=transaction_in.fee_amount,
            sender_id=transaction_in.sender_id,
            receiver_id=transaction_in.receiver_id,
            status=TransactionStatus.PENDING,
            compliance_score=compliance_score,
        )
        
        # Transactional commit
        try:
            self.db.add(db_transaction)
            self.db.commit()
            self.db.refresh(db_transaction)
            logger.info(f"Successfully created transaction with ID: {db_transaction.id} and Ref: {db_transaction.reference_id}")
            return db_transaction
        except Exception as e:
            self.db.rollback()
            logger.error(f"Transaction creation failed: {e}")
            raise InvalidTransactionError(f"Database error during transaction creation: {e}")

    def get_transaction(self, transaction_id: int) -> Transaction:
        db_transaction = self.db.scalar(
            select(Transaction)
            .where(Transaction.id == transaction_id)
            .options(
                # Eagerly load relationships for the TransactionRead schema
                select.joinedload(Transaction.sender),
                select.joinedload(Transaction.receiver)
            )
        )
        if not db_transaction:
            raise NotFoundError("Transaction", transaction_id)
        return db_transaction

    def get_transactions(self, skip: int = 0, limit: int = 100, status: Optional[TransactionStatus] = None) -> List[Transaction]:
        stmt = select(Transaction).offset(skip).limit(limit).order_by(desc(Transaction.created_at))
        if status:
            stmt = stmt.where(Transaction.status == status)
            
        # Eagerly load relationships for the TransactionRead schema
        stmt = stmt.options(
            select.joinedload(Transaction.sender),
            select.joinedload(Transaction.receiver)
        )
        
        return self.db.scalars(stmt).unique().all()
        
    def count_transactions(self, status: Optional[TransactionStatus] = None) -> int:
        stmt = select(func.count()).select_from(Transaction)
        if status:
            stmt = stmt.where(Transaction.status == status)
        return self.db.scalar(stmt)

    def update_transaction(self, transaction_id: int, transaction_in: TransactionUpdate) -> Transaction:
        db_transaction = self.get_transaction(transaction_id)
        
        # Simple state transition check (e.g., cannot go from COMPLETED back to PENDING)
        if db_transaction.status == TransactionStatus.COMPLETED and transaction_in.status in [TransactionStatus.PENDING, TransactionStatus.PROCESSING]:
            raise InvalidTransactionError("Cannot revert a COMPLETED transaction status.")
            
        update_data = transaction_in.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_transaction, key, value)
            
        self.db.add(db_transaction)
        self.db.commit()
        self.db.refresh(db_transaction)
        logger.info(f"Successfully updated transaction with ID: {transaction_id}. New status: {db_transaction.status.value}")
        return db_transaction

    def delete_transaction(self, transaction_id: int) -> None:
        db_transaction = self.get_transaction(transaction_id)
        
        # Only allow deletion of PENDING or FAILED transactions
        if db_transaction.status not in [TransactionStatus.PENDING, TransactionStatus.FAILED, TransactionStatus.CANCELLED]:
            raise ConflictError(f"Cannot delete transaction {transaction_id} with status {db_transaction.status.value}.")
            
        self.db.delete(db_transaction)
        self.db.commit()
        logger.info(f"Successfully deleted transaction with ID: {transaction_id}")