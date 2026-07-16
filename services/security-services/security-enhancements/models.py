import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Index

Base = declarative_base()

class ApiKey(Base):
    """
    SQLAlchemy model for an API Key.
    """
    __tablename__ = "api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    # Storing the hash of the key, not the key itself
    key_hash = Column(String, nullable=False, unique=True, comment="SHA-256 hash of the API key")
    
    # Identifier for the owner of the key (e.g., user ID, client ID)
    owner_id = Column(String, nullable=False, index=True)
    
    name = Column(String, nullable=False, comment="Human-readable name for the key")
    
    # Scopes/permissions associated with the key
    scopes = Column(ARRAY(String), nullable=False, default=[])
    
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True, comment="Optional expiration date for the key")
    
    # Optional metadata for tracking
    metadata_json = Column(Text, nullable=True, comment="JSON string for additional metadata")

    __table_args__ = (
        # Enforce uniqueness on the combination of owner_id and name (keys must have unique names per owner)
        Index('idx_owner_name_unique', owner_id, name, unique=True),
    )

    def __repr__(self):
        return f"<ApiKey(id='{self.id}', owner_id='{self.owner_id}', name='{self.name}', is_active={self.is_active})>"