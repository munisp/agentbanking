import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
"""
Core Banking Service - Account Management and Transaction Processing
Remittance platform main banking engine with double-entry bookkeeping
"""

import logging
import os
import uuid
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any, Dict, List, Optional

import asyncpg
import redis.asyncio as aioredis
from database import Base, DatabaseManager, get_db
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, validator
from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from shared.audit import AuditContext, AuditLogger, EventType
from shared.config import Settings, get_settings
from shared.events import (
    AccountCreatedEvent,
    MoneyDepositedEvent,
    MoneyTransferredEvent,
    MoneyWithdrawnEvent,
    publish_event,
)
from shared.middleware import SecurityMiddleware, setup_middleware
from shared.models import Account, AccountStatus, AuditLog, Transaction, TransactionStatus, User
from shared.monitoring import HealthChecker, MetricsCollector

apply_middleware(app)
setup_logging("core-banking")
app.include_router(metrics_router)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variables
db_manager: Optional[DatabaseManager] = None
redis_client: Optional[aioredis.Redis] = None
health_checker: Optional[HealthChecker] = None
metrics_collector: Optional[MetricsCollector] = None
settings: Settings = get_settings()

security = HTTPBearer()


def utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(timezone.utc)


class AccountType(str, Enum):
    """Account type enumeration."""

    CHECKING = "checking"
    SAVINGS = "savings"
    AGENT_WALLET = "agent_wallet"
    MERCHANT = "merchant"
    PLATFORM = "platform"
    FLOAT = "float"


class Currency(str, Enum):
    """Supported currencies."""

    NGN = "NGN"
    USD = "USD"
    GHS = "GHS"
    KES = "KES"
    ZAR = "ZAR"


# Pydantic Models
class AccountCreate(BaseModel):
    """Account creation request model."""

    user_id: str
    account_type: AccountType
    currency: Currency
    initial_balance: Decimal = Field(default=Decimal("0.00"), ge=0)
    daily_limit: Optional[Decimal] = Field(None, ge=0)
    metadata: Optional[Dict[str, Any]] = None

    @validator("initial_balance", "daily_limit")
    def validate_amounts(cls, v):
        if v is not None:
            return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return v


class AccountResponse(BaseModel):
    """Account response model."""

    id: str
    user_id: str
    account_number: str
    account_type: str
    currency: str
    balance: Decimal
    available_balance: Decimal
    status: str
    daily_limit: Optional[Decimal]
    created_at: datetime
    metadata: Dict[str, Any]

    class Config:
        from_attributes = True


class MoneyOperation(BaseModel):
    """Money operation request model."""

    amount: Decimal = Field(..., gt=0)
    description: Optional[str] = None
    reference: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    @validator("amount")
    def validate_amount(cls, v):
        return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class TransferRequest(BaseModel):
    """Money transfer request model."""

    from_account_id: str
    to_account_id: str
    amount: Decimal = Field(..., gt=0)
    description: Optional[str] = None
    reference: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    @validator("amount")
    def validate_amount(cls, v):
        return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class TransactionResponse(BaseModel):
    """Transaction response model."""

    id: str
    account_id: str
    transaction_type: str
    amount: Decimal
    balance_before: Decimal
    balance_after: Decimal
    description: Optional[str]
    reference: Optional[str]
    status: str
    created_at: datetime
    metadata: Dict[str, Any]

    class Config:
        from_attributes = True


class BalanceResponse(BaseModel):
    """Balance response model."""

    account_id: str
    balance: Decimal
    available_balance: Decimal
    currency: str
    last_updated: datetime


# Exceptions
class BankingException(Exception):
    """Base banking exception."""

    pass


class InsufficientFundsException(BankingException):
    """Insufficient funds exception."""

    pass


class AccountNotFoundException(BankingException):
    """Account not found exception."""

    pass


class AccountSuspendedException(BankingException):
    """Account suspended exception."""

    pass


class DuplicateTransactionException(BankingException):
    """Duplicate transaction exception."""

    pass


# Utility Functions
NUBAN_BANK_CODE = getattr(settings, "BANK_CODE", "999") or "999"


def _nuban_check_digit(bank_code: str, serial: str) -> str:
    """Compute the CBN NUBAN check digit for bank_code(3) + serial(9).

    Each of the 12 digits is multiplied by weights 3,7,3 repeating; the check
    digit is (10 - (sum % 10)) % 10.
    """
    digits = bank_code + serial
    weights = (3, 7, 3) * 4
    total = sum(int(d) * w for d, w in zip(digits, weights))
    return str((10 - (total % 10)) % 10)


def generate_account_number() -> str:
    """Generate a NUBAN-style 10-digit account number: 9-digit serial + check digit."""
    serial = f"{secrets.randbelow(10**9):09d}"
    return serial + _nuban_check_digit(NUBAN_BANK_CODE, serial)


def validate_account_number(account_number: str) -> bool:
    """Validate a NUBAN-style account number: 10 digits ending in a valid check digit."""
    if len(account_number) != 10 or not account_number.isdigit():
        return False
    return _nuban_check_digit(NUBAN_BANK_CODE, account_number[:9]) == account_number[9]


def generate_transaction_reference() -> str:
    """Generate unique transaction reference."""
    return f"TXN{utc_now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:8].upper()}"


async def get_account_by_id(db: AsyncSession, account_id: str) -> Account:
    """Get account by ID or raise exception."""
    stmt = select(Account).where(Account.id == account_id)
    result = await db.execute(stmt)
    account = result.scalar_one_or_none()

    if not account:
        raise AccountNotFoundException(f"Account {account_id} not found")

    if account.status == AccountStatus.SUSPENDED:
        raise AccountSuspendedException(f"Account {account_id} is suspended")

    return account


async def create_transaction_record(
    db: AsyncSession,
    account_id: str,
    transaction_type: str,
    amount: Decimal,
    balance_before: Decimal,
    balance_after: Decimal,
    description: Optional[str] = None,
    reference: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Transaction:
    """Create transaction record."""
    transaction = Transaction(
        id=str(uuid.uuid4()),
        account_id=account_id,
        transaction_type=transaction_type,
        amount=amount,
        balance_before=balance_before,
        balance_after=balance_after,
        description=description,
        reference=reference,
        status=TransactionStatus.COMPLETED,
        metadata=metadata or {},
        created_at=utc_now(),
    )

    db.add(transaction)
    return transaction


# Service Classes
class AccountService:
    """Account management service."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _generate_unique_account_number(self, max_attempts: int = 20) -> str:
        """Generate a NUBAN-style account number verified unique against the DB."""
        for _ in range(max_attempts):
            candidate = generate_account_number()
            stmt = select(Account.id).where(Account.account_number == candidate)
            result = await self.db.execute(stmt)
            if result.scalar_one_or_none() is None:
                return candidate
        raise BankingException(
            "unable to allocate a unique account number after "
            f"{max_attempts} attempts"
        )

    async def create_account(self, account_data: AccountCreate) -> Account:
        """Create new account."""
        account_number = await self._generate_unique_account_number()

        for attempt in range(3):
            account = Account(
                id=str(uuid.uuid4()),
                user_id=account_data.user_id,
                account_number=account_number,
                account_type=account_data.account_type.value,
                currency=account_data.currency.value,
                balance=account_data.initial_balance,
                available_balance=account_data.initial_balance,
                status=AccountStatus.ACTIVE,
                daily_limit=account_data.daily_limit,
                metadata=account_data.metadata or {},
                created_at=utc_now(),
                updated_at=utc_now(),
            )

            self.db.add(account)

            try:
                await self.db.commit()
                break
            except IntegrityError:
                # Account number collision — regenerate and retry; never collide silently.
                await self.db.rollback()
                account_number = await self._generate_unique_account_number()
                if attempt == 2:
                    raise BankingException(
                        "failed to allocate a unique account number"
                    )

        await self.db.refresh(account)

        # Publish account created event
        await publish_event(
            AccountCreatedEvent(
                account_id=account.id,
                user_id=account.user_id,
                account_number=account.account_number,
                account_type=account.account_type,
                currency=account.currency,
                initial_balance=account.initial_balance,
                timestamp=utc_now(),
            )
        )

        logger.info(f"Account created: {account.id} for user {account.user_id}")
        return account

    async def get_account(self, account_id: str) -> Account:
        """Get account by ID."""
        return await get_account_by_id(self.db, account_id)

    async def get_accounts_by_user(self, user_id: str) -> List[Account]:
        """Get all accounts for a user."""
        stmt = select(Account).where(Account.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def update_account_status(self, account_id: str, status: AccountStatus) -> Account:
        """Update account status."""
        account = await self.get_account(account_id)
        account.status = status
        account.updated_at = utc_now()

        await self.db.commit()
        await self.db.refresh(account)

        logger.info(f"Account status updated: {account_id} -> {status.value}")
        return account


class TransactionService:
    """Transaction processing service."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def deposit(self, account_id: str, operation: MoneyOperation) -> Transaction:
        """Deposit money into account."""
        # Check for duplicate transaction
        if operation.reference:
            stmt = select(Transaction).where(
                and_(
                    Transaction.account_id == account_id,
                    Transaction.reference == operation.reference,
                    Transaction.transaction_type == "deposit",
                )
            )
            result = await self.db.execute(stmt)
            if result.scalar_one_or_none():
                raise DuplicateTransactionException("Transaction with this reference already exists")

        account = await get_account_by_id(self.db, account_id)

        # Update balances
        balance_before = account.balance
        balance_after = balance_before + operation.amount

        account.balance = balance_after
        account.available_balance = balance_after
        account.updated_at = utc_now()

        # Create transaction record
        transaction = await create_transaction_record(
            self.db,
            account_id=account_id,
            transaction_type="deposit",
            amount=operation.amount,
            balance_before=balance_before,
            balance_after=balance_after,
            description=operation.description,
            reference=operation.reference,
            metadata=operation.metadata,
        )

        await self.db.commit()
        await self.db.refresh(transaction)

        # Publish deposit event
        await publish_event(
            MoneyDepositedEvent(
                transaction_id=transaction.id,
                account_id=account_id,
                amount=operation.amount,
                currency=account.currency,
                description=operation.description,
                reference=operation.reference,
                timestamp=utc_now(),
            )
        )

        logger.info(f"Deposit processed: {operation.amount} to account {account_id}")
        return transaction

    async def withdraw(self, account_id: str, operation: MoneyOperation) -> Transaction:
        """Withdraw money from account."""
        # Check for duplicate transaction
        if operation.reference:
            stmt = select(Transaction).where(
                and_(
                    Transaction.account_id == account_id,
                    Transaction.reference == operation.reference,
                    Transaction.transaction_type == "withdrawal",
                )
            )
            result = await self.db.execute(stmt)
            if result.scalar_one_or_none():
                raise DuplicateTransactionException("Transaction with this reference already exists")

        account = await get_account_by_id(self.db, account_id)

        # Check sufficient funds
        if account.available_balance < operation.amount:
            raise InsufficientFundsException(
                f"Insufficient funds. Available: {account.available_balance}, "
                f"Requested: {operation.amount}"
            )

        # Check daily limit
        if account.daily_limit:
            today = utc_now().date()
            stmt = select(func.sum(Transaction.amount)).where(
                and_(
                    Transaction.account_id == account_id,
                    Transaction.transaction_type == "withdrawal",
                    func.date(Transaction.created_at) == today,
                )
            )
            result = await self.db.execute(stmt)
            daily_withdrawals = result.scalar() or Decimal("0")

            if daily_withdrawals + operation.amount > account.daily_limit:
                raise BankingException(
                    f"Daily withdrawal limit exceeded. Limit: {account.daily_limit}, "
                    f"Used: {daily_withdrawals}, Requested: {operation.amount}"
                )

        # Update balances
        balance_before = account.balance
        balance_after = balance_before - operation.amount

        account.balance = balance_after
        account.available_balance = balance_after
        account.updated_at = utc_now()

        # Create transaction record
        transaction = await create_transaction_record(
            self.db,
            account_id=account_id,
            transaction_type="withdrawal",
            amount=operation.amount,
            balance_before=balance_before,
            balance_after=balance_after,
            description=operation.description,
            reference=operation.reference,
            metadata=operation.metadata,
        )

        await self.db.commit()
        await self.db.refresh(transaction)

        # Publish withdrawal event
        await publish_event(
            MoneyWithdrawnEvent(
                transaction_id=transaction.id,
                account_id=account_id,
                amount=operation.amount,
                currency=account.currency,
                description=operation.description,
                reference=operation.reference,
                timestamp=utc_now(),
            )
        )

        logger.info(f"Withdrawal processed: {operation.amount} from account {account_id}")
        return transaction

    async def transfer(self, transfer_data: TransferRequest) -> Transaction:
        """Transfer money between accounts."""
        # Check for duplicate transaction
        if transfer_data.reference:
            stmt = select(Transaction).where(
                and_(
                    Transaction.reference == transfer_data.reference,
                    Transaction.transaction_type == "transfer_out",
                )
            )
            result = await self.db.execute(stmt)
            if result.scalar_one_or_none():
                raise DuplicateTransactionException("Transaction with this reference already exists")

        # Get both accounts
        from_account = await get_account_by_id(self.db, transfer_data.from_account_id)
        to_account = await get_account_by_id(self.db, transfer_data.to_account_id)

        # Check currency compatibility
        if from_account.currency != to_account.currency:
            raise BankingException(
                f"Currency mismatch: {from_account.currency} != {to_account.currency}"
            )

        # Check sufficient funds
        if from_account.available_balance < transfer_data.amount:
            raise InsufficientFundsException(
                f"Insufficient funds. Available: {from_account.available_balance}, "
                f"Requested: {transfer_data.amount}"
            )

        # Update balances
        from_balance_before = from_account.balance
        from_balance_after = from_balance_before - transfer_data.amount
        from_account.balance = from_balance_after
        from_account.available_balance = from_balance_after

        to_balance_before = to_account.balance
        to_balance_after = to_balance_before + transfer_data.amount
        to_account.balance = to_balance_after
        to_account.available_balance = to_balance_after

        # Create transaction records (double-entry bookkeeping)
        transfer_reference = transfer_data.reference or generate_transaction_reference()

        # Debit transaction
        debit_transaction = await create_transaction_record(
            self.db,
            account_id=transfer_data.from_account_id,
            transaction_type="transfer_out",
            amount=transfer_data.amount,
            balance_before=from_balance_before,
            balance_after=from_balance_after,
            description=transfer_data.description,
            reference=transfer_reference,
            metadata={
                **(transfer_data.metadata or {}),
                "to_account_id": transfer_data.to_account_id,
                "transfer_reference": transfer_reference,
            },
        )

        # Credit transaction
        credit_transaction = await create_transaction_record(
            self.db,
            account_id=transfer_data.to_account_id,
            transaction_type="transfer_in",
            amount=transfer_data.amount,
            balance_before=to_balance_before,
            balance_after=to_balance_after,
            description=transfer_data.description,
            reference=transfer_reference,
            metadata={
                **(transfer_data.metadata or {}),
                "from_account_id": transfer_data.from_account_id,
                "transfer_reference": transfer_reference,
            },
        )

        await self.db.commit()
        await self.db.refresh(debit_transaction)
        await self.db.refresh(credit_transaction)

        # Publish transfer event
        await publish_event(
            MoneyTransferredEvent(
                transaction_id=debit_transaction.id,
                from_account_id=transfer_data.from_account_id,
                to_account_id=transfer_data.to_account_id,
                amount=transfer_data.amount,
                currency=from_account.currency,
                description=transfer_data.description,
                reference=transfer_reference,
                timestamp=utc_now(),
            )
        )

        logger.info(
            f"Transfer processed: {transfer_data.amount} from "
            f"{transfer_data.from_account_id} to {transfer_data.to_account_id}"
        )
        return debit_transaction

    async def get_transaction_history(
        self,
        account_id: str,
        limit: int = 50,
        offset: int = 0,
        transaction_type: Optional[str] = None,
    ) -> List[Transaction]:
        """Get transaction history for account."""
        await get_account_by_id(self.db, account_id)  # Verify account exists

        stmt = (
            select(Transaction)
            .where(Transaction.account_id == account_id)
            .order_by(Transaction.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        if transaction_type:
            stmt = stmt.where(Transaction.transaction_type == transaction_type)

        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_balance(self, account_id: str) -> BalanceResponse:
        """Get account balance."""
        account = await get_account_by_id(self.db, account_id)

        return BalanceResponse(
            account_id=account_id,
            balance=account.balance,
            available_balance=account.available_balance,
            currency=account.currency,
            last_updated=account.updated_at,
        )


# Application lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global db_manager, redis_client, health_checker, metrics_collector

    # Startup
    logger.info("Starting Core Banking Service...")

    # Initialize database
    db_manager = DatabaseManager()
    await db_manager.initialize()

    # Initialize Redis
    redis_client = aioredis.from_url(settings.redis_url)

    # Initialize health checker and metrics
    health_checker = HealthChecker()
    metrics_collector = MetricsCollector()

    logger.info("Core Banking Service started successfully")

    yield

    # Shutdown
    logger.info("Shutting down Core Banking Service...")

    if db_manager:
        await db_manager.close()
    if redis_client:
        await redis_client.close()

    logger.info("Core Banking Service shut down successfully")


# Create FastAPI app
app = FastAPI(
    title="Core Banking Service",
    description="Account management and transaction processing for remittance platform",
    version="1.0.0",
    lifespan=lifespan,
)

# Add middleware
setup_middleware(app)
app.add_middleware(SecurityMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(AccountNotFoundException)
async def account_not_found_handler(request: Request, exc: AccountNotFoundException):
    """Handle account not found exception."""
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@app.exception_handler(InsufficientFundsException)
async def insufficient_funds_handler(request: Request, exc: InsufficientFundsException):
    """Handle insufficient funds exception."""
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@app.exception_handler(DuplicateTransactionException)
async def duplicate_transaction_handler(request: Request, exc: DuplicateTransactionException):
    """Handle duplicate transaction exception."""
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


# Dependency injection
def get_account_service(db: AsyncSession = Depends(get_db)) -> AccountService:
    """Get account service."""
    return AccountService(db)


def get_transaction_service(db: AsyncSession = Depends(get_db)) -> TransactionService:
    """Get transaction service."""
    return TransactionService(db)


# API Routes
@app.post("/accounts", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account(
    account_data: AccountCreate,
    service: AccountService = Depends(get_account_service),
) -> Account:
    """Create a new account."""
    return await service.create_account(account_data)


@app.get("/accounts/{account_id}", response_model=AccountResponse)
async def get_account(
    account_id: str,
    service: AccountService = Depends(get_account_service),
) -> Account:
    """Get account by ID."""
    return await service.get_account(account_id)


@app.get("/users/{user_id}/accounts", response_model=List[AccountResponse])
async def get_user_accounts(
    user_id: str,
    service: AccountService = Depends(get_account_service),
) -> List[Account]:
    """Get all accounts for a user."""
    return await service.get_accounts_by_user(user_id)


@app.put("/accounts/{account_id}/status")
async def update_account_status(
    account_id: str,
    status: AccountStatus,
    service: AccountService = Depends(get_account_service),
) -> Dict[str, str]:
    """Update account status."""
    account = await service.update_account_status(account_id, status)
    return {"message": f"Account status updated to {status.value}"}


@app.post("/accounts/{account_id}/deposit", response_model=TransactionResponse)
async def deposit_money(
    account_id: str,
    operation: MoneyOperation,
    service: TransactionService = Depends(get_transaction_service),
) -> Transaction:
    """Deposit money into account."""
    return await service.deposit(account_id, operation)


@app.post("/accounts/{account_id}/withdraw", response_model=TransactionResponse)
async def withdraw_money(
    account_id: str,
    operation: MoneyOperation,
    service: TransactionService = Depends(get_transaction_service),
) -> Transaction:
    """Withdraw money from account."""
    return await service.withdraw(account_id, operation)


@app.post("/transfers", response_model=TransactionResponse)
async def transfer_money(
    transfer_data: TransferRequest,
    service: TransactionService = Depends(get_transaction_service),
) -> Transaction:
    """Transfer money between accounts."""
    return await service.transfer(transfer_data)


@app.get("/accounts/{account_id}/balance", response_model=BalanceResponse)
async def get_account_balance(
    account_id: str,
    service: TransactionService = Depends(get_transaction_service),
) -> BalanceResponse:
    """Get account balance."""
    return await service.get_balance(account_id)


@app.get("/accounts/{account_id}/transactions", response_model=List[TransactionResponse])
async def get_transaction_history(
    account_id: str,
    limit: int = 50,
    offset: int = 0,
    transaction_type: Optional[str] = None,
    service: TransactionService = Depends(get_transaction_service),
) -> List[Transaction]:
    """Get transaction history for account."""
    return await service.get_transaction_history(account_id, limit, offset, transaction_type)


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint."""
    if health_checker:
        return await health_checker.check_health()
    return {"status": "healthy", "timestamp": utc_now().isoformat()}


@app.get("/metrics")
async def get_metrics() -> Dict[str, Any]:
    """Metrics endpoint."""
    if metrics_collector:
        return await metrics_collector.get_metrics()
    return {"metrics": "not_available"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
