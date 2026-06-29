from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Index
from sqlalchemy.orm import relationship
from database import Base

class Configuration(Base):
    """
    SQLAlchemy Model for a Configuration setting.
    """
    __tablename__ = "configurations"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True, nullable=False)
    value = Column(Text, nullable=False)
    type = Column(String, default="string", nullable=False) # e.g., 'string', 'integer', 'boolean', 'json'
    is_active = Column(Boolean, default=True, nullable=False)
    description = Column(String, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationship to history
    history = relationship("ConfigurationHistory", back_populates="configuration", cascade="all, delete-orphan")

    __table_args__ = (
        # Enforce uniqueness on key for fast lookups
        Index("ix_config_key_unique", key, unique=True),
    )

    def __repr__(self):
        return f"<Configuration(key='{self.key}', value='{self.value}', type='{self.type}')>"

class ConfigurationHistory(Base):
    """
    SQLAlchemy Model for tracking changes to a Configuration setting.
    """
    __tablename__ = "configuration_history"

    id = Column(Integer, primary_key=True, index=True)
    config_id = Column(Integer, ForeignKey("configurations.id"), nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=False)
    changed_by = Column(String, default="system", nullable=False) # Production implementation for user/system who made the change
    changed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationship to configuration
    configuration = relationship("Configuration", back_populates="history")

    def __repr__(self):
        return f"<ConfigurationHistory(config_id={self.config_id}, changed_at='{self.changed_at}')>"