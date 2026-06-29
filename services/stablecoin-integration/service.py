import logging
from typing import List, Optional
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from models import Stablecoin, Account, Transaction
from schemas import (
    StablecoinCreate, StablecoinUpdate, AccountCreate, AccountUpdate,
    TransactionCreate, TransactionUpdate, TransactionType, TransactionStatus
)

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Custom Exceptions ---

class ServiceException(HTTPException):
    """Base exception for service layer errors."""
    def __init__(self, detail: str, status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR) -> None:
        super().__init__(status_code=status_code, detail=detail)

class NotFoundException(ServiceException):
    """Raised when a requested resource is not found."""
    def __init__(self, resource_name: str, resource_id: int) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{resource_name} with ID {resource_id} not found."
        )

class IntegrityViolationException(ServiceException):
    """Raised for database integrity errors (e.g., unique constraint violation)."""
    def __init__(self, detail: str) -> None:
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail
        )

class InsufficientBalanceException(ServiceException):
    """Raised when an account has insufficient balance for a transaction."""
    def __init__(self, account_id: int, required_amount: Decimal) -> None:
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Account {account_id} has insufficient balance for transaction of {required_amount}."
        )

class AccountLockedException(ServiceException):
    """Raised when an operation is attempted on a locked account."""
    def __init__(self, account_id: int) -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account {account_id} is locked and cannot perform this operation."
        )

# --- Stablecoin Service ---

class StablecoinService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_stablecoin(self, stablecoin_in: StablecoinCreate) -> Stablecoin:
        logger.info(f"Creating new stablecoin: {stablecoin_in.symbol}")
        try:
            db_stablecoin = Stablecoin(**stablecoin_in.model_dump())
            self.db.add(db_stablecoin)
            self.db.commit()
            self.db.refresh(db_stablecoin)
            return db_stablecoin
        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Integrity error creating stablecoin: {e}")
            raise IntegrityViolationException(detail="Stablecoin with this symbol or contract address already exists.")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error creating stablecoin: {e}")
            raise ServiceException(detail="Could not create stablecoin due to an unexpected error.")

    def get_stablecoin(self, stablecoin_id: int) -> Stablecoin:
        db_stablecoin = self.db.query(Stablecoin).filter(Stablecoin.id == stablecoin_id).first()
        if not db_stablecoin:
            raise NotFoundException("Stablecoin", stablecoin_id)
        return db_stablecoin

    def get_all_stablecoins(self, skip: int = 0, limit: int = 100) -> List[Stablecoin]:
        return self.db.query(Stablecoin).offset(skip).limit(limit).all()

    def update_stablecoin(self, stablecoin_id: int, stablecoin_in: StablecoinUpdate) -> Stablecoin:
        db_stablecoin = self.get_stablecoin(stablecoin_id)
        logger.info(f"Updating stablecoin ID {stablecoin_id}")
        update_data = stablecoin_in.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_stablecoin, key, value)
        
        try:
            self.db.add(db_stablecoin)
            self.db.commit()
            self.db.refresh(db_stablecoin)
            return db_stablecoin
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error updating stablecoin: {e}")
            raise ServiceException(detail="Could not update stablecoin due to an unexpected error.")

    def delete_stablecoin(self, stablecoin_id: int) -> None:
        db_stablecoin = self.get_stablecoin(stablecoin_id)
        logger.warning(f"Deleting stablecoin ID {stablecoin_id}")
        self.db.delete(db_stablecoin)
        self.db.commit()

# --- Account Service ---

class AccountService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_account(self, account_in: AccountCreate) -> Account:
        logger.info(f"Creating account for user {account_in.user_id} with stablecoin {account_in.stablecoin_id}")
        # Check if stablecoin exists
        if not self.db.query(Stablecoin).filter(Stablecoin.id == account_in.stablecoin_id).first():
            raise NotFoundException("Stablecoin", account_in.stablecoin_id)

        try:
            db_account = Account(**account_in.model_dump())
            self.db.add(db_account)
            self.db.commit()
            self.db.refresh(db_account)
            return db_account
        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Integrity error creating account: {e}")
            raise IntegrityViolationException(detail="Account with this wallet address already exists or user already has an account for this stablecoin.")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error creating account: {e}")
            raise ServiceException(detail="Could not create account due to an unexpected error.")

    def get_account(self, account_id: int) -> Account:
        db_account = self.db.query(Account).filter(Account.id == account_id).first()
        if not db_account:
            raise NotFoundException("Account", account_id)
        return db_account

    def get_all_accounts(self, skip: int = 0, limit: int = 100) -> List[Account]:
        return self.db.query(Account).offset(skip).limit(limit).all()

    def get_accounts_by_user(self, user_id: int, skip: int = 0, limit: int = 100) -> List[Account]:
        return self.db.query(Account).filter(Account.user_id == user_id).offset(skip).limit(limit).all()

    def update_account(self, account_id: int, account_in: AccountUpdate) -> Account:
        db_account = self.get_account(account_id)
        logger.info(f"Updating account ID {account_id}")
        update_data = account_in.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_account, key, value)
        
        try:
            self.db.add(db_account)
            self.db.commit()
            self.db.refresh(db_account)
            return db_account
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error updating account: {e}")
            raise ServiceException(detail="Could not update account due to an unexpected error.")

    def delete_account(self, account_id: int) -> None:
        db_account = self.get_account(account_id)
        logger.warning(f"Deleting account ID {account_id}")
        self.db.delete(db_account)
        self.db.commit()

# --- Transaction Service ---

class TransactionService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.account_service = AccountService(db)

    def create_transaction(self, transaction_in: TransactionCreate) -> Transaction:
        logger.info(f"Creating transaction of type {transaction_in.transaction_type} for account {transaction_in.account_id}")
        
        db_account = self.account_service.get_account(transaction_in.account_id)
        
        if db_account.is_locked:
            raise AccountLockedException(db_account.id)

        # Check if stablecoin is active
        db_stablecoin = self.db.query(Stablecoin).filter(Stablecoin.id == transaction_in.stablecoin_id).first()
        if not db_stablecoin or not db_stablecoin.is_active:
            raise ServiceException(detail=f"Stablecoin {transaction_in.stablecoin_id} is not active or does not exist.", status_code=status.HTTP_400_BAD_REQUEST)

        amount = Decimal(str(transaction_in.amount))
        
        # Transaction Management (Simulated Balance Update)
        try:
            # 1. Create the transaction record
            db_transaction = Transaction(**transaction_in.model_dump(exclude_none=True))
            db_transaction.status = TransactionStatus.COMPLETED.value # Assume instant completion for DEPOSIT/TRANSFER/WITHDRAWAL
            
            # 2. Update account balance based on transaction type
            if transaction_in.transaction_type == TransactionType.DEPOSIT:
                db_account.balance += amount
            elif transaction_in.transaction_type == TransactionType.WITHDRAWAL or transaction_in.transaction_type == TransactionType.TRANSFER:
                if db_account.balance < amount:
                    raise InsufficientBalanceException(db_account.id, amount)
                db_account.balance -= amount
            
            # 3. Commit both changes in a single transaction
            self.db.add(db_transaction)
            self.db.add(db_account)
            self.db.commit()
            self.db.refresh(db_transaction)
            self.db.refresh(db_account)
            
            logger.info(f"Transaction {db_transaction.id} completed. New balance for account {db_account.id}: {db_account.balance}")
            return db_transaction
            
        except InsufficientBalanceException:
            self.db.rollback()
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error during transaction creation/processing: {e}")
            raise ServiceException(detail="Could not process transaction due to an unexpected error.")

    def get_transaction(self, transaction_id: int) -> Transaction:
        db_transaction = self.db.query(Transaction).filter(Transaction.id == transaction_id).first()
        if not db_transaction:
            raise NotFoundException("Transaction", transaction_id)
        return db_transaction

    def get_transactions_by_account(self, account_id: int, skip: int = 0, limit: int = 100) -> List[Transaction]:
        return self.db.query(Transaction).filter(Transaction.account_id == account_id).offset(skip).limit(limit).all()

    def update_transaction_status(self, transaction_id: int, transaction_in: TransactionUpdate) -> Transaction:
        db_transaction = self.get_transaction(transaction_id)
        logger.info(f"Updating status for transaction ID {transaction_id} to {transaction_in.status}")
        
        update_data = transaction_in.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_transaction, key, value)
        
        try:
            self.db.add(db_transaction)
            self.db.commit()
            self.db.refresh(db_transaction)
            return db_transaction
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error updating transaction status: {e}")
            raise ServiceException(detail="Could not update transaction status due to an unexpected error.")