import datetime
import enum
from typing import Optional, List, Dict, Any

from sqlalchemy import Column, Integer, String, Float, DateTime, Enum, Index, JSON
from sqlalchemy.ext.declarative import declarative_base
from pydantic import BaseModel, Field

# --- SQLAlchemy Base ---

Base = declarative_base()

# --- Enums ---

class TransactionType(str, enum.Enum):
    """
    Defines the possible types of a financial transaction.
    """
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    PURCHASE = "purchase"
    REFUND = "refund"
    TRANSFER = "transfer"

class TransactionStatus(str, enum.Enum):
    """
    Defines the possible statuses of a transaction.
    """
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

# --- SQLAlchemy Models ---

class Transaction(Base):
    """
    SQLAlchemy model for a financial transaction record.
    """
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False, doc="ID of the user who initiated the transaction.")
    
    transaction_type = Column(Enum(TransactionType), nullable=False, doc="The type of the transaction (e.g., DEPOSIT, WITHDRAWAL).")
    
    amount = Column(Float, nullable=False, doc="The monetary amount of the transaction.")
    currency = Column(String(10), default="USD", nullable=False, doc="The currency of the transaction.")
    
    status = Column(Enum(TransactionStatus), default=TransactionStatus.PENDING, nullable=False, index=True, doc="The current status of the transaction.")
    
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, doc="The date and time the transaction was created.")
    
    description = Column(String, nullable=True, doc="A brief description of the transaction.")
    
    # JSON column for flexible, unstructured data (e.g., payment processor details, source/destination accounts)
    metadata_json = Column("metadata", JSON, nullable=True, doc="Unstructured JSON data for additional transaction details.")

    __table_args__ = (
        # Index for efficient searching by user and time range
        Index("idx_user_time", "user_id", "timestamp"),
    )

    def __repr__(self):
        return f"<Transaction(id={self.id}, user_id={self.user_id}, type='{self.transaction_type}', amount={self.amount}, status='{self.status}')>"

# --- Pydantic Schemas ---

# Base schema for common fields
class TransactionBase(BaseModel):
    """
    Base Pydantic schema for transaction data.
    """
    user_id: int = Field(..., description="ID of the user who initiated the transaction.")
    transaction_type: TransactionType = Field(..., description="The type of the transaction (e.g., DEPOSIT, WITHDRAWAL).")
    amount: float = Field(..., gt=0, description="The monetary amount of the transaction.")
    currency: str = Field("USD", max_length=10, description="The currency of the transaction.")
    description: Optional[str] = Field(None, max_length=255, description="A brief description of the transaction.")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Unstructured JSON data for additional transaction details.")

# Schema for creating a new transaction
class TransactionCreate(TransactionBase):
    """
    Pydantic schema for creating a new transaction.
    """
    status: TransactionStatus = Field(TransactionStatus.PENDING, description="The initial status of the transaction.")

# Schema for updating an existing transaction (e.g., status change)
class TransactionUpdate(BaseModel):
    """
    Pydantic schema for updating an existing transaction.
    """
    status: Optional[TransactionStatus] = Field(None, description="The new status of the transaction.")
    description: Optional[str] = Field(None, max_length=255, description="An updated description of the transaction.")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Updated unstructured JSON data.")

# Schema for reading a transaction from the database (response model)
class TransactionResponse(TransactionBase):
    """
    Pydantic schema for a transaction record returned to the client.
    """
    id: int = Field(..., description="Unique ID of the transaction.")
    status: TransactionStatus = Field(..., description="The current status of the transaction.")
    timestamp: datetime.datetime = Field(..., description="The date and time the transaction was created.")

    class Config:
        from_attributes = True
        json_encoders = {
            datetime.datetime: lambda dt: dt.isoformat(),
            TransactionType: lambda t: t.value,
            TransactionStatus: lambda s: s.value,
        }

# Schema for analytics response
class TransactionAnalytics(BaseModel):
    """
    Pydantic schema for transaction analytics data.
    """
    total_transactions: int
    total_amount: float
    completed_transactions: int
    failed_transactions: int
    summary_by_type: Dict[TransactionType, float]

# --- Database Initialization Utility ---

def init_db(engine):
    """
    Creates all tables defined in the Base metadata.
    """
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    # Example usage for local testing
    from config import engine
    print("Initializing database...")
    init_db(engine)
    print("Database initialization complete.")
