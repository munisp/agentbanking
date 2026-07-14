from sqlalchemy import create_engine, Column, String, DateTime, Boolean, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime

from .config import settings

DATABASE_URL = settings.database_url

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class EdgeDevice(Base):
    __tablename__ = "edge_devices"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, index=True)
    location = Column(String)
    status = Column(String, default="offline") # e.g., 'online', 'offline', 'deploying'
    last_seen = Column(DateTime, default=datetime.datetime.utcnow)
    is_active = Column(Boolean, default=True)
    firmware_version = Column(String)
    deployed_config_version = Column(String, nullable=True)

class Deployment(Base):
    __tablename__ = "deployments"

    id = Column(String, primary_key=True, index=True)
    device_id = Column(String, index=True)
    config_version = Column(String)
    status = Column(String, default="pending") # e.g., 'pending', 'in_progress', 'completed', 'failed'
    initiated_at = Column(DateTime, default=datetime.datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    details = Column(String, nullable=True)


def create_db_and_tables():
    Base.metadata.create_all(engine)



class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    email = Column(String, unique=True, index=True)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)

