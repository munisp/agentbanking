from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from utils.config import get_config

config = get_config()

engine = create_engine(
    config.DATABASE_URI, 
    pool_pre_ping=True,  # Checks if connections are alive before using them
    pool_size=10,  # Number of connections to keep in the pool
    max_overflow=20,  # Number of connections to allow in overflow
    pool_timeout=30,  # Time to wait before giving up on getting a connection from the pool
    pool_recycle=1800,  # Recycle connections after this many seconds
)

SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_session():
    session = SessionFactory()

    try:
        yield session
    finally:
        session.close()