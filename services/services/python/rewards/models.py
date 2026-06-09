import datetime
from typing import List, Optional

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Index, BigInteger, DECIMAL
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Reward(Base):
    __tablename__ = "rewards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=True)
    points_cost: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    # Relationship to transactions (to see which transactions involved this reward)
    transactions: Mapped[List["RewardTransaction"]] = relationship("RewardTransaction", back_populates="reward")

    __table_args__ = (
        Index("ix_rewards_cost_active", "points_cost", "is_active"),
    )

class UserPoints(Base):
    __tablename__ = "user_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True) # Assuming user_id comes from an external Auth service
    points_balance: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    # Relationship to transactions
    transactions: Mapped[List["RewardTransaction"]] = relationship("RewardTransaction", back_populates="user_points")

    __table_args__ = (
        Index("ix_user_points_balance", "points_balance"),
    )

class RewardTransaction(Base):
    __tablename__ = "reward_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_points_id: Mapped[int] = mapped_column(ForeignKey("user_points.id"), nullable=False, index=True)
    reward_id: Mapped[Optional[int]] = mapped_column(ForeignKey("rewards.id"), nullable=True, index=True) # Nullable for point-earning transactions
    transaction_type: Mapped[str] = mapped_column(String(50), nullable=False) # e.g., 'EARN', 'REDEEM', 'ADJUST'
    points_change: Mapped[int] = mapped_column(BigInteger, nullable=False) # Positive for EARN, negative for REDEEM/ADJUST
    description: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # Relationships
    user_points: Mapped["UserPoints"] = relationship("UserPoints", back_populates="transactions")
    reward: Mapped[Optional["Reward"]] = relationship("Reward", back_populates="transactions")

    __table_args__ = (
        Index("ix_transactions_user_type", "user_points_id", "transaction_type"),
    )