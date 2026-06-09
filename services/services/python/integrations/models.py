import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Text, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Integration(Base):
    __tablename__ = "integrations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, unique=True, nullable=False, index=True)
    type = Column(String, nullable=False) # e.g., 'PAYMENT', 'CRM', 'COMMUNICATION'
    description = Column(String, nullable=True)
    
    # Sensitive data storage - in a real app, this would be encrypted
    api_key_encrypted = Column(Text, nullable=True)
    
    # Flexible configuration storage
    config_json = Column(JSON, nullable=True)
    
    is_active = Column(Boolean, default=True, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationship to logs
    logs = relationship("IntegrationLog", back_populates="integration", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Integration(name='{self.name}', type='{self.type}', is_active={self.is_active})>"

class IntegrationLog(Base):
    __tablename__ = "integration_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    integration_id = Column(UUID(as_uuid=True), ForeignKey("integrations.id"), nullable=False, index=True)
    
    endpoint = Column(String, nullable=False)
    method = Column(String, nullable=False) # e.g., 'GET', 'POST'
    status_code = Column(String, nullable=False)
    
    request_body = Column(JSON, nullable=True)
    response_body = Column(JSON, nullable=True)
    
    is_success = Column(Boolean, nullable=False)
    error_message = Column(Text, nullable=True)
    
    logged_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationship back to integration
    integration = relationship("Integration", back_populates="logs")

    def __repr__(self):
        return f"<IntegrationLog(integration_id='{self.integration_id}', endpoint='{self.endpoint}', success={self.is_success})>"
