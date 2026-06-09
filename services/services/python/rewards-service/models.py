"""
Rewards Service Models
Database models for rewards service
"""

from sqlalchemy import Column, String, DateTime, Integer, Float, Boolean, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import uuid

Base = declarative_base()

class RewardsService(Base):
    """
    Rewards Service model
    """
    __tablename__ = "rewards_service"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    status = Column(String, default="active", nullable=False)
    
    user_id = Column(String(50), nullable=False)
    points = Column(Integer, default=0)
    tier = Column(String(20), default="bronze")
    
    def __repr__(self):
        return f"<RewardsService(id={self.id})>"
