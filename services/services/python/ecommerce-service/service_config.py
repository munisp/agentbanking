"""
Service Configuration Module
Centralized configuration for all e-commerce and inventory services
Replaces hardcoded localhost URLs with environment-based configuration
"""

import os
from dataclasses import dataclass, field
from typing import Optional
from functools import lru_cache


@dataclass
class DatabaseConfig:
    """Database configuration"""
    host: str = field(default_factory=lambda: os.getenv("DB_HOST", "localhost"))
    port: int = field(default_factory=lambda: int(os.getenv("DB_PORT", "5432")))
    database: str = field(default_factory=lambda: os.getenv("DB_NAME", "remittance"))
    user: str = field(default_factory=lambda: os.getenv("DB_USER", "postgres"))
    password: str = field(default_factory=lambda: os.getenv("DB_PASSWORD", ""))
    
    @property
    def url(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
    
    @property
    def async_url(self) -> str:
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


@dataclass
class RedisConfig:
    """Redis configuration"""
    host: str = field(default_factory=lambda: os.getenv("REDIS_HOST", "localhost"))
    port: int = field(default_factory=lambda: int(os.getenv("REDIS_PORT", "6379")))
    db: int = field(default_factory=lambda: int(os.getenv("REDIS_DB", "0")))
    password: Optional[str] = field(default_factory=lambda: os.getenv("REDIS_PASSWORD"))
    
    @property
    def url(self) -> str:
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"


@dataclass
class ServiceEndpoints:
    """Service endpoint configuration - replaces hardcoded localhost URLs"""
    
    # Core services
    payment_service: str = field(default_factory=lambda: os.getenv(
        "PAYMENT_SERVICE_URL", "http://payment-service:8000"))
    email_service: str = field(default_factory=lambda: os.getenv(
        "EMAIL_SERVICE_URL", "http://email-service:8001"))
    notification_service: str = field(default_factory=lambda: os.getenv(
        "NOTIFICATION_SERVICE_URL", "http://notification-service:8002"))
    
    # E-commerce services
    product_catalog: str = field(default_factory=lambda: os.getenv(
        "PRODUCT_CATALOG_URL", "http://product-catalog:8082"))
    inventory_service: str = field(default_factory=lambda: os.getenv(
        "INVENTORY_SERVICE_URL", "http://inventory-service:8084"))
    order_service: str = field(default_factory=lambda: os.getenv(
        "ORDER_SERVICE_URL", "http://order-service:8085"))
    checkout_service: str = field(default_factory=lambda: os.getenv(
        "CHECKOUT_SERVICE_URL", "http://checkout-service:8086"))
    
    # Supply chain services
    supply_chain: str = field(default_factory=lambda: os.getenv(
        "SUPPLY_CHAIN_URL", "http://supply-chain-service:9000"))
    logistics_service: str = field(default_factory=lambda: os.getenv(
        "LOGISTICS_SERVICE_URL", "http://logistics-service:9001"))
    warehouse_service: str = field(default_factory=lambda: os.getenv(
        "WAREHOUSE_SERVICE_URL", "http://warehouse-service:9002"))
    
    # Integration services
    qr_code_service: str = field(default_factory=lambda: os.getenv(
        "QR_CODE_SERVICE_URL", "http://qr-code-service:8032"))
    payment_gateway: str = field(default_factory=lambda: os.getenv(
        "PAYMENT_GATEWAY_URL", "http://payment-gateway:8015"))
    
    # Carrier APIs
    fedex_api: str = field(default_factory=lambda: os.getenv(
        "FEDEX_API_URL", "https://apis.fedex.com"))
    ups_api: str = field(default_factory=lambda: os.getenv(
        "UPS_API_URL", "https://onlinetools.ups.com"))
    dhl_api: str = field(default_factory=lambda: os.getenv(
        "DHL_API_URL", "https://api.dhl.com"))
    gig_logistics_api: str = field(default_factory=lambda: os.getenv(
        "GIG_LOGISTICS_API_URL", "https://api.giglogistics.com"))
    
    # Frontend URLs
    frontend_url: str = field(default_factory=lambda: os.getenv(
        "FRONTEND_URL", "http://localhost:3000"))
    success_url: str = field(default_factory=lambda: os.getenv(
        "PAYMENT_SUCCESS_URL", "http://localhost:3000/success"))
    cancel_url: str = field(default_factory=lambda: os.getenv(
        "PAYMENT_CANCEL_URL", "http://localhost:3000/cancel"))


@dataclass
class KafkaConfig:
    """Kafka configuration"""
    bootstrap_servers: str = field(default_factory=lambda: os.getenv(
        "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"))
    consumer_group: str = field(default_factory=lambda: os.getenv(
        "KAFKA_CONSUMER_GROUP", "ecommerce-service"))
    
    # Topics
    inventory_events_topic: str = "inventory.events"
    order_events_topic: str = "order.events"
    payment_events_topic: str = "payment.events"
    notification_events_topic: str = "notification.events"


@dataclass
class TemporalConfig:
    """Temporal workflow configuration"""
    host: str = field(default_factory=lambda: os.getenv("TEMPORAL_HOST", "localhost"))
    port: int = field(default_factory=lambda: int(os.getenv("TEMPORAL_PORT", "7233")))
    namespace: str = field(default_factory=lambda: os.getenv("TEMPORAL_NAMESPACE", "default"))
    task_queue: str = field(default_factory=lambda: os.getenv("TEMPORAL_TASK_QUEUE", "ecommerce-tasks"))
    
    @property
    def address(self) -> str:
        return f"{self.host}:{self.port}"


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration"""
    failure_threshold: int = 5
    recovery_timeout: int = 30  # seconds
    half_open_requests: int = 3


@dataclass
class InventoryConfig:
    """Inventory-specific configuration"""
    reservation_timeout_minutes: int = field(default_factory=lambda: int(os.getenv(
        "INVENTORY_RESERVATION_TIMEOUT", "15")))
    sync_interval_seconds: int = field(default_factory=lambda: int(os.getenv(
        "INVENTORY_SYNC_INTERVAL", "300")))
    low_stock_threshold: int = field(default_factory=lambda: int(os.getenv(
        "LOW_STOCK_THRESHOLD", "10")))
    batch_size: int = field(default_factory=lambda: int(os.getenv(
        "INVENTORY_BATCH_SIZE", "100")))


@dataclass
class ServiceConfig:
    """Main service configuration"""
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)
    endpoints: ServiceEndpoints = field(default_factory=ServiceEndpoints)
    kafka: KafkaConfig = field(default_factory=KafkaConfig)
    temporal: TemporalConfig = field(default_factory=TemporalConfig)
    circuit_breaker: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)
    inventory: InventoryConfig = field(default_factory=InventoryConfig)


@lru_cache()
def get_config() -> ServiceConfig:
    """Get cached service configuration"""
    return ServiceConfig()


# Convenience function for getting endpoints
def get_endpoints() -> ServiceEndpoints:
    """Get service endpoints configuration"""
    return get_config().endpoints
