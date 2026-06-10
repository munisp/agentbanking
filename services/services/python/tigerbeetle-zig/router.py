import logging
import os
from typing import List
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select, func

from . import models
from .config import get_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SYNC_MANAGER_URL = os.getenv("SYNC_MANAGER_URL", "http://localhost:8085")


async def _publish_sync_event(event_type: str, operation: str, data: dict):
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            if event_type == "account":
                await client.post(f"{SYNC_MANAGER_URL}/api/v1/sync/accounts", json=data)
            elif event_type == "transfer":
                await client.post(f"{SYNC_MANAGER_URL}/api/v1/sync/transfers", json=data)
            logger.info(f"Sync event published: {event_type}/{operation}")
    except Exception as e:
        logger.warning(f"Failed to publish sync event: {e}")

router = APIRouter(
    prefix="/tigerbeetle-zig",
    tags=["tigerbeetle-zig"],
)

# --- Helper Functions ---

def _create_activity_log(db: Session, account_id: UUID, event_type: str, description: str):
    """Internal function to create an activity log entry."""
    log_entry = models.ActivityLog(
        account_id=account_id,
        event_type=event_type,
        description=description
    )
    db.add(log_entry)
    # Note: The log is committed with the main transaction in the endpoint functions.

# --- LedgerAccount CRUD Endpoints ---

@router.post(
    "/accounts",
    response_model=models.LedgerAccountResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new Ledger Account",
    description="Creates a new ledger account with a unique account_id. Initializes balance to 0.00."
)
def create_account(
    account_in: models.LedgerAccountCreate,
    db: Session = Depends(get_db)
):
    """
    Creates a new LedgerAccount in the database.
    Raises a 400 error if an account with the given account_id already exists.
    """
    logger.info(f"Attempting to create account with ID: {account_in.account_id}")
    
    # Check for existing account_id
    existing_account = db.scalar(
        select(models.LedgerAccount).where(models.LedgerAccount.account_id == account_in.account_id)
    )
    if existing_account:
        logger.warning(f"Account creation failed: account_id {account_in.account_id} already exists.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Account with account_id '{account_in.account_id}' already exists."
        )

    db_account = models.LedgerAccount(**account_in.model_dump())
    
    try:
        db.add(db_account)
        db.flush() # Flush to get the generated UUID for logging
        
        _create_activity_log(
            db, 
            db_account.id, 
            "CREATED", 
            f"Account created with type: {db_account.account_type} and currency: {db_account.currency_code}."
        )
        
        db.commit()
        db.refresh(db_account)
        logger.info(f"Successfully created account with internal ID: {db_account.id}")
        return db_account
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Database integrity error during account creation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error: Could not create account due to integrity constraint."
        )

@router.get(
    "/accounts/{account_id}",
    response_model=models.LedgerAccountResponse,
    summary="Retrieve a Ledger Account by its unique ID",
    description="Fetches a single ledger account using its internal UUID."
)
def read_account(
    account_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Retrieves a LedgerAccount by its internal UUID.
    Raises a 404 error if the account is not found.
    """
    db_account = db.scalar(
        select(models.LedgerAccount)
        .where(models.LedgerAccount.id == account_id)
    )
    if db_account is None:
        logger.warning(f"Account not found for internal ID: {account_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ledger Account not found"
        )
    return db_account

@router.get(
    "/accounts",
    response_model=List[models.LedgerAccountResponse],
    summary="List all Ledger Accounts",
    description="Retrieves a list of all ledger accounts, with optional pagination."
)
def list_accounts(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Retrieves a list of LedgerAccounts with pagination.
    """
    accounts = db.scalars(
        select(models.LedgerAccount).offset(skip).limit(limit)
    ).all()
    return accounts

@router.patch(
    "/accounts/{account_id}",
    response_model=models.LedgerAccountResponse,
    summary="Update an existing Ledger Account",
    description="Updates one or more fields of an existing ledger account using its internal UUID."
)
def update_account(
    account_id: UUID,
    account_in: models.LedgerAccountUpdate,
    db: Session = Depends(get_db)
):
    """
    Updates an existing LedgerAccount. Only non-null fields in the input schema are updated.
    Raises a 404 error if the account is not found.
    """
    db_account = db.scalar(
        select(models.LedgerAccount).where(models.LedgerAccount.id == account_id)
    )
    if db_account is None:
        logger.warning(f"Update failed: Account not found for internal ID: {account_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ledger Account not found"
        )

    update_data = account_in.model_dump(exclude_unset=True)
    
    changes = []
    for key, value in update_data.items():
        if hasattr(db_account, key) and getattr(db_account, key) != value:
            changes.append(f"{key} changed from {getattr(db_account, key)} to {value}")
            setattr(db_account, key, value)

    if changes:
        _create_activity_log(
            db, 
            db_account.id, 
            "UPDATED", 
            "Account details updated: " + "; ".join(changes)
        )
        db.commit()
        db.refresh(db_account)
        logger.info(f"Successfully updated account with internal ID: {account_id}")
    else:
        logger.info(f"No changes detected for account with internal ID: {account_id}")

    return db_account

@router.delete(
    "/accounts/{account_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a Ledger Account",
    description="Deletes a ledger account using its internal UUID. This will also delete all associated activity logs."
)
def delete_account(
    account_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Deletes a LedgerAccount and all associated ActivityLogs (due to CASCADE).
    Raises a 404 error if the account is not found.
    """
    db_account = db.scalar(
        select(models.LedgerAccount).where(models.LedgerAccount.id == account_id)
    )
    if db_account is None:
        logger.warning(f"Deletion failed: Account not found for internal ID: {account_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ledger Account not found"
        )

    db.delete(db_account)
    db.commit()
    logger.info(f"Successfully deleted account with internal ID: {account_id}")
    return

# --- Business-Specific Endpoint: Transfer ---

class TransferRequest(models.BaseModel):
    """Schema for a fund transfer request."""
    debit_account_id: str = Field(..., description="The account_id to debit (source).")
    credit_account_id: str = Field(..., description="The account_id to credit (destination).")
    amount: float = Field(..., gt=0, description="The amount to transfer. Must be positive.")
    description: str = Field(..., description="Description of the transfer.")

@router.post(
    "/transfers",
    status_code=status.HTTP_200_OK,
    summary="Perform a double-entry fund transfer",
    description="Processes a double-entry transfer between two accounts. This is the core business logic."
)
def transfer_funds(
    transfer_in: TransferRequest,
    db: Session = Depends(get_db)
):
    """
    Performs a double-entry transfer: debits the source account and credits the destination account.
    This operation is atomic (ACID).
    """
    if transfer_in.debit_account_id == transfer_in.credit_account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debit and credit accounts must be different."
        )

    # 1. Fetch accounts
    debit_account = db.scalar(
        select(models.LedgerAccount).where(models.LedgerAccount.account_id == transfer_in.debit_account_id)
    )
    credit_account = db.scalar(
        select(models.LedgerAccount).where(models.LedgerAccount.account_id == transfer_in.credit_account_id)
    )

    if not debit_account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Debit account '{transfer_in.debit_account_id}' not found.")
    if not credit_account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Credit account '{transfer_in.credit_account_id}' not found.")
    
    if debit_account.currency_code != credit_account.currency_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Currency codes must match for transfer.")
    
    if not debit_account.is_active or not credit_account.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Both accounts must be active for transfer.")

    # 2. Perform the transfer (Debit = subtract, Credit = add)
    amount = transfer_in.amount
    
    # Check for sufficient funds (a simple check, real systems are more complex)
    if debit_account.current_balance < amount:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Insufficient funds in debit account.")

    debit_account.current_balance -= amount
    credit_account.current_balance += amount

    # 3. Create activity logs
    log_description = f"Transfer of {amount} {debit_account.currency_code} for: {transfer_in.description}"
    
    _create_activity_log(
        db, 
        debit_account.id, 
        "DEBIT", 
        f"DEBIT: {log_description}. New balance: {debit_account.current_balance}"
    )
    _create_activity_log(
        db, 
        credit_account.id, 
        "CREDIT", 
        f"CREDIT: {log_description}. New balance: {credit_account.current_balance}"
    )

    # 4. Commit transaction
    try:
        db.commit()
        logger.info(f"Successful transfer of {amount} from {debit_account.account_id} to {credit_account.account_id}")

        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(_publish_sync_event("transfer", "create", {
                    "debit_account_id": str(transfer_in.debit_account_id),
                    "credit_account_id": str(transfer_in.credit_account_id),
                    "amount": amount,
                    "currency": debit_account.currency_code,
                    "description": transfer_in.description,
                }))
            else:
                loop.run_until_complete(_publish_sync_event("transfer", "create", {
                    "debit_account_id": str(transfer_in.debit_account_id),
                    "credit_account_id": str(transfer_in.credit_account_id),
                    "amount": amount,
                    "currency": debit_account.currency_code,
                    "description": transfer_in.description,
                }))
        except Exception as sync_err:
            logger.warning(f"Sync event publish failed (non-blocking): {sync_err}")

        return {"message": "Transfer successful", "transaction_amount": amount}
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Database integrity error during transfer: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error: Transfer failed due to integrity constraint."
        )

# --- ActivityLog Endpoints ---

@router.get(
    "/accounts/{account_id}/logs",
    response_model=List[models.ActivityLogResponse],
    summary="Get activity logs for a specific account",
    description="Retrieves a list of all activity logs associated with a given Ledger Account internal UUID."
)
def get_account_logs(
    account_id: UUID,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Retrieves activity logs for a specific account, ordered by timestamp.
    Raises a 404 error if the account is not found.
    """
    # Check if account exists
    account_exists = db.scalar(
        select(models.LedgerAccount.id).where(models.LedgerAccount.id == account_id)
    )
    if not account_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ledger Account not found"
        )

    logs = db.scalars(
        select(models.ActivityLog)
        .where(models.ActivityLog.account_id == account_id)
        .order_by(models.ActivityLog.timestamp.desc())
        .offset(skip)
        .limit(limit)
    ).all()
    
    return logs
