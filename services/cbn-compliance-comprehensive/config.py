import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from service import Base

# Accepts DATABASE_URI (set by Helm/k8s) or CBN_COMPLIANCE_DATABASE_URL (legacy override)
DATABASE_URL = (
    os.environ.get("CBN_COMPLIANCE_DATABASE_URL")
    or os.environ.get("DATABASE_URI")
    or "sqlite:///./cbn_compliance.db"
)
TRAINING_SVC_URL = os.environ.get("TRAINING_SVC_URL", "http://agent-training-academy")

# NFIU portal — required for SAR transmission; service will refuse to submit without these.
NFIU_PORTAL_URL = os.environ.get("NFIU_PORTAL_URL", "")
NFIU_API_KEY = os.environ.get("NFIU_API_KEY", "")
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
