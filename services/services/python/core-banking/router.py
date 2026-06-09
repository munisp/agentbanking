import uuid
from typing import List, Annotated
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status, Body, Form
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from database import DBSession
from schemas import (
    UserCreate,
    UserInDB,
    CustomerCreate,
    CustomerUpdate,
    CustomerInDB,
    AccountCreate,
    AccountUpdate,
    AccountInDB,
    TransactionCreate,
    TransactionInDB,
    Token,
    AccountWithTransactions,
    CustomerWithAccounts,
)
from service import (
    UserService,
    CustomerService,
    AccountService,
    TransactionService,
    ServiceException,
    NotFoundException,
    ConflictException,
    InsufficientFundsException,
    InvalidTransactionException,
    AuthenticationException,
    create_access_token,
)
from models import User
from config import settings

# --- Router Setup ---
router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# --- Dependency Functions ---

async def get_user_service(db: Annotated[AsyncSession, Depends(DBSession)]) -> UserService:
    return UserService(db)

async def get_customer_service(db: Annotated[AsyncSession, Depends(DBSession)]) -> CustomerService:
    return CustomerService(db)

async def get_account_service(db: Annotated[AsyncSession, Depends(DBSession)]) -> AccountService:
    return AccountService(db)

async def get_transaction_service(db: Annotated[AsyncSession, Depends(DBSession)]) -> TransactionService:
    return TransactionService(db)

async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> User:
    try:
        user = await user_service.get_current_user(token)
        return user
    except AuthenticationException as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.message,
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_active_user(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    return current_user

# --- Error Handling Utility ---

def handle_service_exception(e: ServiceException):
    """Converts a ServiceException into an HTTPException."""
    raise HTTPException(status_code=e.status_code, detail=e.message)

# --- Authentication Endpoints ---

@router.post("/token", response_model=Token, tags=["Auth"])
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    user_service: Annotated[UserService, Depends(get_user_service)],
):
    """Authenticate user and return an access token."""
    user = await user_service.authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"user_id": user.id}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer", "expires_at": (datetime.utcnow() + access_token_expires)}

@router.post("/users", response_model=UserInDB, status_code=status.HTTP_201_CREATED, tags=["Users"])
async def create_user_endpoint(
    user_in: UserCreate,
    user_service: Annotated[UserService, Depends(get_user_service)],
):
    """Register a new user."""
    try:
        return await user_service.create_user(user_in)
    except ConflictException as e:
        handle_service_exception(e)

@router.get("/users/me", response_model=UserInDB, tags=["Users"])
async def read_users_me(
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """Get the current authenticated user's details."""
    return current_user

# --- Customer Endpoints ---

@router.post("/customers", response_model=CustomerInDB, status_code=status.HTTP_201_CREATED, tags=["Customers"])
async def create_customer_endpoint(
    customer_in: CustomerCreate,
    customer_service: Annotated[CustomerService, Depends(get_customer_service)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Create a new customer profile. Requires authentication."""
    if customer_in.user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot create customer for another user.")
    try:
        return await customer_service.create_customer(customer_in)
    except ConflictException as e:
        handle_service_exception(e)
    except NotFoundException as e:
        handle_service_exception(e)

@router.get("/customers/{customer_id}", response_model=CustomerInDB, tags=["Customers"])
async def read_customer_endpoint(
    customer_id: uuid.UUID,
    customer_service: Annotated[CustomerService, Depends(get_customer_service)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Get a customer's details by ID. User must own the customer profile or be a superuser."""
    try:
        customer = await customer_service.get_customer(customer_id)
        if customer.user_id != current_user.id and not current_user.is_superuser:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this customer.")
        return customer
    except NotFoundException as e:
        handle_service_exception(e)

@router.put("/customers/{customer_id}", response_model=CustomerInDB, tags=["Customers"])
async def update_customer_endpoint(
    customer_id: uuid.UUID,
    customer_in: CustomerUpdate,
    customer_service: Annotated[CustomerService, Depends(get_customer_service)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Update a customer's details by ID. User must own the customer profile or be a superuser."""
    try:
        customer = await customer_service.get_customer(customer_id)
        if customer.user_id != current_user.id and not current_user.is_superuser:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to update this customer.")
        return await customer_service.update_customer(customer_id, customer_in)
    except (NotFoundException, ConflictException) as e:
        handle_service_exception(e)

@router.delete("/customers/{customer_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Customers"])
async def delete_customer_endpoint(
    customer_id: uuid.UUID,
    customer_service: Annotated[CustomerService, Depends(get_customer_service)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Delete a customer profile by ID. Only superusers can delete customers."""
    if not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only superusers can delete customers.")
    try:
        await customer_service.delete_customer(customer_id)
    except NotFoundException as e:
        handle_service_exception(e)

# --- Account Endpoints ---

@router.post("/accounts", response_model=AccountInDB, status_code=status.HTTP_201_CREATED, tags=["Accounts"])
async def create_account_endpoint(
    account_in: AccountCreate,
    account_service: Annotated[AccountService, Depends(get_account_service)],
    customer_service: Annotated[CustomerService, Depends(get_customer_service)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Create a new bank account for a customer. User must own the customer profile or be a superuser."""
    try:
        customer = await customer_service.get_customer(account_in.customer_id)
        if customer.user_id != current_user.id and not current_user.is_superuser:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to create account for this customer.")
        return await account_service.create_account(account_in)
    except (NotFoundException, ConflictException) as e:
        handle_service_exception(e)

@router.get("/accounts/{account_id}", response_model=AccountInDB, tags=["Accounts"])
async def read_account_endpoint(
    account_id: uuid.UUID,
    account_service: Annotated[AccountService, Depends(get_account_service)],
    customer_service: Annotated[CustomerService, Depends(get_customer_service)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Get account details by ID. User must own the account's customer profile or be a superuser."""
    try:
        account = await account_service.get_account(account_id)
        customer = await customer_service.get_customer(account.customer_id)
        if customer.user_id != current_user.id and not current_user.is_superuser:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this account.")
        return account
    except NotFoundException as e:
        handle_service_exception(e)

@router.get("/customers/{customer_id}/accounts", response_model=List[AccountInDB], tags=["Accounts"])
async def list_customer_accounts_endpoint(
    customer_id: uuid.UUID,
    account_service: Annotated[AccountService, Depends(get_account_service)],
    customer_service: Annotated[CustomerService, Depends(get_customer_service)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """List all accounts for a customer. User must own the customer profile or be a superuser."""
    try:
        customer = await customer_service.get_customer(customer_id)
        if customer.user_id != current_user.id and not current_user.is_superuser:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view accounts for this customer.")
        return await account_service.get_accounts_by_customer(customer_id)
    except NotFoundException as e:
        handle_service_exception(e)

# --- Transaction Endpoints ---

@router.post("/transactions/deposit", response_model=TransactionInDB, status_code=status.HTTP_201_CREATED, tags=["Transactions"])
async def deposit_funds_endpoint(
    account_id: Annotated[uuid.UUID, Body(embed=True)],
    amount: Annotated[float, Body(embed=True, gt=0)],
    description: Annotated[str, Body(embed=True, default=None)],
    transaction_service: Annotated[TransactionService, Depends(get_transaction_service)],
    account_service: Annotated[AccountService, Depends(get_account_service)],
    customer_service: Annotated[CustomerService, Depends(get_customer_service)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Deposit funds into an account."""
    try:
        account = await account_service.get_account(account_id)
        customer = await customer_service.get_customer(account.customer_id)
        if customer.user_id != current_user.id and not current_user.is_superuser:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to deposit to this account.")

        transaction_in = TransactionCreate(
            account_id=account_id,
            amount=amount,
            description=description,
            transaction_type="DEPOSIT"
        )
        return await transaction_service.create_transaction(transaction_in)
    except (NotFoundException, InvalidTransactionException) as e:
        handle_service_exception(e)

@router.post("/transactions/withdrawal", response_model=TransactionInDB, status_code=status.HTTP_201_CREATED, tags=["Transactions"])
async def withdraw_funds_endpoint(
    account_id: Annotated[uuid.UUID, Body(embed=True)],
    amount: Annotated[float, Body(embed=True, gt=0)],
    description: Annotated[str, Body(embed=True, default=None)],
    transaction_service: Annotated[TransactionService, Depends(get_transaction_service)],
    account_service: Annotated[AccountService, Depends(get_account_service)],
    customer_service: Annotated[CustomerService, Depends(get_customer_service)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Withdraw funds from an account."""
    try:
        account = await account_service.get_account(account_id)
        customer = await customer_service.get_customer(account.customer_id)
        if customer.user_id != current_user.id and not current_user.is_superuser:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to withdraw from this account.")

        transaction_in = TransactionCreate(
            account_id=account_id,
            amount=amount,
            description=description,
            transaction_type="WITHDRAWAL"
        )
        return await transaction_service.create_transaction(transaction_in)
    except (NotFoundException, InvalidTransactionException, InsufficientFundsException) as e:
        handle_service_exception(e)

class TransferRequest(BaseModel):
    source_account_id: uuid.UUID
    target_account_id: uuid.UUID
    amount: float = Field(..., gt=0)
    description: Optional[str] = None

@router.post("/transactions/transfer", response_model=List[TransactionInDB], status_code=status.HTTP_201_CREATED, tags=["Transactions"])
async def transfer_funds_endpoint(
    transfer_request: TransferRequest,
    transaction_service: Annotated[TransactionService, Depends(get_transaction_service)],
    account_service: Annotated[AccountService, Depends(get_account_service)],
    customer_service: Annotated[CustomerService, Depends(get_customer_service)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Transfer funds between two accounts."""
    try:
        # Authorization check: User must own the source account
        source_account = await account_service.get_account(transfer_request.source_account_id)
        customer = await customer_service.get_customer(source_account.customer_id)
        if customer.user_id != current_user.id and not current_user.is_superuser:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to transfer from the source account.")

        source_tx, target_tx = await transaction_service.transfer_funds(
            source_account_id=transfer_request.source_account_id,
            target_account_id=transfer_request.target_account_id,
            amount=transfer_request.amount,
            description=transfer_request.description
        )
        return [source_tx, target_tx]
    except (NotFoundException, InvalidTransactionException, InsufficientFundsException) as e:
        handle_service_exception(e)

@router.get("/accounts/{account_id}/transactions", response_model=List[TransactionInDB], tags=["Transactions"])
async def list_account_transactions_endpoint(
    account_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
    transaction_service: Annotated[TransactionService, Depends(get_transaction_service)],
    account_service: Annotated[AccountService, Depends(get_account_service)],
    customer_service: Annotated[CustomerService, Depends(get_customer_service)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """List all transactions for a specific account. User must own the account or be a superuser."""
    try:
        # Authorization check
        account = await account_service.get_account(account_id)
        customer = await customer_service.get_customer(account.customer_id)
        if customer.user_id != current_user.id and not current_user.is_superuser:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view transactions for this account.")

        return await transaction_service.get_transactions_by_account(account_id, skip, limit)
    except NotFoundException as e:
        handle_service_exception(e)