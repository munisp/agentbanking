import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, func, update
from decimal import Decimal

from . import models
from .config import get_db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/loyalty",
    tags=["loyalty"],
    responses={404: {"description": "Not found"}},
)

# --- Helper Functions ---

def get_account_by_user_id(db: Session, user_id: int) -> models.LoyaltyAccount:
    """Helper to fetch a loyalty account by user_id or raise 404."""
    stmt = select(models.LoyaltyAccount).where(models.LoyaltyAccount.user_id == user_id)
    account = db.execute(stmt).scalar_one_or_none()
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Loyalty account for user_id {user_id} not found"
        )
    return account

def update_account_tier(account: models.LoyaltyAccount):
    """
    Business logic to update the loyalty tier based on current points.
    This is a simplified example.
    """
    points = account.current_points
    if points >= 5000:
        account.tier = models.LoyaltyTier.PLATINUM
    elif points >= 2000:
        account.tier = models.LoyaltyTier.GOLD
    elif points >= 500:
        account.tier = models.LoyaltyTier.SILVER
    else:
        account.tier = models.LoyaltyTier.BRONZE

# --- LoyaltyAccount Endpoints (CRUD) ---

@router.post(
    "/accounts",
    response_model=models.LoyaltyAccountResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new loyalty account",
    description="Creates a new loyalty account for a given user_id. Initial points are 0."
)
def create_loyalty_account(
    account_in: models.LoyaltyAccountCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new loyalty account.
    """
    logger.info(f"Attempting to create loyalty account for user_id: {account_in.user_id}")
    
    # Check if account already exists
    stmt = select(models.LoyaltyAccount).where(models.LoyaltyAccount.user_id == account_in.user_id)
    if db.execute(stmt).scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Loyalty account for user_id {account_in.user_id} already exists"
        )

    db_account = models.LoyaltyAccount(
        user_id=account_in.user_id,
        current_points=Decimal(0.00),
        tier=models.LoyaltyTier.BRONZE
    )
    db.add(db_account)
    db.commit()
    db.refresh(db_account)
    logger.info(f"Loyalty account created with ID: {db_account.id} for user_id: {db_account.user_id}")
    return db_account

@router.get(
    "/accounts/{user_id}",
    response_model=models.LoyaltyAccountResponse,
    summary="Get loyalty account details by user ID",
    description="Retrieves the current status of a loyalty account using the user's ID."
)
def read_loyalty_account(
    user_id: int,
    db: Session = Depends(get_db)
):
    """
    Retrieve a loyalty account by user_id.
    """
    return get_account_by_user_id(db, user_id)

@router.get(
    "/accounts",
    response_model=List[models.LoyaltyAccountResponse],
    summary="List all loyalty accounts",
    description="Retrieves a list of all loyalty accounts with optional pagination."
)
def list_loyalty_accounts(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, gt=0, le=100)
):
    """
    List all loyalty accounts with pagination.
    """
    stmt = select(models.LoyaltyAccount).offset(skip).limit(limit)
    accounts = db.execute(stmt).scalars().all()
    return accounts

@router.put(
    "/accounts/{user_id}",
    response_model=models.LoyaltyAccountResponse,
    summary="Update loyalty account details",
    description="Manually updates the tier or current points of a loyalty account. Use with caution."
)
def update_loyalty_account(
    user_id: int,
    account_in: models.LoyaltyAccountUpdate,
    db: Session = Depends(get_db)
):
    """
    Update a loyalty account.
    """
    db_account = get_account_by_user_id(db, user_id)

    update_data = account_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if key == "current_points":
            # Convert float to Decimal for database storage
            setattr(db_account, key, Decimal(str(value)))
        else:
            setattr(db_account, key, value)

    # Re-evaluate tier if points were manually updated
    if "current_points" in update_data:
        update_account_tier(db_account)

    db.add(db_account)
    db.commit()
    db.refresh(db_account)
    logger.info(f"Loyalty account for user_id {user_id} updated.")
    return db_account

@router.delete(
    "/accounts/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a loyalty account",
    description="Deletes a loyalty account and all associated activities."
)
def delete_loyalty_account(
    user_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete a loyalty account.
    """
    db_account = get_account_by_user_id(db, user_id)
    db.delete(db_account)
    db.commit()
    logger.warning(f"Loyalty account for user_id {user_id} deleted.")
    return

# --- LoyaltyActivity Endpoints (Business Logic) ---

@router.post(
    "/accounts/{user_id}/earn",
    response_model=models.LoyaltyAccountResponse,
    summary="Record a point earning activity",
    description="Adds points to a user's loyalty account and records the activity."
)
def earn_points(
    user_id: int,
    activity_in: models.LoyaltyActivityCreate,
    db: Session = Depends(get_db)
):
    """
    Record an EARN activity and update the account balance.
    """
    if activity_in.type != models.ActivityType.EARN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Activity type must be 'EARN' for this endpoint."
        )

    db_account = get_account_by_user_id(db, user_id)
    points_to_add = Decimal(str(activity_in.points_change))

    # 1. Update account balance
    db_account.current_points += points_to_add
    
    # 2. Update tier
    update_account_tier(db_account)

    # 3. Create activity log
    db_activity = models.LoyaltyActivity(
        account_id=db_account.id,
        type=activity_in.type,
        points_change=points_to_add,
        description=activity_in.description,
        reference_id=activity_in.reference_id
    )
    db.add(db_account)
    db.add(db_activity)
    db.commit()
    db.refresh(db_account)
    logger.info(f"User {user_id} earned {points_to_add} points. New balance: {db_account.current_points}")
    return db_account

@router.post(
    "/accounts/{user_id}/spend",
    response_model=models.LoyaltyAccountResponse,
    summary="Record a point spending activity",
    description="Deducts points from a user's loyalty account and records the activity."
)
def spend_points(
    user_id: int,
    activity_in: models.LoyaltyActivityCreate,
    db: Session = Depends(get_db)
):
    """
    Record a SPEND activity and update the account balance.
    """
    if activity_in.type != models.ActivityType.SPEND:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Activity type must be 'SPEND' for this endpoint."
        )

    db_account = get_account_by_user_id(db, user_id)
    points_to_deduct = Decimal(str(activity_in.points_change))

    if db_account.current_points < points_to_deduct:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Insufficient loyalty points for this transaction."
        )

    # 1. Update account balance (deduct)
    db_account.current_points -= points_to_deduct
    
    # 2. Update tier
    update_account_tier(db_account)

    # 3. Create activity log (points_change is stored as negative for SPEND)
    db_activity = models.LoyaltyActivity(
        account_id=db_account.id,
        type=activity_in.type,
        points_change=-points_to_deduct, # Store as negative
        description=activity_in.description,
        reference_id=activity_in.reference_id
    )
    db.add(db_account)
    db.add(db_activity)
    db.commit()
    db.refresh(db_account)
    logger.info(f"User {user_id} spent {points_to_deduct} points. New balance: {db_account.current_points}")
    return db_account

@router.get(
    "/accounts/{user_id}/activities",
    response_model=List[models.LoyaltyActivityResponse],
    summary="List loyalty activities for an account",
    description="Retrieves a paginated list of all loyalty activities for a specific user."
)
def list_loyalty_activities(
    user_id: int,
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, gt=0, le=100),
    activity_type: Optional[models.ActivityType] = Query(None, description="Filter by activity type.")
):
    """
    List loyalty activities for a specific account.
    """
    db_account = get_account_by_user_id(db, user_id)
    
    stmt = select(models.LoyaltyActivity).where(models.LoyaltyActivity.account_id == db_account.id)
    
    if activity_type:
        stmt = stmt.where(models.LoyaltyActivity.type == activity_type)
        
    stmt = stmt.order_by(models.LoyaltyActivity.created_at.desc()).offset(skip).limit(limit)
    
    activities = db.execute(stmt).scalars().all()
    return activities
