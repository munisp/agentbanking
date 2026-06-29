import logging
from typing import List, Optional
import os
from datetime import datetime, timezone
from math import floor

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from decimal import Decimal

import models
from config import get_db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/loyalty",
    tags=["loyalty"],
    responses={404: {"description": "Not found"}},
)

SUCCESS_STATUSES = {"SUCCESS", "SETTLED", "COMPLETED"}
REVERSAL_STATUSES = {"REVERSED", "CHARGEBACK", "CHARGED_BACK"}

MIN_ELIGIBLE_AMOUNT_NGN = Decimal(os.getenv("LOYALTY_MIN_TXN_NGN", "500"))
DAILY_POINTS_CAP = Decimal(os.getenv("LOYALTY_DAILY_CAP", "500"))
MONTHLY_POINTS_CAP = Decimal(os.getenv("LOYALTY_MONTHLY_CAP", "5000"))

RATE_BY_TXN_TYPE = {
    "cash_in": Decimal("0.001"),
    "cash_out": Decimal("0.001"),
    "bill_payment": Decimal("0.002"),
    "airtime": Decimal("0.0005"),
    "data": Decimal("0.0005"),
    "transfer": Decimal("0.001"),
    "withdrawal": Decimal("0.001"),
    "loan_payment": Decimal("0.002"),
    "lpo_payment": Decimal("0.002"),
    "insurance_premium": Decimal("0.002"),
    "supply_chain": Decimal("0.001"),
}


def _normalise_txn_type(txn_type: str) -> str:
    return txn_type.strip().lower().replace("-", "_").replace(" ", "_")


def _normalise_status(status_text: str) -> str:
    return status_text.strip().upper().replace("-", "_").replace(" ", "_")


def _sum_auto_earned_points_since(
    db: Session, account_id: int, start_at: datetime
) -> Decimal:
    stmt = select(func.coalesce(func.sum(models.LoyaltyActivity.points_change), 0)).where(
        models.LoyaltyActivity.account_id == account_id,
        models.LoyaltyActivity.type == models.ActivityType.EARN,
        models.LoyaltyActivity.created_at >= start_at,
        models.LoyaltyActivity.description.like("AUTO_EARN:%"),
    )
    value = db.execute(stmt).scalar_one()
    return Decimal(str(value or 0))


def _find_existing_auto_activity(
    db: Session, account_id: int, reference_id: str
) -> Optional[models.LoyaltyActivity]:
    stmt = (
        select(models.LoyaltyActivity)
        .where(
            models.LoyaltyActivity.account_id == account_id,
            models.LoyaltyActivity.reference_id == reference_id,
            models.LoyaltyActivity.description.like("AUTO_%"),
        )
        .order_by(models.LoyaltyActivity.id.desc())
    )
    return db.execute(stmt).scalars().first()


def _find_auto_earn_activity(
    db: Session, account_id: int, reference_id: str
) -> Optional[models.LoyaltyActivity]:
    stmt = (
        select(models.LoyaltyActivity)
        .where(
            models.LoyaltyActivity.account_id == account_id,
            models.LoyaltyActivity.reference_id == reference_id,
            models.LoyaltyActivity.type == models.ActivityType.EARN,
            models.LoyaltyActivity.description.like("AUTO_EARN:%"),
        )
        .order_by(models.LoyaltyActivity.id.desc())
    )
    return db.execute(stmt).scalars().first()

# --- Helper Functions ---


def get_account_by_user_id(db: Session, user_id: str) -> models.LoyaltyAccount:
    """Helper to fetch a loyalty account by string user_id or raise 404."""
    stmt = select(models.LoyaltyAccount).where(models.LoyaltyAccount.user_id == user_id)
    account = db.execute(stmt).scalar_one_or_none()
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Loyalty account for user_id {user_id} not found",
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
    description="Creates a new loyalty account for a given string user_id. Initial points are 0.",
)
def create_loyalty_account(
    account_in: models.LoyaltyAccountCreate, db: Session = Depends(get_db)
):
    """
    Create a new loyalty account.
    """
    logger.info(
        f"Attempting to create loyalty account for user_id: {account_in.user_id}"
    )

    # Check if account already exists
    stmt = select(models.LoyaltyAccount).where(
        models.LoyaltyAccount.user_id == account_in.user_id
    )
    if db.execute(stmt).scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Loyalty account for user_id {account_in.user_id} already exists",
        )

    db_account = models.LoyaltyAccount(
        user_id=account_in.user_id,
        current_points=Decimal(0.00),
        tier=models.LoyaltyTier.BRONZE,
    )
    db.add(db_account)
    db.commit()
    db.refresh(db_account)
    logger.info(
        f"Loyalty account created with ID: {db_account.id} for user_id: {db_account.user_id}"
    )
    return db_account


@router.get(
    "/accounts/{user_id}",
    response_model=models.LoyaltyAccountResponse,
    summary="Get loyalty account details by user ID",
    description="Retrieves the current status of a loyalty account using the user's string ID.",
)
def read_loyalty_account(user_id: str, db: Session = Depends(get_db)):
    """
    Retrieve a loyalty account by user_id, creating one if it doesn't exist.
    """
    stmt = select(models.LoyaltyAccount).where(models.LoyaltyAccount.user_id == user_id)
    account = db.execute(stmt).scalar_one_or_none()
    if account is None:
        account = models.LoyaltyAccount(
            user_id=user_id,
            current_points=Decimal(0.00),
            tier=models.LoyaltyTier.BRONZE,
        )
        db.add(account)
        db.commit()
        db.refresh(account)
    return account


@router.get(
    "/accounts",
    response_model=List[models.LoyaltyAccountResponse],
    summary="List all loyalty accounts",
    description="Retrieves a list of all loyalty accounts with optional pagination.",
)
def list_loyalty_accounts(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, gt=0, le=100),
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
    description="Manually updates the tier or current points of a loyalty account using a string user_id. Use with caution.",
)
def update_loyalty_account(
    user_id: str, account_in: models.LoyaltyAccountUpdate, db: Session = Depends(get_db)
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
    description="Deletes a loyalty account and all associated activities for a string user_id.",
)
def delete_loyalty_account(user_id: str, db: Session = Depends(get_db)):
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
    description="Adds points to a user's loyalty account and records the activity.",
)
def earn_points(
    user_id: str,
    activity_in: models.LoyaltyActivityCreate,
    db: Session = Depends(get_db),
):
    """
    Record an EARN activity and update the account balance.
    """
    if activity_in.type != models.ActivityType.EARN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Activity type must be 'EARN' for this endpoint.",
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
        reference_id=activity_in.reference_id,
    )
    db.add(db_account)
    db.add(db_activity)
    db.commit()
    db.refresh(db_account)
    logger.info(
        f"User {user_id} earned {points_to_add} points. New balance: {db_account.current_points}"
    )
    return db_account


@router.post(
    "/accounts/{user_id}/spend",
    response_model=models.LoyaltyAccountResponse,
    summary="Record a point spending activity",
    description="Deducts points from a user's loyalty account and records the activity.",
)
def spend_points(
    user_id: str,
    activity_in: models.LoyaltyActivityCreate,
    db: Session = Depends(get_db),
):
    """
    Record a SPEND activity and update the account balance.
    """
    if activity_in.type != models.ActivityType.SPEND:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Activity type must be 'SPEND' for this endpoint.",
        )

    db_account = get_account_by_user_id(db, user_id)
    points_to_deduct = Decimal(str(activity_in.points_change))

    if db_account.current_points < points_to_deduct:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Insufficient loyalty points for this transaction.",
        )

    # 1. Update account balance (deduct)
    db_account.current_points -= points_to_deduct

    # 2. Update tier
    update_account_tier(db_account)

    # 3. Create activity log (points_change is stored as negative for SPEND)
    db_activity = models.LoyaltyActivity(
        account_id=db_account.id,
        type=activity_in.type,
        points_change=-points_to_deduct,  # Store as negative
        description=activity_in.description,
        reference_id=activity_in.reference_id,
    )
    db.add(db_account)
    db.add(db_activity)
    db.commit()
    db.refresh(db_account)
    logger.info(
        f"User {user_id} spent {points_to_deduct} points. New balance: {db_account.current_points}"
    )
    return db_account


@router.get(
    "/accounts/{user_id}/activities",
    response_model=List[models.LoyaltyActivityResponse],
    summary="List loyalty activities for an account",
    description="Retrieves a paginated list of all loyalty activities for a specific user.",
)
def list_loyalty_activities(
    user_id: str,
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, gt=0, le=100),
    activity_type: Optional[models.ActivityType] = Query(
        None, description="Filter by activity type."
    ),
):
    """
    List loyalty activities for a specific account.
    """
    db_account = get_account_by_user_id(db, user_id)

    stmt = select(models.LoyaltyActivity).where(
        models.LoyaltyActivity.account_id == db_account.id
    )

    if activity_type:
        stmt = stmt.where(models.LoyaltyActivity.type == activity_type)

    stmt = (
        stmt.order_by(models.LoyaltyActivity.created_at.desc())
        .offset(skip)
        .limit(limit)
    )

    activities = db.execute(stmt).scalars().all()
    return activities


@router.get("/leaderboard", summary="Agent loyalty leaderboard ranked by points")
def get_leaderboard(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    stmt = (
        select(
            models.LoyaltyAccount,
            func.count(models.LoyaltyActivity.id)
            .filter(models.LoyaltyActivity.type == models.ActivityType.EARN)
            .label("total_transactions"),
        )
        .outerjoin(
            models.LoyaltyActivity,
            models.LoyaltyAccount.id == models.LoyaltyActivity.account_id,
        )
        .group_by(models.LoyaltyAccount.id)
        .order_by(models.LoyaltyAccount.current_points.desc())
        .limit(limit)
    )
    rows = db.execute(stmt).all()
    return [
        {
            "agent_id": acc.user_id,
            "agent_name": acc.user_id,
            "points": float(acc.current_points),
            "tier": acc.tier.value,
            "total_transactions": txn_count,
            "total_volume": 0,
        }
        for acc, txn_count in rows
    ]


@router.get("/stats", summary="Aggregate loyalty programme statistics")
def get_loyalty_stats(db: Session = Depends(get_db)):
    total_accounts = db.execute(
        select(func.count(models.LoyaltyAccount.id))
    ).scalar_one()
    total_points = db.execute(
        select(func.coalesce(func.sum(models.LoyaltyAccount.current_points), 0))
    ).scalar_one()
    tier_rows = db.execute(
        select(models.LoyaltyAccount.tier, func.count(models.LoyaltyAccount.id)).group_by(
            models.LoyaltyAccount.tier
        )
    ).all()
    return {
        "total_accounts": total_accounts,
        "total_points_issued": float(total_points),
        "tier_breakdown": {tier.value: count for tier, count in tier_rows},
    }


@router.get("/badges", summary="List all loyalty tier badges")
def list_badges():
    return [
        {
            "id": "badge-bronze",
            "name": "Bronze Agent",
            "description": "Starting tier — accumulate up to 499 points",
            "tier": "Bronze",
        },
        {
            "id": "badge-silver",
            "name": "Silver Agent",
            "description": "Accumulated 500–1,999 loyalty points",
            "tier": "Silver",
        },
        {
            "id": "badge-gold",
            "name": "Gold Agent",
            "description": "Accumulated 2,000–4,999 loyalty points",
            "tier": "Gold",
        },
        {
            "id": "badge-platinum",
            "name": "Platinum Agent",
            "description": "Elite tier — accumulated 5,000+ loyalty points",
            "tier": "Platinum",
        },
    ]


@router.get("/achievements", summary="List achievements and how many agents have earned each")
def list_achievements(db: Session = Depends(get_db)):
    milestones = [
        {
            "id": "ach-first-txn",
            "name": "First Transaction",
            "description": "Processed your first loyalty-earning transaction",
            "points": 10,
            "threshold": Decimal("1"),
        },
        {
            "id": "ach-100-pts",
            "name": "Century Club",
            "description": "Accumulated 100 loyalty points",
            "points": 50,
            "threshold": Decimal("100"),
        },
        {
            "id": "ach-500-pts",
            "name": "Silver Milestone",
            "description": "Accumulated 500 loyalty points — reached Silver tier",
            "points": 100,
            "threshold": Decimal("500"),
        },
        {
            "id": "ach-2000-pts",
            "name": "Gold Milestone",
            "description": "Accumulated 2,000 loyalty points — reached Gold tier",
            "points": 200,
            "threshold": Decimal("2000"),
        },
        {
            "id": "ach-5000-pts",
            "name": "Platinum Elite",
            "description": "Accumulated 5,000 loyalty points — reached Platinum tier",
            "points": 500,
            "threshold": Decimal("5000"),
        },
    ]
    result = []
    for m in milestones:
        earned_count = db.execute(
            select(func.count(models.LoyaltyAccount.id)).where(
                models.LoyaltyAccount.current_points >= m["threshold"]
            )
        ).scalar_one()
        result.append(
            {
                "id": m["id"],
                "name": m["name"],
                "description": m["description"],
                "points": m["points"],
                "earned_count": earned_count,
            }
        )
    return result


@router.post(
    "/transactions/process",
    response_model=models.LoyaltyTransactionEventResponse,
    summary="Process transaction for automatic loyalty points",
    description="Awards or reverses loyalty points from completed transaction events with idempotency and caps.",
)
def process_transaction_for_loyalty(
    event_in: models.LoyaltyTransactionEventCreate, db: Session = Depends(get_db)
):
    # Auto-create account on first transaction so onboarding order doesn't matter
    stmt = select(models.LoyaltyAccount).where(models.LoyaltyAccount.user_id == event_in.user_id)
    db_account = db.execute(stmt).scalar_one_or_none()
    if db_account is None:
        db_account = models.LoyaltyAccount(
            user_id=event_in.user_id,
            current_points=Decimal(0),
            tier=models.LoyaltyTier.BRONZE,
        )
        db.add(db_account)
        db.commit()
        db.refresh(db_account)
        logger.info(f"Auto-created loyalty account for user_id={event_in.user_id}")
    existing = _find_existing_auto_activity(db, db_account.id, event_in.reference_id)

    if existing is not None:
        return {
            "processed": True,
            "awarded": False,
            "reference_id": event_in.reference_id,
            "points_change": 0,
            "current_points": float(db_account.current_points),
            "tier": db_account.tier,
            "reason": "reference_already_processed",
        }

    txn_status = _normalise_status(event_in.status)
    txn_type = _normalise_txn_type(event_in.transaction_type)
    amount_ngn = Decimal(str(event_in.amount_ngn))
    bonus_points = Decimal(str(event_in.bonus_points or 0))

    now = datetime.now(timezone.utc)

    if txn_status in REVERSAL_STATUSES:
        original_earn = _find_auto_earn_activity(db, db_account.id, event_in.reference_id)
        if original_earn is None:
            skip_activity = models.LoyaltyActivity(
                account_id=db_account.id,
                type=models.ActivityType.ADJUST,
                points_change=Decimal("0.00"),
                description="AUTO_REVERSAL:skip_no_original_earn",
                reference_id=event_in.reference_id,
            )
            db.add(skip_activity)
            db.commit()
            db.refresh(db_account)
            return {
                "processed": True,
                "awarded": False,
                "reference_id": event_in.reference_id,
                "points_change": 0,
                "current_points": float(db_account.current_points),
                "tier": db_account.tier,
                "reason": "reversal_without_original_earn",
            }

        deduction = min(
            Decimal(str(abs(original_earn.points_change))),
            Decimal(str(db_account.current_points)),
        )
        db_account.current_points -= deduction
        update_account_tier(db_account)

        reversal_activity = models.LoyaltyActivity(
            account_id=db_account.id,
            type=models.ActivityType.ADJUST,
            points_change=-deduction,
            description="AUTO_REVERSAL:transaction_reversal",
            reference_id=event_in.reference_id,
        )
        db.add(db_account)
        db.add(reversal_activity)
        db.commit()
        db.refresh(db_account)

        return {
            "processed": True,
            "awarded": deduction > 0,
            "reference_id": event_in.reference_id,
            "points_change": float(-deduction),
            "current_points": float(db_account.current_points),
            "tier": db_account.tier,
            "reason": "reversal_processed",
        }

    if txn_status not in SUCCESS_STATUSES:
        skip_activity = models.LoyaltyActivity(
            account_id=db_account.id,
            type=models.ActivityType.ADJUST,
            points_change=Decimal("0.00"),
            description=f"AUTO_SKIP:status_{txn_status.lower()}",
            reference_id=event_in.reference_id,
        )
        db.add(skip_activity)
        db.commit()
        db.refresh(db_account)
        return {
            "processed": True,
            "awarded": False,
            "reference_id": event_in.reference_id,
            "points_change": 0,
            "current_points": float(db_account.current_points),
            "tier": db_account.tier,
            "reason": "transaction_not_eligible_status",
        }

    if amount_ngn < MIN_ELIGIBLE_AMOUNT_NGN:
        skip_activity = models.LoyaltyActivity(
            account_id=db_account.id,
            type=models.ActivityType.ADJUST,
            points_change=Decimal("0.00"),
            description="AUTO_SKIP:below_minimum_amount",
            reference_id=event_in.reference_id,
        )
        db.add(skip_activity)
        db.commit()
        db.refresh(db_account)
        return {
            "processed": True,
            "awarded": False,
            "reference_id": event_in.reference_id,
            "points_change": 0,
            "current_points": float(db_account.current_points),
            "tier": db_account.tier,
            "reason": "below_minimum_amount",
        }

    rate = RATE_BY_TXN_TYPE.get(txn_type, Decimal("0.001"))
    computed_points = Decimal(floor(float(amount_ngn * rate))) + bonus_points
    if computed_points <= 0:
        skip_activity = models.LoyaltyActivity(
            account_id=db_account.id,
            type=models.ActivityType.ADJUST,
            points_change=Decimal("0.00"),
            description="AUTO_SKIP:computed_zero_points",
            reference_id=event_in.reference_id,
        )
        db.add(skip_activity)
        db.commit()
        db.refresh(db_account)
        return {
            "processed": True,
            "awarded": False,
            "reference_id": event_in.reference_id,
            "points_change": 0,
            "current_points": float(db_account.current_points),
            "tier": db_account.tier,
            "reason": "computed_zero_points",
        }

    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    earned_today = _sum_auto_earned_points_since(db, db_account.id, day_start)
    earned_this_month = _sum_auto_earned_points_since(db, db_account.id, month_start)

    remaining_daily = max(Decimal("0"), DAILY_POINTS_CAP - earned_today)
    remaining_monthly = max(Decimal("0"), MONTHLY_POINTS_CAP - earned_this_month)
    awarded_points = min(computed_points, remaining_daily, remaining_monthly)

    if awarded_points <= 0:
        skip_activity = models.LoyaltyActivity(
            account_id=db_account.id,
            type=models.ActivityType.ADJUST,
            points_change=Decimal("0.00"),
            description="AUTO_SKIP:points_cap_reached",
            reference_id=event_in.reference_id,
        )
        db.add(skip_activity)
        db.commit()
        db.refresh(db_account)
        return {
            "processed": True,
            "awarded": False,
            "reference_id": event_in.reference_id,
            "points_change": 0,
            "current_points": float(db_account.current_points),
            "tier": db_account.tier,
            "reason": "points_cap_reached",
        }

    db_account.current_points += awarded_points
    update_account_tier(db_account)

    earn_activity = models.LoyaltyActivity(
        account_id=db_account.id,
        type=models.ActivityType.EARN,
        points_change=awarded_points,
        description=f"AUTO_EARN:txn_type={txn_type};status={txn_status}",
        reference_id=event_in.reference_id,
    )

    db.add(db_account)
    db.add(earn_activity)
    db.commit()
    db.refresh(db_account)

    return {
        "processed": True,
        "awarded": True,
        "reference_id": event_in.reference_id,
        "points_change": float(awarded_points),
        "current_points": float(db_account.current_points),
        "tier": db_account.tier,
        "reason": "points_awarded",
    }
