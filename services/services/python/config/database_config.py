"""
Centralized Database Configuration

This module provides environment-based database configuration for all Python services.
No hardcoded credentials - all values come from environment variables.
"""

import os
from typing import Optional
from dataclasses import dataclass


@dataclass
class DatabaseConfig:
    """Database configuration from environment variables"""
    host: str
    port: int
    database: str
    user: str
    password: str
    ssl_mode: str = "prefer"
    pool_min_size: int = 5
    pool_max_size: int = 20
    command_timeout: int = 30
    
    @property
    def url(self) -> str:
        """Get PostgreSQL connection URL"""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}?sslmode={self.ssl_mode}"
    
    @property
    def async_url(self) -> str:
        """Get async PostgreSQL connection URL"""
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
    
    @property
    def sync_url(self) -> str:
        """Get sync PostgreSQL connection URL"""
        return f"postgresql+psycopg2://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


@dataclass
class RedisConfig:
    """Redis configuration from environment variables"""
    host: str
    port: int
    password: Optional[str] = None
    db: int = 0
    ssl: bool = False
    
    @property
    def url(self) -> str:
        """Get Redis connection URL"""
        auth = f":{self.password}@" if self.password else ""
        protocol = "rediss" if self.ssl else "redis"
        return f"{protocol}://{auth}{self.host}:{self.port}/{self.db}"


def get_database_config() -> DatabaseConfig:
    """Get database configuration from environment variables"""
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        from urllib.parse import urlparse
        parsed = urlparse(database_url)
        return DatabaseConfig(
            host=parsed.hostname or "localhost",
            port=parsed.port or 5432,
            database=parsed.path.lstrip("/") if parsed.path else "remittance",
            user=parsed.username or "postgres",
            password=parsed.password or "",
            ssl_mode=os.getenv("DB_SSL_MODE", "prefer"),
            pool_min_size=int(os.getenv("DB_POOL_MIN", "5")),
            pool_max_size=int(os.getenv("DB_POOL_MAX", "20")),
            command_timeout=int(os.getenv("DB_COMMAND_TIMEOUT", "30"))
        )
    
    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT")
    database = os.getenv("DB_NAME")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    
    if not all([host, user, password]):
        raise ValueError(
            "Database configuration missing. Set DATABASE_URL or individual env vars: "
            "DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD"
        )
    
    return DatabaseConfig(
        host=host,
        port=int(port) if port else 5432,
        database=database or "remittance",
        user=user,
        password=password,
        ssl_mode=os.getenv("DB_SSL_MODE", "prefer"),
        pool_min_size=int(os.getenv("DB_POOL_MIN", "5")),
        pool_max_size=int(os.getenv("DB_POOL_MAX", "20")),
        command_timeout=int(os.getenv("DB_COMMAND_TIMEOUT", "30"))
    )


def get_redis_config() -> RedisConfig:
    """Get Redis configuration from environment variables"""
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        from urllib.parse import urlparse
        parsed = urlparse(redis_url)
        return RedisConfig(
            host=parsed.hostname or "localhost",
            port=parsed.port or 6379,
            password=parsed.password,
            db=int(parsed.path.lstrip("/")) if parsed.path and parsed.path != "/" else 0,
            ssl=parsed.scheme == "rediss"
        )
    
    host = os.getenv("REDIS_HOST")
    if not host:
        raise ValueError(
            "Redis configuration missing. Set REDIS_URL or individual env vars: "
            "REDIS_HOST, REDIS_PORT, REDIS_PASSWORD, REDIS_DB"
        )
    
    return RedisConfig(
        host=host,
        port=int(os.getenv("REDIS_PORT", "6379")),
        password=os.getenv("REDIS_PASSWORD"),
        db=int(os.getenv("REDIS_DB", "0")),
        ssl=os.getenv("REDIS_SSL", "false").lower() == "true"
    )


def get_kafka_config() -> dict:
    """Get Kafka configuration from environment variables"""
    brokers = os.getenv("KAFKA_BROKERS")
    if not brokers:
        raise ValueError("KAFKA_BROKERS environment variable not set")
    
    return {
        "bootstrap_servers": brokers,
        "security_protocol": os.getenv("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT"),
        "sasl_mechanism": os.getenv("KAFKA_SASL_MECHANISM"),
        "sasl_username": os.getenv("KAFKA_SASL_USERNAME"),
        "sasl_password": os.getenv("KAFKA_SASL_PASSWORD"),
    }


def get_tigerbeetle_config() -> dict:
    """Get TigerBeetle configuration from environment variables"""
    addresses = os.getenv("TIGERBEETLE_ADDRESSES")
    if not addresses:
        raise ValueError("TIGERBEETLE_ADDRESSES environment variable not set")
    
    return {
        "addresses": addresses,
        "cluster_id": int(os.getenv("TIGERBEETLE_CLUSTER_ID", "0")),
    }


def validate_required_env_vars(required_vars: list) -> None:
    """Validate that required environment variables are set"""
    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
