from typing import List
from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from service import (
    StablecoinService, AccountService, TransactionService,
    NotFoundException, IntegrityViolationException, InsufficientBalanceException, AccountLockedException
)
from schemas import (
    Stablecoin, StablecoinCreate, StablecoinUpdate,
    Account, AccountCreate, AccountUpdate,
    Transaction, TransactionCreate, TransactionUpdate,
    HTTPError
)

# Production implementation for a real authentication dependency
def get_current_user_id() -> int:
    """
    Placeholder dependency for user authentication.
    In a real application, this would decode a JWT or similar token.
    For now, it returns a dummy user ID.
    """
    # Simulate a successful authentication
    return 1

# --- Stablecoin Router ---
stablecoin_router = APIRouter(
    prefix="/stablecoins",
    tags=["Stablecoins"],
    dependencies=[Depends(get_current_user_id)],
    responses={404: {"model": HTTPError}, 409: {"model": HTTPError}}
)

@stablecoin_router.post(
    "/",
    response_model=Stablecoin,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new stablecoin entry",
    description="Registers a new stablecoin in the system for use in accounts and transactions."
)
def create_stablecoin(
    stablecoin_in: StablecoinCreate,
    db: Session = Depends(get_db)
) -> None:
    try:
        return StablecoinService(db).create_stablecoin(stablecoin_in)
    except IntegrityViolationException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

@stablecoin_router.get(
    "/{stablecoin_id}",
    response_model=Stablecoin,
    summary="Get a stablecoin by ID",
)
def read_stablecoin(
    stablecoin_id: int,
    db: Session = Depends(get_db)
) -> None:
    try:
        return StablecoinService(db).get_stablecoin(stablecoin_id)
    except NotFoundException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

@stablecoin_router.get(
    "/",
    response_model=List[Stablecoin],
    summary="List all stablecoins",
)
def list_stablecoins(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
) -> None:
    return StablecoinService(db).get_all_stablecoins(skip=skip, limit=limit)

@stablecoin_router.put(
    "/{stablecoin_id}",
    response_model=Stablecoin,
    summary="Update a stablecoin's details",
)
def update_stablecoin(
    stablecoin_id: int,
    stablecoin_in: StablecoinUpdate,
    db: Session = Depends(get_db)
) -> None:
    try:
        return StablecoinService(db).update_stablecoin(stablecoin_id, stablecoin_in)
    except NotFoundException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

@stablecoin_router.delete(
    "/{stablecoin_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a stablecoin",
)
def delete_stablecoin(
    stablecoin_id: int,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    try:
        StablecoinService(db).delete_stablecoin(stablecoin_id)
        return {"ok": True}
    except NotFoundException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

# --- Account Router ---
account_router = APIRouter(
    prefix="/accounts",
    tags=["Accounts"],
    dependencies=[Depends(get_current_user_id)],
    responses={404: {"model": HTTPError}, 409: {"model": HTTPError}, 403: {"model": HTTPError}}
)

@account_router.post(
    "/",
    response_model=Account,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new stablecoin account",
    description="Creates a new account for a user and a specific stablecoin."
)
def create_account(
    account_in: AccountCreate,
    db: Session = Depends(get_db)
) -> None:
    try:
        return AccountService(db).create_account(account_in)
    except (IntegrityViolationException, NotFoundException) as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

@account_router.get(
    "/{account_id}",
    response_model=Account,
    summary="Get an account by ID",
)
def read_account(
    account_id: int,
    db: Session = Depends(get_db)
) -> None:
    try:
        return AccountService(db).get_account(account_id)
    except NotFoundException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

@account_router.get(
    "/",
    response_model=List[Account],
    summary="List all accounts (or filter by user_id)",
)
def list_accounts(
    user_id: int = Depends(get_current_user_id), # Filter by current user by default
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
) -> None:
    return AccountService(db).get_accounts_by_user(user_id=user_id, skip=skip, limit=limit)

@account_router.patch(
    "/{account_id}",
    response_model=Account,
    summary="Update an account's details (e.g., lock status)",
)
def update_account(
    account_id: int,
    account_in: AccountUpdate,
    db: Session = Depends(get_db)
) -> None:
    try:
        return AccountService(db).update_account(account_id, account_in)
    except NotFoundException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

@account_router.delete(
    "/{account_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an account",
)
def delete_account(
    account_id: int,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    try:
        AccountService(db).delete_account(account_id)
        return {"ok": True}
    except NotFoundException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

# --- Transaction Router ---
transaction_router = APIRouter(
    prefix="/transactions",
    tags=["Transactions"],
    dependencies=[Depends(get_current_user_id)],
    responses={
        404: {"model": HTTPError},
        400: {"model": HTTPError},
        403: {"model": HTTPError},
        500: {"model": HTTPError}
    }
)

@transaction_router.post(
    "/",
    response_model=Transaction,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new transaction (Deposit, Withdrawal, Transfer)",
    description="Initiates a new stablecoin transaction. Note: For simplicity, this API assumes instant completion for balance updates."
)
def create_transaction(
    transaction_in: TransactionCreate,
    db: Session = Depends(get_db)
) -> None:
    try:
        return TransactionService(db).create_transaction(transaction_in)
    except (NotFoundException, InsufficientBalanceException, AccountLockedException) as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except HTTPException as e: # Catch ServiceException which is a subclass of HTTPException
        raise e

@transaction_router.get(
    "/{transaction_id}",
    response_model=Transaction,
    summary="Get a transaction by ID",
)
def read_transaction(
    transaction_id: int,
    db: Session = Depends(get_db)
) -> None:
    try:
        return TransactionService(db).get_transaction(transaction_id)
    except NotFoundException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

@transaction_router.get(
    "/account/{account_id}",
    response_model=List[Transaction],
    summary="List transactions for a specific account",
)
def list_transactions_by_account(
    account_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
) -> None:
    return TransactionService(db).get_transactions_by_account(account_id=account_id, skip=skip, limit=limit)

@transaction_router.patch(
    "/{transaction_id}",
    response_model=Transaction,
    summary="Update a transaction's status (e.g., from PENDING to COMPLETED)",
    description="This endpoint is typically used by a background worker or webhook to update the final status of an off-chain or blockchain transaction."
)
def update_transaction_status(
    transaction_id: int,
    transaction_in: TransactionUpdate,
    db: Session = Depends(get_db)
) -> None:
    try:
        return TransactionService(db).update_transaction_status(transaction_id, transaction_in)
    except NotFoundException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)