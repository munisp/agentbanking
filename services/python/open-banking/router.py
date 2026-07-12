from typing import List, Optional
from fastapi import APIRouter, Depends, status, HTTPException
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
import jwt  # Migrated from python-jose (CVE-2024-33663) to PyJWT
from jwt.exceptions import InvalidTokenError as JWTError
from datetime import timedelta, datetime
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal

from database import get_db
from service import OpenBankingService, security_service, NotFoundException, UnauthorizedException, ConflictException, ForbiddenException
from schemas import (
    UserCreate, UserResponse, Token, TokenData,
    AccountCreate, AccountResponse, AccountUpdate, AccountListResponse,
    TransactionResponse, TransactionListResponse, BalanceResponse
)
from models import User, CreditDebitIndicator
from config import settings

# --- Constants for JWT ---
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# --- Security Dependency ---
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> None:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(
    db: AsyncSession = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> User:
    credentials_exception = UnauthorizedException()
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
    except JWTError:
        raise credentials_exception

    service = OpenBankingService(db)
    user = await service.get_user_by_email(email=token_data.email)
    if user is None:
        raise credentials_exception
    return user

# --- Routers ---

router = APIRouter(prefix="/api/v1", tags=["Open Banking API"])

# --- Authentication Endpoints ---

@router.post("/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_in: UserCreate, service: OpenBankingService = Depends(OpenBankingService)
) -> None:
    """Register a new user."""
    return await service.create_user(user_in)

@router.post("/auth/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    service: OpenBankingService = Depends(OpenBankingService)
) -> Dict[str, Any]:
    """Obtain an access token by providing username (email) and password."""
    user = await service.get_user_by_email(form_data.username)
    if not user or not security_service.verify_password(form_data.password, user.hashed_password):
        raise UnauthorizedException(detail="Incorrect username or password")
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/users/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)) -> None:
    """Get the current authenticated user's details."""
    return current_user

# --- Account Endpoints ---

@router.post("/accounts", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account_for_user(
    account_in: AccountCreate,
    current_user: User = Depends(get_current_user),
    service: OpenBankingService = Depends(OpenBankingService)
) -> None:
    """Create a new bank account for the authenticated user."""
    return await service.create_account(current_user.id, account_in)

@router.get("/accounts", response_model=AccountListResponse)
async def list_accounts_for_user(
    current_user: User = Depends(get_current_user),
    service: OpenBankingService = Depends(OpenBankingService)
) -> Dict[str, Any]:
    """List all bank accounts belonging to the authenticated user."""
    accounts = await service.get_accounts_for_user(current_user.id)
    return {"accounts": accounts}

@router.get("/accounts/{account_id}", response_model=AccountResponse)
async def get_account_details(
    account_id: str,
    current_user: User = Depends(get_current_user),
    service: OpenBankingService = Depends(OpenBankingService)
) -> None:
    """Get details for a specific account."""
    account = await service.get_account_by_id(account_id)
    if account.owner_id != current_user.id:
        raise ForbiddenException()
    return account

@router.patch("/accounts/{account_id}", response_model=AccountResponse)
async def update_account_details(
    account_id: str,
    account_in: AccountUpdate,
    current_user: User = Depends(get_current_user),
    service: OpenBankingService = Depends(OpenBankingService)
) -> None:
    """Update a specific account's details (e.g., nickname, status)."""
    account = await service.get_account_by_id(account_id)
    if account.owner_id != current_user.id:
        raise ForbiddenException()
    return await service.update_account(account_id, account_in)

@router.delete("/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    account_id: str,
    current_user: User = Depends(get_current_user),
    service: OpenBankingService = Depends(OpenBankingService)
) -> None:
    """Delete a specific account and all associated data."""
    account = await service.get_account_by_id(account_id)
    if account.owner_id != current_user.id:
        raise ForbiddenException()
    await service.delete_account(account_id)
    return

# --- Transaction Endpoints ---

@router.post("/accounts/{account_id}/transactions", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
async def create_transaction(
    account_id: str,
    amount: Decimal,
    indicator: CreditDebitIndicator,
    reference: Optional[str] = None,
    information: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    service: OpenBankingService = Depends(OpenBankingService)
) -> None:
    """
    Create a new transaction (e.g., deposit or withdrawal) on an account.
    Note: In a real Open Banking API, this would typically be a Payment Initiation endpoint.
    This simplified version demonstrates the ledger update logic.
    """
    account = await service.get_account_by_id(account_id)
    if account.owner_id != current_user.id:
        raise ForbiddenException()
    
    if amount <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Amount must be positive.")

    return await service.create_transaction(
        account_id=account_id,
        amount=amount,
        indicator=indicator,
        reference=reference,
        information=information
    )

@router.get("/accounts/{account_id}/transactions", response_model=TransactionListResponse)
async def list_transactions(
    account_id: str,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    service: OpenBankingService = Depends(OpenBankingService)
) -> Dict[str, Any]:
    """List transactions for a specific account."""
    account = await service.get_account_by_id(account_id)
    if account.owner_id != current_user.id:
        raise ForbiddenException()
        
    transactions = await service.get_transactions_for_account(account_id, limit)
    return {"transactions": transactions}

# --- Balance Endpoints ---

@router.get("/accounts/{account_id}/balances", response_model=List[BalanceResponse])
async def list_balances(
    account_id: str,
    current_user: User = Depends(get_current_user),
    service: OpenBankingService = Depends(OpenBankingService)
) -> None:
    """List all balance records for a specific account."""
    account = await service.get_account_by_id(account_id)
    if account.owner_id != current_user.id:
        raise ForbiddenException()
        
    return await service.get_balances_for_account(account_id)