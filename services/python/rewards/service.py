import logging
from typing import List, Optional

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from models import Reward, UserPoints, RewardTransaction
from schemas import (
    RewardCreate, RewardUpdate, RewardTransactionCreate,
    TransactionType, PointsAdjustmentRequest, RewardRedemptionRequest
)
from main import ServiceException # Re-using the custom exception defined in main.py

logger = logging.getLogger(__name__)

# --- Custom Service Exceptions ---

class NotFoundException(ServiceException):
    def __init__(self, detail: str = "Resource not found") -> None:
        super().__init__(status_code=404, detail=detail)

class ConflictException(ServiceException):
    def __init__(self, detail: str = "Resource already exists or a conflict occurred") -> None:
        super().__init__(status_code=409, detail=detail)

class BadRequestException(ServiceException):
    def __init__(self, detail: str = "Invalid request") -> None:
        super().__init__(status_code=400, detail=detail)

class ForbiddenException(ServiceException):
    def __init__(self, detail: str = "Operation forbidden") -> None:
        super().__init__(status_code=403, detail=detail)

# --- Helper Functions ---

async def get_user_points_model(db: AsyncSession, user_id: int) -> Optional[UserPoints]:
    """Retrieves the UserPoints model for a given user_id."""
    stmt = select(UserPoints).where(UserPoints.user_id == user_id)
    result = await db.execute(stmt)
    return result.scalars().first()

async def get_or_create_user_points(db: AsyncSession, user_id: int) -> UserPoints:
    """Retrieves or creates the UserPoints model for a given user_id."""
    user_points = await get_user_points_model(db, user_id)
    if user_points is None:
        user_points = UserPoints(user_id=user_id, points_balance=0)
        db.add(user_points)
        await db.flush() # Flush to get the ID, but don't commit yet
        logger.info(f"Created new UserPoints record for user_id: {user_id}")
    return user_points

# --- Reward Service ---

class RewardService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_reward(self, reward_in: RewardCreate) -> Reward:
        logger.info(f"Attempting to create reward: {reward_in.name}")
        try:
            db_reward = Reward(**reward_in.model_dump())
            self.db.add(db_reward)
            await self.db.commit()
            await self.db.refresh(db_reward)
            logger.info(f"Successfully created reward with ID: {db_reward.id}")
            return db_reward
        except IntegrityError:
            await self.db.rollback()
            raise ConflictException(detail=f"Reward with name '{reward_in.name}' already exists.")
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating reward: {e}")
            raise ServiceException(status_code=500, detail="Failed to create reward due to a server error.")

    async def get_reward(self, reward_id: int) -> Reward:
        stmt = select(Reward).where(Reward.id == reward_id)
        result = await self.db.execute(stmt)
        db_reward = result.scalars().first()
        if not db_reward:
            raise NotFoundException(detail=f"Reward with ID {reward_id} not found.")
        return db_reward

    async def list_rewards(self, skip: int = 0, limit: int = 100, is_active: Optional[bool] = None) -> List[Reward]:
        stmt = select(Reward).offset(skip).limit(limit).order_by(Reward.id)
        if is_active is not None:
            stmt = stmt.where(Reward.is_active == is_active)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update_reward(self, reward_id: int, reward_in: RewardUpdate) -> Reward:
        db_reward = await self.get_reward(reward_id)
        update_data = reward_in.model_dump(exclude_unset=True)

        for key, value in update_data.items():
            setattr(db_reward, key, value)

        try:
            await self.db.commit()
            await self.db.refresh(db_reward)
            logger.info(f"Successfully updated reward with ID: {reward_id}")
            return db_reward
        except IntegrityError:
            await self.db.rollback()
            raise ConflictException(detail=f"Reward name conflict during update.")
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error updating reward {reward_id}: {e}")
            raise ServiceException(status_code=500, detail="Failed to update reward due to a server error.")

    async def delete_reward(self, reward_id: int) -> None:
        db_reward = await self.get_reward(reward_id)
        await self.db.delete(db_reward)
        await self.db.commit()
        logger.info(f"Successfully deleted reward with ID: {reward_id}")

# --- User Points and Transaction Service ---

class UserPointsService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_user_points(self, user_id: int) -> UserPoints:
        db_user_points = await get_user_points_model(self.db, user_id)
        if not db_user_points:
            # For a rewards service, it's often better to create the record if it doesn't exist
            # However, for a GET endpoint, we'll return 404 or a default. Let's return a default of 0 points.
            # But since the model must exist to have transactions, we'll create it on first interaction.
            # For a simple GET, let's just return a 404 if the user has never interacted.
            raise NotFoundException(detail=f"User with ID {user_id} has no points record.")
        return db_user_points

    async def _create_transaction(self, user_points: UserPoints, transaction_type: TransactionType,
                                  points_change: int, description: Optional[str] = None,
                                  reward_id: Optional[int] = None) -> RewardTransaction:
        """Internal method to create a transaction record."""
        transaction_in = RewardTransactionCreate(
            user_id=user_points.user_id,
            reward_id=reward_id,
            transaction_type=transaction_type,
            points_change=points_change,
            description=description
        )

        db_transaction = RewardTransaction(
            user_points_id=user_points.id,
            reward_id=transaction_in.reward_id,
            transaction_type=transaction_in.transaction_type.value,
            points_change=transaction_in.points_change,
            description=transaction_in.description
        )
        self.db.add(db_transaction)
        await self.db.flush() # Flush to ensure transaction is recorded before commit
        return db_transaction

    async def adjust_user_points(self, user_id: int, adjustment_in: PointsAdjustmentRequest, transaction_type: TransactionType) -> UserPoints:
        """
        Adjusts a user's points balance and records a transaction.
        Used for EARN (positive change) or ADJUST (positive/negative change).
        """
        if transaction_type == TransactionType.REDEEM:
            raise BadRequestException(detail="Use 'redeem_reward' for redemption transactions.")

        db_user_points = await get_or_create_user_points(self.db, user_id)
        new_balance = db_user_points.points_balance + adjustment_in.points_change

        if new_balance < 0:
            await self.db.rollback()
            raise BadRequestException(detail="Points balance cannot be negative after adjustment.")

        db_user_points.points_balance = new_balance

        try:
            await self._create_transaction(
                user_points=db_user_points,
                transaction_type=transaction_type,
                points_change=adjustment_in.points_change,
                description=adjustment_in.description
            )
            await self.db.commit()
            await self.db.refresh(db_user_points)
            logger.info(f"User {user_id} points adjusted by {adjustment_in.points_change}. New balance: {new_balance}")
            return db_user_points
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error adjusting points for user {user_id}: {e}")
            raise ServiceException(status_code=500, detail="Failed to adjust points due to a server error.")

    async def redeem_reward(self, user_id: int, redemption_in: RewardRedemptionRequest) -> RewardTransaction:
        """Handles the redemption of a reward."""
        reward_service = RewardService(self.db)
        db_reward = await reward_service.get_reward(redemption_in.reward_id)

        if not db_reward.is_active:
            raise ForbiddenException(detail=f"Reward '{db_reward.name}' is currently inactive.")

        db_user_points = await get_user_points_model(self.db, user_id)
        if not db_user_points:
            raise NotFoundException(detail=f"User with ID {user_id} has no points record.")

        cost = db_reward.points_cost
        points_change = -cost # Redemption is a negative change

        if db_user_points.points_balance < cost:
            raise BadRequestException(detail=f"Insufficient points. Required: {cost}, Available: {db_user_points.points_balance}")

        # Perform the transaction
        db_user_points.points_balance -= cost

        try:
            db_transaction = await self._create_transaction(
                user_points=db_user_points,
                transaction_type=TransactionType.REDEEM,
                points_change=points_change,
                description=f"Redeemed reward: {db_reward.name}",
                reward_id=db_reward.id
            )
            await self.db.commit()
            await self.db.refresh(db_user_points)
            logger.info(f"User {user_id} redeemed reward {db_reward.id} for {cost} points. New balance: {db_user_points.points_balance}")
            return db_transaction
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error redeeming reward for user {user_id}: {e}")
            raise ServiceException(status_code=500, detail="Failed to redeem reward due to a server error.")

    async def list_user_transactions(self, user_id: int, skip: int = 0, limit: int = 100) -> List[RewardTransaction]:
        db_user_points = await get_user_points_model(self.db, user_id)
        if not db_user_points:
            return [] # Return empty list if user has no points record

        stmt = (
            select(RewardTransaction)
            .where(RewardTransaction.user_points_id == db_user_points.id)
            .offset(skip)
            .limit(limit)
            .order_by(RewardTransaction.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())