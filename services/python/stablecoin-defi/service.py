import logging
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from passlib.context import CryptContext

from models import User, Stablecoin, Account, Transaction
from schemas import (
    UserCreate, UserUpdate, StablecoinCreate, StablecoinUpdate,
    AccountCreate, AccountUpdate, TransactionCreate, TransactionType
)

# --- Configuration and Setup ---

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- Custom Exceptions ---

class ServiceException(Exception):
    """Base exception for service layer errors."""
    def __init__(self, name: str, status_code: int, detail: str) -> None:
        self.name = name
        self.status_code = status_code
        self.detail = detail

class NotFoundException(ServiceException):
    def __init__(self, detail: str = "Item not found") -> None:
        super().__init__("NotFound", 404, detail)

class ConflictException(ServiceException):
    def __init__(self, detail: str = "Resource already exists") -> None:
        super().__init__("Conflict", 409, detail)

class ForbiddenException(ServiceException):
    def __init__(self, detail: str = "Operation forbidden") -> None:
        super().__init__("Forbidden", 403, detail)

class BadRequestException(ServiceException):
    def __init__(self, detail: str = "Bad request") -> None:
        super().__init__("BadRequest", 400, detail)

# --- Utility Functions ---

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

# --- User Service ---

def get_user(db: Session, user_id: UUID) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()

def get_user_by_username(db: Session, username: str) -> Optional[User]:
    return db.query(User).filter(User.username == username).first()

def create_user(db: Session, user: UserCreate) -> User:
    if get_user_by_username(db, user.username):
        raise ConflictException(detail=f"User with username '{user.username}' already exists.")
    
    hashed_password = get_password_hash(user.password)
    db_user = User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password
    )
    try:
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        logger.info(f"User created: {db_user.username}")
        return db_user
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error creating user: {e}")
        raise ConflictException(detail="Email or username already registered.")

# --- Stablecoin Service (Admin-level CRUD) ---

def get_stablecoin(db: Session, stablecoin_id: int) -> Optional[Stablecoin]:
    return db.query(Stablecoin).filter(Stablecoin.id == stablecoin_id).first()

def get_stablecoin_by_symbol(db: Session, symbol: str) -> Optional[Stablecoin]:
    return db.query(Stablecoin).filter(Stablecoin.symbol == symbol).first()

def get_stablecoins(db: Session, skip: int = 0, limit: int = 100) -> List[Stablecoin]:
    return db.query(Stablecoin).offset(skip).limit(limit).all()

def create_stablecoin(db: Session, stablecoin: StablecoinCreate) -> Stablecoin:
    if get_stablecoin_by_symbol(db, stablecoin.symbol):
        raise ConflictException(detail=f"Stablecoin with symbol '{stablecoin.symbol}' already exists.")
    
    db_stablecoin = Stablecoin(**stablecoin.model_dump())
    try:
        db.add(db_stablecoin)
        db.commit()
        db.refresh(db_stablecoin)
        logger.info(f"Stablecoin created: {db_stablecoin.symbol}")
        return db_stablecoin
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error creating stablecoin: {e}")
        raise ConflictException(detail="Stablecoin symbol already exists.")

def update_stablecoin(db: Session, stablecoin_id: int, stablecoin_in: StablecoinUpdate) -> Stablecoin:
    db_stablecoin = get_stablecoin(db, stablecoin_id)
    if not db_stablecoin:
        raise NotFoundException(detail=f"Stablecoin with ID {stablecoin_id} not found.")
    
    update_data = stablecoin_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_stablecoin, key, value)
    
    try:
        db.commit()
        db.refresh(db_stablecoin)
        logger.info(f"Stablecoin updated: {db_stablecoin.symbol}")
        return db_stablecoin
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error updating stablecoin: {e}")
        raise ConflictException(detail="Stablecoin symbol already exists.")

# --- Account Service ---

def get_account(db: Session, account_id: UUID) -> Optional[Account]:
    return db.query(Account).filter(Account.id == account_id).first()

def get_user_account_by_stablecoin(db: Session, user_id: UUID, stablecoin_id: int) -> Optional[Account]:
    return db.query(Account).filter(
        Account.user_id == user_id,
        Account.stablecoin_id == stablecoin_id
    ).first()

def get_user_accounts(db: Session, user_id: UUID, skip: int = 0, limit: int = 100) -> List[Account]:
    return db.query(Account).filter(Account.user_id == user_id).offset(skip).limit(limit).all()

def create_account(db: Session, user_id: UUID, account: AccountCreate) -> Account:
    if not get_stablecoin(db, account.stablecoin_id):
        raise NotFoundException(detail=f"Stablecoin with ID {account.stablecoin_id} not found.")
    
    if get_user_account_by_stablecoin(db, user_id, account.stablecoin_id):
        raise ConflictException(detail=f"Account for user {user_id} and stablecoin {account.stablecoin_id} already exists.")

    db_account = Account(
        user_id=user_id,
        stablecoin_id=account.stablecoin_id,
        balance=0.0, # Always start at 0
        deposit_rate=0.05, # Default rates for new accounts
        borrow_rate=0.08
    )
    try:
        db.add(db_account)
        db.commit()
        db.refresh(db_account)
        logger.info(f"Account created for user {user_id} and stablecoin {account.stablecoin_id}")
        return db_account
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error creating account: {e}")
        raise ConflictException(detail="Account already exists for this user and stablecoin.")

def update_account_rates(db: Session, account_id: UUID, account_in: AccountUpdate) -> Account:
    db_account = get_account(db, account_id)
    if not db_account:
        raise NotFoundException(detail=f"Account with ID {account_id} not found.")
    
    update_data = account_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_account, key, value)
    
    try:
        db.commit()
        db.refresh(db_account)
        logger.info(f"Account rates updated for account {account_id}")
        return db_account
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating account rates: {e}")
        raise BadRequestException(detail="Could not update account rates.")

# --- Transaction Service ---

def get_transactions_by_account(db: Session, account_id: UUID, skip: int = 0, limit: int = 100) -> List[Transaction]:
    return db.query(Transaction).filter(Transaction.account_id == account_id).offset(skip).limit(limit).all()

def process_transaction(db: Session, account_id: UUID, transaction_in: TransactionCreate) -> Transaction:
    db_account = get_account(db, account_id)
    if not db_account:
        raise NotFoundException(detail=f"Account with ID {account_id} not found.")
    
    amount = transaction_in.amount
    tx_type = transaction_in.type
    
    # Start transaction block
    try:
        if tx_type == TransactionType.deposit:
            db_account.balance += amount
            rate = db_account.deposit_rate
            logger.info(f"Deposit of {amount} to account {account_id}. New balance: {db_account.balance}")
        
        elif tx_type == TransactionType.withdraw:
            if db_account.balance < amount:
                raise BadRequestException(detail="Insufficient balance for withdrawal.")
            db_account.balance -= amount
            rate = db_account.deposit_rate
            logger.info(f"Withdrawal of {amount} from account {account_id}. New balance: {db_account.balance}")

        elif tx_type == TransactionType.borrow:
            # Simple borrow logic: increase balance, track rate
            db_account.balance += amount
            rate = db_account.borrow_rate
            logger.info(f"Borrow of {amount} to account {account_id}. New balance: {db_account.balance}")

        elif tx_type == TransactionType.repay:
            # Simple repay logic: decrease balance, track rate
            if db_account.balance < amount:
                # In a real system, this would check the total borrowed amount, not just the balance.
                # For simplicity, we assume balance can go negative to represent debt, but repay must not exceed debt.
                # For this implementation, we'll just ensure the balance doesn't go positive from a negative debt.
                # A more robust model would track borrowed_amount separately.
                pass # Allow repayment even if balance is positive (over-repayment)
            
            db_account.balance -= amount
            rate = db_account.borrow_rate
            logger.info(f"Repay of {amount} from account {account_id}. New balance: {db_account.balance}")

        else:
            raise BadRequestException(detail=f"Invalid transaction type: {tx_type}")

        # Create the transaction record
        db_transaction = Transaction(
            account_id=account_id,
            stablecoin_id=db_account.stablecoin_id,
            type=tx_type,
            amount=amount,
            rate_at_time=rate
        )
        
        db.add(db_transaction)
        db.commit()
        db.refresh(db_account)
        db.refresh(db_transaction)
        
        return db_transaction

    except ServiceException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Critical error during transaction processing: {e}")
        raise BadRequestException(detail="Transaction failed due to an unexpected error.")

# --- Authentication Service ---

def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    user = get_user_by_username(db, username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    if not user.is_active:
        return None
    return user

def get_current_active_user(db: Session, user_id: UUID) -> User:
    user = get_user(db, user_id)
    if not user or not user.is_active:
        raise ForbiddenException(detail="Inactive user")
    return user