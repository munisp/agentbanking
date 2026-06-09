"""
Database Configuration
Production-ready PostgreSQL connection settings
"""

from typing import Any, Dict, List, Optional, Union, Tuple

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager

class DatabaseConfig:
    """Database configuration"""
    
    # Connection settings
    DB_HOST = os.getenv('POSTGRES_HOST', 'localhost')
    DB_PORT = os.getenv('POSTGRES_PORT', '5432')
    DB_NAME = os.getenv('POSTGRES_DB', 'remittance')
    DB_USER = os.getenv('POSTGRES_USER', 'postgres')
    DB_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'secure_password')
    
    # SSL settings
    DB_SSL_MODE = os.getenv('POSTGRES_SSL_MODE', 'require')
    DB_SSL_ROOT_CERT = os.getenv('POSTGRES_SSL_ROOT_CERT', None)
    
    # Pool settings
    POOL_SIZE = int(os.getenv('DB_POOL_SIZE', '10'))
    MAX_OVERFLOW = int(os.getenv('DB_MAX_OVERFLOW', '20'))
    POOL_TIMEOUT = int(os.getenv('DB_POOL_TIMEOUT', '30'))
    POOL_RECYCLE = int(os.getenv('DB_POOL_RECYCLE', '3600'))
    
    # Connection string
    @classmethod
    def get_connection_string(cls, async_driver=False) -> None:
        """Get database connection string"""
        driver = 'postgresql+asyncpg' if async_driver else 'postgresql+psycopg2'
        
        conn_str = f"{driver}://{cls.DB_USER}:{cls.DB_PASSWORD}@{cls.DB_HOST}:{cls.DB_PORT}/{cls.DB_NAME}"
        
        if cls.DB_SSL_MODE and cls.DB_SSL_MODE != 'disable':
            conn_str += f"?sslmode={cls.DB_SSL_MODE}"
            if cls.DB_SSL_ROOT_CERT:
                conn_str += f"&sslrootcert={cls.DB_SSL_ROOT_CERT}"
        
        return conn_str

class DatabaseManager:
    """Database connection manager with pooling"""
    
    def __init__(self) -> None:
        self.engine = None
        self.Session = None
    
    def initialize(self) -> None:
        """Initialize database connection pool"""
        connection_string = DatabaseConfig.get_connection_string()
        
        self.engine = create_engine(
            connection_string,
            poolclass=QueuePool,
            pool_size=DatabaseConfig.POOL_SIZE,
            max_overflow=DatabaseConfig.MAX_OVERFLOW,
            pool_timeout=DatabaseConfig.POOL_TIMEOUT,
            pool_recycle=DatabaseConfig.POOL_RECYCLE,
            pool_pre_ping=True,  # Verify connections before using
            echo=False  # Set to True for SQL logging
        )
        
        self.Session = scoped_session(sessionmaker(bind=self.engine))
        
        print(f"✅ Database connection pool initialized")
        print(f"   Pool size: {DatabaseConfig.POOL_SIZE}")
        print(f"   Max overflow: {DatabaseConfig.MAX_OVERFLOW}")
    
    @contextmanager
    def get_session(self) -> None:
        """Get database session with automatic cleanup"""
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def health_check(self) -> bool:
        """Check database connection health"""
        try:
            with self.get_session() as session:
                session.execute("SELECT 1")
            return True
        except Exception as e:
            print(f"❌ Database health check failed: {e}")
            return False
    
    def close(self) -> None:
        """Close all database connections"""
        if self.Session:
            self.Session.remove()
        if self.engine:
            self.engine.dispose()
        print("✅ Database connections closed")

# Global database manager instance
db_manager = DatabaseManager()
