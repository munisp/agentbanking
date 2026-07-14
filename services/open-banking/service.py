from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from fastapi import HTTPException, status
from passlib.context import CryptContext
import logging
from decimal import Decimal

from models import User, Account, Balance, Transaction, AccountStatus, CreditDebitIndicator, BalanceType
from schemas import UserCreate, AccountCreate, AccountUpdate, TransactionResponse, BalanceResponse

log = logging.getLogger(__name__)

# --- Custom Exceptions ---

class NotFoundException(HTTPException):
    def __init__(self, detail: str) -> None:
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)

class ConflictException(HTTPException):
    def __init__(self, detail: str) -> None:
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)

class UnauthorizedException(HTTPException):
    def __init__(self, detail: str = "Could not validate credentials") -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )

class ForbiddenException(HTTPException):
    def __init__(self, detail: str = "Operation forbidden") -> None:
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)

# --- Security Service ---

class SecurityService:
    """Handles password hashing and verification."""
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    def get_password_hash(self, password: str) -> str:
        return self.pwd_context.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return self.pwd_context.verify(plain_password, hashed_password)

security_service = SecurityService()

# --- Open Banking Service (Business Logic) ---

class OpenBankingService:
    """
    Core business logic service for Open Banking entities.
    All database operations are performed asynchronously.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # --- User Operations ---

    async def create_user(self, user_in: UserCreate) -> User:
        """Creates a new user, checking for existing email."""
        log.info(f"Attempting to create user with email: {user_in.email}")
        
        # Check if user already exists
        existing_user = await self.get_user_by_email(user_in.email)
        if existing_user:
            raise ConflictException(detail=f"User with email '{user_in.email}' already exists.")

        hashed_password = security_service.get_password_hash(user_in.password)
        
        new_user = User(
            email=user_in.email,
            hashed_password=hashed_password,
        )
        self.db.add(new_user)
        await self.db.commit()
        await self.db.refresh(new_user)
        log.info(f"User created successfully with ID: {new_user.id}")
        return new_user

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Retrieves a user by email."""
        stmt = select(User).where(User.email == email)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_user_by_id(self, user_id: str) -> User:
        """Retrieves a user by ID, raising NotFoundException if not found."""
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        user = result.scalars().first()
        if not user:
            raise NotFoundException(detail=f"User with ID '{user_id}' not found.")
        return user

    # --- Account Operations ---

    async def create_account(self, user_id: str, account_in: AccountCreate) -> Account:
        """Creates a new account for a given user."""
        log.info(f"Creating account for user ID: {user_id}")
        
        # Ensure user exists (implicitly checked by ForeignKey, but good for explicit error)
        await self.get_user_by_id(user_id)

        new_account = Account(
            owner_id=user_id,
            currency=account_in.currency.upper(),
            nickname=account_in.nickname,
        )
        self.db.add(new_account)
        
        # Initialize with a zero balance (Booked and Available)
        initial_balance_booked = Balance(
            account_id=new_account.id,
            amount=Decimal(0.00),
            currency=new_account.currency,
            type=BalanceType.OpeningBooked,
            credit_debit_indicator=CreditDebitIndicator.Credit,
        )
        initial_balance_available = Balance(
            account_id=new_account.id,
            amount=Decimal(0.00),
            currency=new_account.currency,
            type=BalanceType.ClosingAvailable,
            credit_debit_indicator=CreditDebitIndicator.Credit,
        )
        self.db.add_all([initial_balance_booked, initial_balance_available])

        await self.db.commit()
        await self.db.refresh(new_account)
        log.info(f"Account created successfully with ID: {new_account.id}")
        return new_account

    async def get_account_by_id(self, account_id: str) -> Account:
        """Retrieves an account by ID."""
        stmt = select(Account).where(Account.id == account_id)
        result = await self.db.execute(stmt)
        account = result.scalars().first()
        if not account:
            raise NotFoundException(detail=f"Account with ID '{account_id}' not found.")
        return account

    async def get_accounts_for_user(self, user_id: str) -> List[Account]:
        """Retrieves all accounts for a given user."""
        stmt = select(Account).where(Account.owner_id == user_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update_account(self, account_id: str, account_in: AccountUpdate) -> Account:
        """Updates an account's nickname or status."""
        log.info(f"Updating account ID: {account_id}")
        
        account = await self.get_account_by_id(account_id)
        
        update_data = account_in.model_dump(exclude_unset=True)
        if not update_data:
            return account # No update needed

        stmt = (
            update(Account)
            .where(Account.id == account_id)
            .values(**update_data)
            .returning(Account)
        )
        
        await self.db.execute(stmt)
        await self.db.commit()
        await self.db.refresh(account)
        log.info(f"Account ID {account_id} updated.")
        return account

    async def delete_account(self, account_id: str) -> None:
        """Deletes an account and all related data (balances, transactions)."""
        log.warning(f"Deleting account ID: {account_id}")
        
        # The cascade="all, delete-orphan" in models.py handles related balances and transactions
        stmt = delete(Account).where(Account.id == account_id)
        result = await self.db.execute(stmt)
        
        if result.rowcount == 0:
            raise NotFoundException(detail=f"Account with ID '{account_id}' not found.")
            
        await self.db.commit()
        log.info(f"Account ID {account_id} deleted successfully.")

    # --- Transaction Operations ---

    async def create_transaction(
        self, 
        account_id: str, 
        amount: Decimal, 
        indicator: CreditDebitIndicator, 
        reference: Optional[str] = None,
        information: Optional[str] = None
    ) -> Transaction:
        """
        Creates a new transaction and updates the account balance in a single transaction.
        This is a simplified example of a financial transaction.
        """
        log.info(f"Processing transaction for account ID {account_id}: {indicator.value} {amount}")
        
        account = await self.get_account_by_id(account_id)
        
        # 1. Create the new transaction
        new_transaction = Transaction(
            account_id=account_id,
            amount=amount,
            currency=account.currency,
            credit_debit_indicator=indicator,
            transaction_reference=reference,
            transaction_information=information,
        )
        self.db.add(new_transaction)
        
        # 2. Update the account balance (ClosingAvailable is used as the current balance)
        # Find the latest ClosingAvailable balance
        balance_stmt = (
            select(Balance)
            .where(Balance.account_id == account_id, Balance.type == BalanceType.ClosingAvailable)
            .order_by(Balance.datetime.desc())
        )
        result = await self.db.execute(balance_stmt)
        current_balance = result.scalars().first()

        if not current_balance:
            # Should not happen if account creation is correct, but good to handle
            raise NotFoundException(detail=f"Current balance for account '{account_id}' not found.")

        # Calculate new balance
        new_balance_amount = current_balance.amount
        if indicator == CreditDebitIndicator.Credit:
            new_balance_amount += amount
        else:
            new_balance_amount -= amount
            
        # Create a new balance record (immutable ledger approach)
        new_balance = Balance(
            account_id=account_id,
            amount=new_balance_amount,
            currency=account.currency,
            type=BalanceType.ClosingAvailable,
            credit_debit_indicator=CreditDebitIndicator.Credit if new_balance_amount >= 0 else CreditDebitIndicator.Debit,
        )
        self.db.add(new_balance)

        # Commit both the transaction and the new balance record
        await self.db.commit()
        await self.db.refresh(new_transaction)
        log.info(f"Transaction {new_transaction.id} and new balance recorded.")
        return new_transaction

    # --- Data Retrieval Operations ---

    async def get_transactions_for_account(self, account_id: str, limit: int = 100) -> List[Transaction]:
        """Retrieves a list of transactions for an account."""
        await self.get_account_by_id(account_id) # Check if account exists
        
        stmt = (
            select(Transaction)
            .where(Transaction.account_id == account_id)
            .order_by(Transaction.booking_date_time.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_balances_for_account(self, account_id: str) -> List[Balance]:
        """Retrieves all balance records for an account."""
        await self.get_account_by_id(account_id) # Check if account exists
        
        stmt = (
            select(Balance)
            .where(Balance.account_id == account_id)
            .order_by(Balance.datetime.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

# Dependency to get the service instance
async def get_open_banking_service(db: AsyncSession) -> OpenBankingService:
    """Dependency function to provide the OpenBankingService."""
    return OpenBankingService(db)