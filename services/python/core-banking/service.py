import uuid
import logging
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from passlib.context import CryptContext
import jwt  # Migrated from python-jose (CVE-2024-33663) to PyJWT
from jwt.exceptions import InvalidTokenError as JWTError
from config import settings
from models import User, Customer, Account, Transaction
from schemas import (
    UserCreate,
    CustomerCreate,
    CustomerUpdate,
    AccountCreate,
    AccountUpdate,
    TransactionCreate,
    TokenData,
)

# --- Configuration and Setup ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
logger = logging.getLogger(__name__)

# --- Custom Exceptions ---

class ServiceException(Exception):
    """Base class for service-layer exceptions."""
    def __init__(self, message: str, status_code: int = 400) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)

class NotFoundException(ServiceException):
    """Raised when a requested resource is not found."""
    def __init__(self, resource_name: str, identifier: str) -> None:
        super().__init__(f"{resource_name} with identifier '{identifier}' not found.", 404)

class ConflictException(ServiceException):
    """Raised when a resource already exists or a unique constraint is violated."""
    def __init__(self, message: str) -> None:
        super().__init__(message, 409)

class InsufficientFundsException(ServiceException):
    """Raised when a transaction exceeds the available balance."""
    def __init__(self, account_id: uuid.UUID) -> None:
        super().__init__(f"Insufficient funds in account {account_id}.", 400)

class InvalidTransactionException(ServiceException):
    """Raised for invalid transaction types or amounts."""
    def __init__(self, message: str) -> None:
        super().__init__(message, 400)

class AuthenticationException(ServiceException):
    """Raised for authentication or authorization failures."""
    def __init__(self, message: str = "Could not validate credentials.") -> None:
        super().__init__(message, 401)

# --- Utility Functions ---

def get_password_hash(password: str) -> str:
    """Hashes a password using bcrypt."""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Creates a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "sub": str(data["user_id"])})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def generate_account_number() -> str:
    """Generates a simple 16-digit account number."""
    # In a real system, this would involve a more robust, collision-resistant mechanism
    # and possibly a check digit. For simplicity, we use a random UUID part.
    return str(uuid.uuid4().int)[:16]

# --- User Service ---

class UserService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_user(self, user_in: UserCreate) -> User:
        """Creates a new user and hashes the password."""
        hashed_password = get_password_hash(user_in.password)
        db_user = User(
            email=user_in.email,
            hashed_password=hashed_password,
            is_active=user_in.is_active,
            is_superuser=user_in.is_superuser,
        )
        try:
            self.db.add(db_user)
            await self.db.commit()
            await self.db.refresh(db_user)
            logger.info(f"User created: {db_user.email}")
            return db_user
        except IntegrityError:
            await self.db.rollback()
            raise ConflictException(f"User with email '{user_in.email}' already exists.")

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Retrieves a user by email."""
        stmt = select(User).where(User.email == email)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: uuid.UUID) -> User:
        """Retrieves a user by ID."""
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        db_user = result.scalar_one_or_none()
        if db_user is None:
            raise NotFoundException("User", str(user_id))
        return db_user

    async def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """Authenticates a user by email and password."""
        user = await self.get_user_by_email(email)
        if not user or not verify_password(password, user.hashed_password):
            return None
        if not user.is_active:
            return None
        return user

    async def get_current_user(self, token: str) -> User:
        """Validates JWT token and returns the authenticated user."""
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            user_id: str = payload.get("sub")
            if user_id is None:
                raise AuthenticationException()
            token_data = TokenData(user_id=uuid.UUID(user_id))
        except JWTError:
            raise AuthenticationException()

        user = await self.get_user_by_id(token_data.user_id)
        if user is None:
            raise AuthenticationException()
        return user

# --- Customer Service ---

class CustomerService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_customer(self, customer_in: CustomerCreate) -> Customer:
        """Creates a new customer linked to a user."""
        db_customer = Customer(**customer_in.model_dump())
        try:
            self.db.add(db_customer)
            await self.db.commit()
            await self.db.refresh(db_customer)
            logger.info(f"Customer created for user_id: {db_customer.user_id}")
            return db_customer
        except IntegrityError as e:
            await self.db.rollback()
            if "unique constraint" in str(e):
                raise ConflictException("A customer already exists for this user or phone number.")
            raise

    async def get_customer(self, customer_id: uuid.UUID) -> Customer:
        """Retrieves a customer by ID."""
        stmt = select(Customer).where(Customer.id == customer_id)
        result = await self.db.execute(stmt)
        db_customer = result.scalar_one_or_none()
        if db_customer is None:
            raise NotFoundException("Customer", str(customer_id))
        return db_customer

    async def get_customer_by_user_id(self, user_id: uuid.UUID) -> Customer:
        """Retrieves a customer by user ID."""
        stmt = select(Customer).where(Customer.user_id == user_id)
        result = await self.db.execute(stmt)
        db_customer = result.scalar_one_or_none()
        if db_customer is None:
            raise NotFoundException("Customer", f"user_id {user_id}")
        return db_customer

    async def get_all_customers(self, skip: int = 0, limit: int = 100) -> List[Customer]:
        """Retrieves a list of all customers."""
        stmt = select(Customer).offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update_customer(self, customer_id: uuid.UUID, customer_in: CustomerUpdate) -> Customer:
        """Updates an existing customer's details."""
        db_customer = await self.get_customer(customer_id)
        update_data = customer_in.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_customer, key, value)
        
        db_customer.updated_at = datetime.utcnow()
        try:
            await self.db.commit()
            await self.db.refresh(db_customer)
            logger.info(f"Customer updated: {customer_id}")
            return db_customer
        except IntegrityError:
            await self.db.rollback()
            raise ConflictException("A customer with this phone number already exists.")

    async def delete_customer(self, customer_id: uuid.UUID) -> None:
        """Deletes a customer and their associated accounts/data (cascading delete not implemented in this service)."""
        db_customer = await self.get_customer(customer_id)
        await self.db.delete(db_customer)
        await self.db.commit()
        logger.info(f"Customer deleted: {customer_id}")

# --- Account Service ---

class AccountService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_account(self, account_in: AccountCreate) -> Account:
        """Creates a new bank account for a customer."""
        # Ensure customer exists
        customer_service = CustomerService(self.db)
        await customer_service.get_customer(account_in.customer_id)

        db_account = Account(
            **account_in.model_dump(),
            account_number=generate_account_number(),
            balance=0.0
        )
        try:
            self.db.add(db_account)
            await self.db.commit()
            await self.db.refresh(db_account)
            logger.info(f"Account created: {db_account.account_number} for customer {db_account.customer_id}")
            return db_account
        except IntegrityError:
            await self.db.rollback()
            raise ConflictException("Failed to create account due to a database constraint violation.")

    async def get_account(self, account_id: uuid.UUID) -> Account:
        """Retrieves an account by ID."""
        stmt = select(Account).where(Account.id == account_id)
        result = await self.db.execute(stmt)
        db_account = result.scalar_one_or_none()
        if db_account is None:
            raise NotFoundException("Account", str(account_id))
        return db_account

    async def get_accounts_by_customer(self, customer_id: uuid.UUID) -> List[Account]:
        """Retrieves all accounts for a given customer."""
        stmt = select(Account).where(Account.customer_id == customer_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update_account(self, account_id: uuid.UUID, account_in: AccountUpdate) -> Account:
        """Updates an existing account's details (e.g., status, type)."""
        db_account = await self.get_account(account_id)
        update_data = account_in.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_account, key, value)
        
        db_account.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(db_account)
        logger.info(f"Account updated: {account_id}")
        return db_account

# --- Transaction Service ---

class TransactionService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.account_service = AccountService(self.db)

    async def _update_balance(self, account: Account, amount: float, is_deposit: bool) -> None:
        """Internal function to safely update an account balance."""
        if is_deposit:
            account.balance += amount
        else:
            if account.balance < amount:
                raise InsufficientFundsException(account.id)
            account.balance -= amount
        account.updated_at = datetime.utcnow()
        self.db.add(account)

    async def create_transaction(self, transaction_in: TransactionCreate) -> Transaction:
        """Processes a single transaction (DEPOSIT or WITHDRAWAL)."""
        account = await self.account_service.get_account(transaction_in.account_id)

        if not account.is_active:
            raise InvalidTransactionException(f"Account {account.id} is not active.")

        amount = float(transaction_in.amount)
        transaction_type = transaction_in.transaction_type

        if transaction_type == "DEPOSIT":
            is_deposit = True
        elif transaction_type == "WITHDRAWAL":
            is_deposit = False
        elif transaction_type == "TRANSFER":
            raise InvalidTransactionException("Use the dedicated transfer endpoint for transfers.")
        else:
            raise InvalidTransactionException(f"Invalid transaction type: {transaction_type}")

        # Start transaction block
        try:
            await self._update_balance(account, amount, is_deposit)
            
            db_transaction = Transaction(
                **transaction_in.model_dump(),
                amount=amount,
                status="COMPLETED"
            )
            self.db.add(db_transaction)
            
            await self.db.commit()
            await self.db.refresh(db_transaction)
            logger.info(f"{transaction_type} of {amount} completed for account {account.id}")
            return db_transaction
        except InsufficientFundsException as e:
            await self.db.rollback()
            raise e
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Transaction failed for account {account.id}: {e}")
            raise InvalidTransactionException("Transaction failed due to an unexpected error.")

    async def transfer_funds(self, source_account_id: uuid.UUID, target_account_id: uuid.UUID, amount: float, description: Optional[str] = None) -> tuple[Transaction, Transaction]:
        """Processes a fund transfer between two accounts."""
        if source_account_id == target_account_id:
            raise InvalidTransactionException("Cannot transfer funds to the same account.")
        
        if amount <= 0:
            raise InvalidTransactionException("Transfer amount must be positive.")

        # Retrieve accounts
        source_account = await self.account_service.get_account(source_account_id)
        target_account = await self.account_service.get_account(target_account_id)

        if not source_account.is_active or not target_account.is_active:
            raise InvalidTransactionException("One or both accounts are not active.")

        # Start transaction block
        try:
            # 1. Withdrawal from source
            await self._update_balance(source_account, amount, is_deposit=False)
            
            source_transaction = Transaction(
                account_id=source_account_id,
                transaction_type="TRANSFER",
                amount=amount,
                description=f"Transfer to {target_account.account_number}. {description or ''}",
                status="COMPLETED"
            )
            self.db.add(source_transaction)

            # 2. Deposit to target
            await self._update_balance(target_account, amount, is_deposit=True)

            target_transaction = Transaction(
                account_id=target_account_id,
                transaction_type="TRANSFER",
                amount=amount,
                description=f"Transfer from {source_account.account_number}. {description or ''}",
                status="COMPLETED"
            )
            self.db.add(target_transaction)

            await self.db.commit()
            logger.info(f"Transfer of {amount} from {source_account.id} to {target_account.id} completed.")
            return source_transaction, target_transaction
        except InsufficientFundsException as e:
            await self.db.rollback()
            raise e
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Transfer failed: {e}")
            raise InvalidTransactionException("Transfer failed due to an unexpected error.")

    async def get_transaction(self, transaction_id: uuid.UUID) -> Transaction:
        """Retrieves a transaction by ID."""
        stmt = select(Transaction).where(Transaction.id == transaction_id)
        result = await self.db.execute(stmt)
        db_transaction = result.scalar_one_or_none()
        if db_transaction is None:
            raise NotFoundException("Transaction", str(transaction_id))
        return db_transaction

    async def get_transactions_by_account(self, account_id: uuid.UUID, skip: int = 0, limit: int = 100) -> List[Transaction]:
        """Retrieves transactions for a given account."""
        stmt = select(Transaction).where(Transaction.account_id == account_id).offset(skip).limit(limit).order_by(Transaction.timestamp.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())