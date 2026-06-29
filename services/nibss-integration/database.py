from typing import Any, Dict, List, Optional, Union, Tuple

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base

from config import settings
from models import Base

# Create the SQLAlchemy engine
engine = create_engine(
    settings.DATABASE_URL, 
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
    pool_pre_ping=True
)

# Create a configured "Session" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dependency to get the database session
def get_db() -> None:
    """
    Dependency function that yields a new SQLAlchemy session for each request.
    It ensures the session is closed after the request is finished.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Function to create all tables in the database
def init_db() -> None:
    """
    Initializes the database by creating all tables defined in models.py.
    """
    Base.metadata.create_all(bind=engine)

# Optional: Function to populate initial data (e.g., Bank list)
def populate_banks(db: Session) -> None:
    """
    Populates the Bank table with a sample list of banks.
    In a real-world scenario, this list would be loaded from a trusted source.
    """
    from models import Bank
    
    # Sample NIBSS bank codes and names
    sample_banks = [
        {"bank_code": "044", "bank_name": "Access Bank Plc"},
        {"bank_code": "058", "bank_name": "Guaranty Trust Bank Plc"},
        {"bank_code": "033", "bank_name": "United Bank for Africa Plc"},
        {"bank_code": "050", "bank_name": "Ecobank Nigeria Plc"},
        {"bank_code": "070", "bank_name": "First Bank of Nigeria Plc"},
    ]
    
    for bank_data in sample_banks:
        if not db.query(Bank).filter(Bank.bank_code == bank_data["bank_code"]).first():
            db.add(Bank(**bank_data))
    
    db.commit()
    print("Sample banks populated.")

if __name__ == "__main__":
    # Example usage for local development
    init_db()
    db = SessionLocal()
    populate_banks(db)
    db.close()
