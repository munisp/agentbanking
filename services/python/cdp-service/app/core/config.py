"""
Configuration Management
"""

from pydantic_settings import BaseSettings
from typing import List
import os

class Settings(BaseSettings):
    """Application settings"""
    
    # Application
    APP_NAME: str = "Nigerian Remittance Platform - CDP Service"
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    APP_URL: str = "http://localhost:8000"
    FRONTEND_URL: str = "http://localhost:3000"
    
    # Database
    DATABASE_URL: str = "postgresql://user:pass@localhost:5432/remittance"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_PASSWORD: str = ""
    
    # JWT
    JWT_SECRET_KEY: str = "your_super_secret_jwt_key_min_32_characters_long"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Coinbase CDP
    CDP_PROJECT_ID: str = ""
    CDP_API_KEY: str = ""
    CDP_API_SECRET: str = ""
    CDP_NETWORK: str = "base-sepolia"  # or base-mainnet
    CDP_WEBHOOK_SECRET: str = ""
    
    # Base Network
    BASE_RPC_URL: str = "https://sepolia.base.org"
    BASE_CHAIN_ID: int = 84532  # Sepolia testnet
    ADMIN_WALLET_ADDRESS: str = ""
    ADMIN_WALLET_PRIVATE_KEY: str = ""
    ESCROW_CONTRACT_ADDRESS: str = ""
    
    # Email
    SMTP_HOST: str = "smtp.sendgrid.net"
    SMTP_PORT: int = 587
    SMTP_USER: str = "apikey"
    SMTP_PASSWORD: str = ""
    EMAIL_FROM: str = "noreply@remittance.com"
    
    # SMS
    SMS_PROVIDER: str = "twilio"
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_PHONE_NUMBER: str = ""
    
    # Storage
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "af-south-1"
    AWS_S3_BUCKET: str = "remittance-documents"
    
    # Monitoring
    SENTRY_DSN: str = ""
    LOG_LEVEL: str = "INFO"
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_PER_HOUR: int = 1000
    
    # Security
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8080"]
    ALLOWED_HOSTS: List[str] = ["localhost", "127.0.0.1"]
    
    # OTP
    OTP_LENGTH: int = 6
    OTP_EXPIRY_MINUTES: int = 10
    OTP_MAX_ATTEMPTS: int = 3
    OTP_RATE_LIMIT_PER_MINUTE: int = 3
    
    # Transaction Limits (in Naira)
    TIER_0_DAILY_LIMIT: int = 10000
    TIER_1_DAILY_LIMIT: int = 50000
    TIER_2_DAILY_LIMIT: int = 500000
    TIER_3_DAILY_LIMIT: int = 5000000
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
