import uuid
from typing import List, Optional
from datetime import timedelta, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import ValidationError
from sqlalchemy.orm import Session

from database import get_db
from service import (
    get_user, get_user_by_username, create_user,
    get_stablecoin, get_stablecoins, create_stablecoin, update_stablecoin,
    get_user_accounts, create_account, update_account_rates,
    get_transactions_by_account, process_transaction,
    authenticate_user, get_current_active_user,
    ServiceException, NotFoundException, ConflictException, ForbiddenException, BadRequestException
)
from schemas import (
    User, UserCreate, UserUpdate, Stablecoin, StablecoinCreate, StablecoinUpdate,
    Account, AccountCreate, AccountUpdate, Transaction, TransactionCreate,
    Token, TokenData
)
from config import settings

# --- Security Setup ---

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> None:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

async def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except (JWTError, ValidationError):
        raise credentials_exception
    
    user = get_user_by_username(db, username=token_data.username)
    if user is None:
        raise credentials_exception
    
    # Use the service layer function to check for active status
    try:
        return get_current_active_user(db, user.id)
    except ForbiddenException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

# --- Routers ---

router = APIRouter(prefix="/api/v1", tags=["v1"])

# --- Authentication Endpoints ---

@router.post("/auth/register", response_model=User, status_code=status.HTTP_201_CREATED, summary="Register a new user")
def register_user(user: UserCreate, db: Session = Depends(get_db)) -> None:
    try:
        return create_user(db, user)
    except ConflictException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

@router.post("/auth/token", response_model=Token, summary="Get access token for authentication")
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)) -> Dict[str, Any]:
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/auth/me", response_model=User, summary="Get current authenticated user details")
def read_users_me(current_user: User = Depends(get_current_user)) -> None:
    return current_user

# --- Stablecoin Endpoints (Admin/Public Read) ---

@router.get("/stablecoins", response_model=List[Stablecoin], summary="List all stablecoins")
def list_stablecoins(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)) -> None:
    return get_stablecoins(db, skip=skip, limit=limit)

@router.get("/stablecoins/{stablecoin_id}", response_model=Stablecoin, summary="Get a stablecoin by ID")
def read_stablecoin(stablecoin_id: int, db: Session = Depends(get_db)) -> None:
    db_stablecoin = get_stablecoin(db, stablecoin_id)
    if db_stablecoin is None:
        raise HTTPException(status_code=404, detail="Stablecoin not found")
    return db_stablecoin

@router.post("/stablecoins", response_model=Stablecoin, status_code=status.HTTP_201_CREATED, summary="Create a new stablecoin (Admin only)")
def create_new_stablecoin(stablecoin: StablecoinCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> None:
    # NOTE: In a real app, we would check if the user is an admin. For this task, we just ensure they are authenticated.
    try:
        return create_stablecoin(db, stablecoin)
    except ConflictException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

@router.put("/stablecoins/{stablecoin_id}", response_model=Stablecoin, summary="Update an existing stablecoin (Admin only)")
def update_existing_stablecoin(stablecoin_id: int, stablecoin_in: StablecoinUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> None:
    # NOTE: In a real app, we would check if the user is an admin.
    try:
        return update_stablecoin(db, stablecoin_id, stablecoin_in)
    except NotFoundException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except ConflictException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

# --- Account Endpoints ---

@router.get("/accounts", response_model=List[Account], summary="List all accounts for the current user")
def list_user_accounts(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> None:
    return get_user_accounts(db, current_user.id, skip=skip, limit=limit)

@router.post("/accounts", response_model=Account, status_code=status.HTTP_201_CREATED, summary="Create a new stablecoin account for the current user")
def create_user_account(account: AccountCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> None:
    try:
        return create_account(db, current_user.id, account)
    except (NotFoundException, ConflictException) as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

@router.put("/accounts/{account_id}/rates", response_model=Account, summary="Update deposit/borrow rates for an account (Admin only)")
def update_account_deposit_borrow_rates(account_id: uuid.UUID, account_in: AccountUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> None:
    # NOTE: This is an admin-level function to simulate rate changes in the DeFi protocol.
    try:
        return update_account_rates(db, account_id, account_in)
    except (NotFoundException, BadRequestException) as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

# --- Transaction Endpoints ---

@router.get("/accounts/{account_id}/transactions", response_model=List[Transaction], summary="List transactions for a specific account")
def list_account_transactions(account_id: uuid.UUID, skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> None:
    # Authorization check: Ensure the account belongs to the current user
    db_account = get_account(db, account_id)
    if not db_account or db_account.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Account not found or access denied")
    
    return get_transactions_by_account(db, account_id, skip=skip, limit=limit)

@router.post("/accounts/{account_id}/transactions", response_model=Transaction, status_code=status.HTTP_201_CREATED, summary="Process a new deposit, withdraw, borrow, or repay transaction")
def create_new_transaction(account_id: uuid.UUID, transaction_in: TransactionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> None:
    # Authorization check: Ensure the account belongs to the current user
    db_account = get_account(db, account_id)
    if not db_account or db_account.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Account not found or access denied")
    
    try:
        return process_transaction(db, account_id, transaction_in)
    except (NotFoundException, BadRequestException) as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)