"""
Complete Database Models for Email Service
Includes all tables for email logging, templates, and tracking
"""

from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Boolean, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
from pydantic import BaseModel, EmailStr
from typing import Optional, List

# Database connection
from .config import get_settings
settings = get_settings()
SQLALCHEMY_DATABASE_URL = settings.database_url

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- SQLAlchemy Models ---

class EmailLog(Base):
    """
    Email sending log with complete tracking
    """
    __tablename__ = "email_logs"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(String(255), unique=True, index=True, nullable=False)
    
    # Recipients
    to_addresses = Column(JSON, nullable=False)  # List of email addresses
    cc_addresses = Column(JSON, nullable=True)
    bcc_addresses = Column(JSON, nullable=True)
    
    # Content
    subject = Column(String(500), nullable=False)
    template = Column(String(100), nullable=False)
    template_data = Column(JSON, nullable=True)
    
    # Status tracking
    status = Column(String(50), default="queued", index=True)  # queued, sent, delivered, opened, clicked, bounced, failed
    priority = Column(String(20), default="normal")  # low, normal, high
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    scheduled_at = Column(DateTime, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    opened_at = Column(DateTime, nullable=True)
    clicked_at = Column(DateTime, nullable=True)
    
    # Error tracking
    bounced = Column(Boolean, default=False)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    last_retry_at = Column(DateTime, nullable=True)
    
    # Metadata
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    
    def __repr__(self):
        return f"<EmailLog(id={self.id}, message_id='{self.message_id}', status='{self.status}')>"

class EmailTemplate(Base):
    """
    Email templates for different use cases
    """
    __tablename__ = "email_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, index=True, nullable=False)
    
    # Content
    subject = Column(String(500), nullable=False)
    html_content = Column(Text, nullable=False)
    text_content = Column(Text, nullable=True)
    
    # Template metadata
    variables = Column(JSON, nullable=True)  # List of required variables
    category = Column(String(50), nullable=False, index=True)  # transactional, marketing, system
    
    # Status
    active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String(255), nullable=True)
    
    def __repr__(self):
        return f"<EmailTemplate(id={self.id}, name='{self.name}', category='{self.category}')>"

class EmailAttachment(Base):
    """
    Email attachments storage
    """
    __tablename__ = "email_attachments"

    id = Column(Integer, primary_key=True, index=True)
    email_log_id = Column(Integer, ForeignKey("email_logs.id"), nullable=False)
    
    # File info
    filename = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=False)  # bytes
    mime_type = Column(String(100), nullable=False)
    
    # Storage
    storage_path = Column(String(500), nullable=False)  # S3 path or local path
    storage_type = Column(String(20), default="s3")  # s3, local, url
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationship
    email_log = relationship("EmailLog", backref="attachments")
    
    def __repr__(self):
        return f"<EmailAttachment(id={self.id}, filename='{self.filename}')>"

class EmailClick(Base):
    """
    Track email link clicks
    """
    __tablename__ = "email_clicks"

    id = Column(Integer, primary_key=True, index=True)
    email_log_id = Column(Integer, ForeignKey("email_logs.id"), nullable=False)
    
    # Click data
    link_url = Column(String(1000), nullable=False)
    link_label = Column(String(255), nullable=True)
    
    # Tracking
    clicked_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    
    # Relationship
    email_log = relationship("EmailLog", backref="clicks")
    
    def __repr__(self):
        return f"<EmailClick(id={self.id}, url='{self.link_url}')>"

class EmailBounce(Base):
    """
    Track email bounces
    """
    __tablename__ = "email_bounces"

    id = Column(Integer, primary_key=True, index=True)
    email_log_id = Column(Integer, ForeignKey("email_logs.id"), nullable=False)
    
    # Bounce data
    bounce_type = Column(String(50), nullable=False)  # hard, soft, transient
    bounce_reason = Column(Text, nullable=True)
    bounce_code = Column(String(20), nullable=True)
    
    # Timestamps
    bounced_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationship
    email_log = relationship("EmailLog", backref="bounce_records")
    
    def __repr__(self):
        return f"<EmailBounce(id={self.id}, type='{self.bounce_type}')>"

class EmailUnsubscribe(Base):
    """
    Track email unsubscribes
    """
    __tablename__ = "email_unsubscribes"

    id = Column(Integer, primary_key=True, index=True)
    
    # Unsubscribe data
    email_address = Column(String(255), unique=True, index=True, nullable=False)
    reason = Column(Text, nullable=True)
    
    # Categories
    unsubscribe_all = Column(Boolean, default=True)
    unsubscribe_marketing = Column(Boolean, default=False)
    unsubscribe_transactional = Column(Boolean, default=False)
    
    # Timestamps
    unsubscribed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f"<EmailUnsubscribe(id={self.id}, email='{self.email_address}')>"

# --- Pydantic Schemas ---

class EmailBase(BaseModel):
    recipient_email: EmailStr
    subject: str
    body: str

class EmailCreate(EmailBase):
    pass

class EmailUpdateStatus(BaseModel):
    status: str
    retries: Optional[int] = None
    last_attempt: Optional[datetime] = None

class EmailResponse(EmailBase):
    id: int
    sender_email: str
    sent_at: datetime
    status: str
    retries: int
    last_attempt: Optional[datetime]

    class Config:
        orm_mode = True

# Function to create tables
def create_db_tables():
    """Create all database tables"""
    Base.metadata.create_all(bind=engine)

# Function to get database session
def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

