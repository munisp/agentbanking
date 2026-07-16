"""
Shared Authentication and Security Module for Communication Services
Provides JWT authentication, rate limiting, logging, and security utilities
"""

from fastapi import HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from slowapi import Limiter
from slowapi.util import get_remote_address
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
from enum import Enum
import jwt
import logging
from logging.handlers import RotatingFileHandler
import os
import hashlib
import hmac

# ==================== CONFIGURATION ====================

class Config:
    JWT_SECRET = os.getenv("JWT_SECRET")
    if not JWT_SECRET:
        raise RuntimeError("JWT_SECRET env var is required")

    JWT_ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 30
    REFRESH_TOKEN_EXPIRE_DAYS = 7
    
    # Rate limiting
    RATE_LIMIT_SEND_MESSAGE = os.getenv("RATE_LIMIT_SEND", "10/minute")
    RATE_LIMIT_WEBHOOK = os.getenv("RATE_LIMIT_WEBHOOK", "100/minute")
    RATE_LIMIT_GENERAL = os.getenv("RATE_LIMIT_GENERAL", "60/minute")
    
    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_DIR = os.getenv("LOG_DIR", "/var/log/communication-services")
    
    # Webhook security
    WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
    if not WEBHOOK_SECRET:
        raise RuntimeError("WEBHOOK_SECRET env var is required")

config = Config()

# ==================== ENUMS ====================

class UserRole(str, Enum):
    ADMIN = "admin"
    SERVICE = "service"
    AGENT = "agent"
    CUSTOMER = "customer"

# ==================== MODELS ====================

class User(BaseModel):
    user_id: str
    email: str
    role: UserRole
    permissions: List[str]
    
class TokenData(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

# ==================== LOGGING SETUP ====================

def setup_logging(service_name: str) -> logging.Logger:
    """Setup logging with rotation for a communication service"""
    os.makedirs(config.LOG_DIR, exist_ok=True)
    
    logger = logging.getLogger(service_name)
    logger.setLevel(getattr(logging, config.LOG_LEVEL))
    
    # File handler with rotation
    file_handler = RotatingFileHandler(
        f"{config.LOG_DIR}/{service_name}.log",
        maxBytes=10485760,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(logging.INFO)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# ==================== RATE LIMITING ====================

limiter = Limiter(key_func=get_remote_address)

def get_rate_limit(endpoint_type: str) -> str:
    """Get rate limit for specific endpoint type"""
    limits = {
        "send_message": config.RATE_LIMIT_SEND_MESSAGE,
        "webhook": config.RATE_LIMIT_WEBHOOK,
        "general": config.RATE_LIMIT_GENERAL
    }
    return limits.get(endpoint_type, config.RATE_LIMIT_GENERAL)

# ==================== JWT AUTHENTICATION ====================

security = HTTPBearer()

def create_access_token(user: User) -> str:
    """Create JWT access token"""
    payload = {
        "user_id": user.user_id,
        "email": user.email,
        "role": user.role,
        "permissions": user.permissions,
        "exp": datetime.utcnow() + timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES),
        "type": "access"
    }
    return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)

def create_refresh_token(user: User) -> str:
    """Create JWT refresh token"""
    payload = {
        "user_id": user.user_id,
        "exp": datetime.utcnow() + timedelta(days=config.REFRESH_TOKEN_EXPIRE_DAYS),
        "type": "refresh"
    }
    return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)

def create_tokens(user: User) -> TokenData:
    """Create both access and refresh tokens"""
    access_token = create_access_token(user)
    refresh_token = create_refresh_token(user)
    
    return TokenData(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=config.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )

def verify_token(token: str) -> User:
    """Verify JWT token and return user"""
    try:
        payload = jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
        
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        
        return User(
            user_id=payload["user_id"],
            email=payload["email"],
            role=payload["role"],
            permissions=payload["permissions"]
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> User:
    """Get current authenticated user from JWT token"""
    return verify_token(credentials.credentials)

def require_permission(permission: str):
    """Decorator to require specific permission"""
    async def permission_checker(user: User = Depends(get_current_user)):
        if permission not in user.permissions and "admin:all" not in user.permissions:
            raise HTTPException(
                status_code=403,
                detail=f"Permission denied: {permission}"
            )
        return user
    return permission_checker

def require_role(role: UserRole):
    """Decorator to require specific role"""
    async def role_checker(user: User = Depends(get_current_user)):
        if user.role != role and user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=403,
                detail=f"Role required: {role}"
            )
        return user
    return role_checker

# ==================== WEBHOOK SECURITY ====================

def generate_webhook_signature(payload: str) -> str:
    """Generate HMAC signature for webhook payload"""
    return hmac.new(
        config.WEBHOOK_SECRET.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()

def verify_webhook_signature(payload: str, signature: str) -> bool:
    """Verify webhook signature"""
    expected_signature = generate_webhook_signature(payload)
    return hmac.compare_digest(signature, expected_signature)

async def verify_webhook_request(request: Request) -> bool:
    """Verify incoming webhook request"""
    signature = request.headers.get("X-Webhook-Signature")
    if not signature:
        raise HTTPException(status_code=401, detail="Missing webhook signature")
    
    body = await request.body()
    payload = body.decode()
    
    if not verify_webhook_signature(payload, signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    
    return True

# ==================== PERMISSIONS ====================

class Permissions:
    """Standard permissions for communication services"""
    
    # Message permissions
    SEND_MESSAGE = "message:send"
    READ_MESSAGE = "message:read"
    DELETE_MESSAGE = "message:delete"
    
    # Channel permissions
    MANAGE_CHANNELS = "channel:manage"
    VIEW_CHANNELS = "channel:view"
    
    # Webhook permissions
    MANAGE_WEBHOOKS = "webhook:manage"
    RECEIVE_WEBHOOKS = "webhook:receive"
    
    # Analytics permissions
    VIEW_ANALYTICS = "analytics:view"
    EXPORT_DATA = "analytics:export"
    
    # Admin permissions
    ADMIN_ALL = "admin:all"

# ==================== ROLE PERMISSIONS ====================

ROLE_PERMISSIONS = {
    UserRole.ADMIN: [Permissions.ADMIN_ALL],
    UserRole.SERVICE: [
        Permissions.SEND_MESSAGE,
        Permissions.READ_MESSAGE,
        Permissions.VIEW_CHANNELS,
        Permissions.RECEIVE_WEBHOOKS
    ],
    UserRole.AGENT: [
        Permissions.SEND_MESSAGE,
        Permissions.READ_MESSAGE,
        Permissions.VIEW_CHANNELS,
        Permissions.VIEW_ANALYTICS
    ],
    UserRole.CUSTOMER: [
        Permissions.SEND_MESSAGE,
        Permissions.READ_MESSAGE
    ]
}

def get_role_permissions(role: UserRole) -> List[str]:
    """Get default permissions for a role"""
    return ROLE_PERMISSIONS.get(role, [])

# ==================== UTILITIES ====================

def sanitize_phone_number(phone: str) -> str:
    """Sanitize and format phone number"""
    # Remove all non-digit characters
    digits = ''.join(filter(str.isdigit, phone))
    
    # Add country code if missing (assuming Nigeria +234)
    if len(digits) == 10:
        digits = "234" + digits
    elif len(digits) == 11 and digits.startswith("0"):
        digits = "234" + digits[1:]
    
    return digits

def mask_sensitive_data(data: str, visible_chars: int = 4) -> str:
    """Mask sensitive data for logging"""
    if len(data) <= visible_chars:
        return "*" * len(data)
    return "*" * (len(data) - visible_chars) + data[-visible_chars:]

def log_message_sent(logger: logging.Logger, channel: str, recipient: str, message_id: str):
    """Log message sent event"""
    logger.info(
        f"Message sent - Channel: {channel}, "
        f"Recipient: {mask_sensitive_data(recipient)}, "
        f"Message ID: {message_id}"
    )

def log_message_failed(logger: logging.Logger, channel: str, recipient: str, error: str):
    """Log message failed event"""
    logger.error(
        f"Message failed - Channel: {channel}, "
        f"Recipient: {mask_sensitive_data(recipient)}, "
        f"Error: {error}"
    )

def log_webhook_received(logger: logging.Logger, channel: str, event_type: str):
    """Log webhook received event"""
    logger.info(f"Webhook received - Channel: {channel}, Event: {event_type}")

# ==================== EXAMPLE USAGE ====================

"""
Example usage in a communication service:

from communication_shared.auth_security import (
    setup_logging, limiter, get_current_user, 
    require_permission, Permissions, log_message_sent
)

# Setup logging
logger = setup_logging("whatsapp-service")

# Add rate limiting to FastAPI app
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Protected endpoint with authentication and rate limiting
@app.post("/send")
@limiter.limit("10/minute")
async def send_message(
    request: Request,
    message: MessageRequest,
    user: User = Depends(require_permission(Permissions.SEND_MESSAGE))
):
    try:
        # Send message logic
        message_id = send_whatsapp_message(message)
        
        # Log success
        log_message_sent(logger, "whatsapp", message.recipient, message_id)
        
        return {"message_id": message_id, "status": "sent"}
    except Exception as e:
        # Log failure
        log_message_failed(logger, "whatsapp", message.recipient, str(e))
        raise HTTPException(status_code=500, detail=str(e))
"""

