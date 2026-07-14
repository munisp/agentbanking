from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

import schemas
import service
from database import get_db
from service import AccountService, AccountNotFound, CurrencyBalanceNotFound, CurrencyBalanceAlreadyExists, ServiceError

router = APIRouter(
    tags=["Multi-Currency Accounts"],
    responses={404: {"description": "Not found"}},
)

# --- Dependency Placeholder ---
# In a real application, this would be a function to get the current authenticated user
# For this task, we will assume a user_id is passed in the request body for creation/listing
# and that all other operations are authorized.
def get_current_user_id() -> int:
    """Placeholder for authentication dependency."""
    # In a real app, this would extract user ID from a JWT token or session
    # For now, we'll return a default ID or raise an HTTPException if not authenticated
    return 1 # Default user ID for demonstration

# --- Account Endpoints ---

@router.post(
    "/accounts", 
    response_model=schemas.Account, 
    status_code=status.HTTP_201_CREATED,
    summary="Create a new multi-currency account"
)
def create_account_endpoint(
    account_data: schemas.AccountCreate, 
    db: Session = Depends(get_db)
) -> None:
    """
    Creates a new account for a user, optionally with initial currency balances.
    """
    try:
        account_service = AccountService(db)
        return account_service.create_account(account_data)
    except ServiceError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get(
    "/accounts", 
    response_model=List[schemas.Account],
    summary="List all accounts (or filter by user)"
)
def list_accounts_endpoint(
    user_id: Optional[int] = None,
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
) -> None:
    """
    Retrieves a list of all accounts in the system. Can be filtered by user_id.
    """
    account_service = AccountService(db)
    return account_service.get_all_accounts(user_id=user_id, skip=skip, limit=limit)

@router.get(
    "/accounts/{account_id}", 
    response_model=schemas.Account,
    summary="Get a specific account by ID"
)
def get_account_endpoint(
    account_id: int, 
    db: Session = Depends(get_db)
) -> None:
    """
    Retrieves the details of a single account, including all its currency balances.
    """
    try:
        account_service = AccountService(db)
        return account_service.get_account(account_id)
    except AccountNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@router.put(
    "/accounts/{account_id}", 
    response_model=schemas.Account,
    summary="Update an existing account"
)
def update_account_endpoint(
    account_id: int, 
    account_data: schemas.AccountUpdate, 
    db: Session = Depends(get_db)
) -> None:
    """
    Updates the name or other details of an existing account.
    """
    try:
        account_service = AccountService(db)
        return account_service.update_account(account_id, account_data)
    except AccountNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ServiceError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.delete(
    "/accounts/{account_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an account"
)
def delete_account_endpoint(
    account_id: int, 
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Deletes an account and all its associated currency balances.
    """
    try:
        account_service = AccountService(db)
        account_service.delete_account(account_id)
        return {"message": "Account deleted successfully"}
    except AccountNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ServiceError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

# --- Currency Balance Endpoints ---

@router.post(
    "/accounts/{account_id}/balances",
    response_model=schemas.CurrencyBalance,
    status_code=status.HTTP_201_CREATED,
    summary="Add a new currency balance to an account"
)
def create_currency_balance_endpoint(
    account_id: int,
    balance_data: schemas.CurrencyBalanceCreate,
    db: Session = Depends(get_db)
) -> None:
    """
    Adds a new currency balance (e.g., a new currency) to an existing account.
    """
    try:
        account_service = AccountService(db)
        return account_service.create_currency_balance(account_id, balance_data)
    except AccountNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except CurrencyBalanceAlreadyExists as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ServiceError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.put(
    "/accounts/{account_id}/balances/{currency_code}",
    response_model=schemas.CurrencyBalance,
    summary="Update or create a currency balance"
)
def update_currency_balance_endpoint(
    account_id: int,
    currency_code: str,
    balance_data: schemas.CurrencyBalanceUpdate,
    db: Session = Depends(get_db)
) -> None:
    """
    Updates the balance for a specific currency in an account. 
    If the balance does not exist, it will be created (upsert behavior).
    """
    try:
        account_service = AccountService(db)
        # Ensure the currency code in the path matches the one in the body for consistency
        if balance_data.currency_code != currency_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Currency code in path and body must match."
            )
        return account_service.update_currency_balance(account_id, currency_code, balance_data)
    except AccountNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ServiceError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.delete(
    "/accounts/{account_id}/balances/{currency_code}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a currency balance"
)
def delete_currency_balance_endpoint(
    account_id: int,
    currency_code: str,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Deletes a specific currency balance from an account.
    """
    try:
        account_service = AccountService(db)
        account_service.delete_currency_balance(account_id, currency_code)
        return {"message": "Currency balance deleted successfully"}
    except CurrencyBalanceNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ServiceError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))