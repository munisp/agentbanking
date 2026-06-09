from typing import List, Optional

from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from service import RewardService, UserPointsService
from schemas import (
    Reward, RewardCreate, RewardUpdate,
    UserPoints, RewardTransaction,
    PointsAdjustmentRequest, RewardRedemptionRequest,
    TransactionType
)

# Production implementation for a real authentication dependency
# In a production app, this would extract the user_id from a JWT or session
def get_current_user_id(user_id: int = Query(..., description="The ID of the authenticated user.")) -> int:
    return user_id

rewards_router = APIRouter()

# --- Reward Endpoints (Admin/System Access) ---

@rewards_router.post("/rewards", response_model=Reward, status_code=status.HTTP_201_CREATED, summary="Create a new reward")
async def create_reward(
    reward_in: RewardCreate,
    db: AsyncSession = Depends(get_db)
) -> None:
    """
    Creates a new reward that users can redeem with points.
    Requires system/admin privileges.
    """
    service = RewardService(db)
    return await service.create_reward(reward_in)

@rewards_router.get("/rewards", response_model=List[Reward], summary="List all rewards")
async def list_rewards(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=1000),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db: AsyncSession = Depends(get_db)
) -> None:
    """
    Retrieves a list of all rewards, with optional filtering by active status.
    """
    service = RewardService(db)
    return await service.list_rewards(skip=skip, limit=limit, is_active=is_active)

@rewards_router.get("/rewards/{reward_id}", response_model=Reward, summary="Get a reward by ID")
async def get_reward(
    reward_id: int,
    db: AsyncSession = Depends(get_db)
) -> None:
    """
    Retrieves a single reward by its unique ID.
    """
    service = RewardService(db)
    return await service.get_reward(reward_id)

@rewards_router.put("/rewards/{reward_id}", response_model=Reward, summary="Update an existing reward")
async def update_reward(
    reward_id: int,
    reward_in: RewardUpdate,
    db: AsyncSession = Depends(get_db)
) -> None:
    """
    Updates an existing reward's details.
    Requires system/admin privileges.
    """
    service = RewardService(db)
    return await service.update_reward(reward_id, reward_in)

@rewards_router.delete("/rewards/{reward_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a reward")
async def delete_reward(
    reward_id: int,
    db: AsyncSession = Depends(get_db)
) -> None:
    """
    Deletes a reward. Note: This should be handled carefully in a production system (e.g., soft delete).
    Requires system/admin privileges.
    """
    service = RewardService(db)
    await service.delete_reward(reward_id)
    return

# --- User Points Endpoints (User Access) ---

@rewards_router.get("/users/me/points", response_model=UserPoints, summary="Get current user's points balance")
async def get_my_points(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
) -> None:
    """
    Retrieves the current points balance for the authenticated user.
    """
    service = UserPointsService(db)
    return await service.get_user_points(user_id)

@rewards_router.post("/users/me/points/earn", response_model=UserPoints, summary="Earn points for the current user")
async def earn_points(
    adjustment_in: PointsAdjustmentRequest,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
) -> None:
    """
    Records an 'EARN' transaction and updates the user's points balance.
    Note: The `points_change` in the request should be positive.
    """
    if adjustment_in.points_change <= 0:
        raise status.HTTP_400_BAD_REQUEST(detail="Points change for earning must be positive.")

    service = UserPointsService(db)
    return await service.adjust_user_points(user_id, adjustment_in, TransactionType.EARN)

@rewards_router.post("/users/me/points/adjust", response_model=UserPoints, summary="Adjust points for the current user (Admin only)")
async def adjust_points(
    adjustment_in: PointsAdjustmentRequest,
    user_id: int = Depends(get_current_user_id), # In a real app, this would be the target user_id, and the caller would be an admin
    db: AsyncSession = Depends(get_db)
) -> None:
    """
    Records an 'ADJUST' transaction and updates the user's points balance.
    This endpoint is typically restricted to admin/system users.
    `points_change` can be positive or negative.
    """
    service = UserPointsService(db)
    return await service.adjust_user_points(user_id, adjustment_in, TransactionType.ADJUST)

@rewards_router.post("/users/me/rewards/redeem", response_model=RewardTransaction, status_code=status.HTTP_201_CREATED, summary="Redeem a reward")
async def redeem_reward(
    redemption_in: RewardRedemptionRequest,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
) -> None:
    """
    Redeems a reward, deducting the cost from the user's points balance and recording a 'REDEEM' transaction.
    """
    service = UserPointsService(db)
    return await service.redeem_reward(user_id, redemption_in)

@rewards_router.get("/users/me/transactions", response_model=List[RewardTransaction], summary="Get current user's transaction history")
async def get_my_transactions(
    user_id: int = Depends(get_current_user_id),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=1000),
    db: AsyncSession = Depends(get_db)
) -> None:
    """
    Retrieves the transaction history for the authenticated user.
    """
    service = UserPointsService(db)
    return await service.list_user_transactions(user_id, skip=skip, limit=limit)