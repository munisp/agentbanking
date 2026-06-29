"""
Secure POS Authentication Module
JWT-based authentication with RBAC for POS system
"""

import os
import jwt
import bcrypt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from enum import Enum

from fastapi import HTTPException, Security, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

SECRET_KEY = os.getenv("POS_JWT_SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("POS_JWT_SECRET_KEY env var is required")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30  # Short-lived for security
REFRESH_TOKEN_EXPIRE_DAYS = 7

security = HTTPBearer()

# ============================================================================
# ENUMS
# ============================================================================

class POSUserRole(str, Enum):
    """POS user roles with hierarchical permissions"""
    SUPER_ADMIN = "super_admin"      # Full system access
    MERCHANT_ADMIN = "merchant_admin"  # Merchant-level admin
    TERMINAL_OPERATOR = "terminal_operator"  # Can process payments
    CASHIER = "cashier"              # Basic payment processing
    VIEWER = "viewer"                # Read-only access

class POSPermission(str, Enum):
    """Granular permissions for POS operations"""
    PROCESS_PAYMENT = "process_payment"
    REFUND_PAYMENT = "refund_payment"
    VIEW_TRANSACTIONS = "view_transactions"
    MANAGE_DEVICES = "manage_devices"
    MANAGE_TERMINALS = "manage_terminals"
    MANAGE_MERCHANTS = "manage_merchants"
    VIEW_ANALYTICS = "view_analytics"
    CONFIGURE_SYSTEM = "configure_system"

# Role-Permission mapping
ROLE_PERMISSIONS: Dict[POSUserRole, List[POSPermission]] = {
    POSUserRole.SUPER_ADMIN: [
        POSPermission.PROCESS_PAYMENT,
        POSPermission.REFUND_PAYMENT,
        POSPermission.VIEW_TRANSACTIONS,
        POSPermission.MANAGE_DEVICES,
        POSPermission.MANAGE_TERMINALS,
        POSPermission.MANAGE_MERCHANTS,
        POSPermission.VIEW_ANALYTICS,
        POSPermission.CONFIGURE_SYSTEM,
    ],
    POSUserRole.MERCHANT_ADMIN: [
        POSPermission.PROCESS_PAYMENT,
        POSPermission.REFUND_PAYMENT,
        POSPermission.VIEW_TRANSACTIONS,
        POSPermission.MANAGE_DEVICES,
        POSPermission.MANAGE_TERMINALS,
        POSPermission.VIEW_ANALYTICS,
    ],
    POSUserRole.TERMINAL_OPERATOR: [
        POSPermission.PROCESS_PAYMENT,
        POSPermission.REFUND_PAYMENT,
        POSPermission.VIEW_TRANSACTIONS,
    ],
    POSUserRole.CASHIER: [
        POSPermission.PROCESS_PAYMENT,
        POSPermission.VIEW_TRANSACTIONS,
    ],
    POSUserRole.VIEWER: [
        POSPermission.VIEW_TRANSACTIONS,
        POSPermission.VIEW_ANALYTICS,
    ],
}

# ============================================================================
# MODELS
# ============================================================================

class POSUser(BaseModel):
    """POS user model"""
    user_id: str
    username: str
    email: str
    role: POSUserRole
    merchant_id: Optional[str] = None
    terminal_ids: List[str] = []
    is_active: bool = True
    created_at: datetime
    last_login: Optional[datetime] = None

class LoginRequest(BaseModel):
    """Login request"""
    username: str
    password: str
    terminal_id: Optional[str] = None

class TokenResponse(BaseModel):
    """Token response"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: POSUser

# ============================================================================
# PASSWORD HASHING (Secure with bcrypt)
# ============================================================================

class PasswordHasher:
    """Secure password hashing using bcrypt"""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password with bcrypt"""
        salt = bcrypt.gensalt(rounds=12)  # 12 rounds for good security
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        try:
            return bcrypt.checkpw(
                plain_password.encode('utf-8'),
                hashed_password.encode('utf-8')
            )
        except Exception:
            return False

# ============================================================================
# JWT TOKEN FUNCTIONS
# ============================================================================

def create_access_token(user: POSUser) -> str:
    """Create JWT access token"""
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    payload = {
        "user_id": user.user_id,
        "username": user.username,
        "role": user.role.value,
        "merchant_id": user.merchant_id,
        "terminal_ids": user.terminal_ids,
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access"
    }
    
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token

def create_refresh_token(user: POSUser) -> str:
    """Create JWT refresh token"""
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    
    payload = {
        "user_id": user.user_id,
        "username": user.username,
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "refresh"
    }
    
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token

def decode_token(token: str) -> Dict[str, Any]:
    """Decode and verify JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

# ============================================================================
# AUTHENTICATION DEPENDENCIES
# ============================================================================

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> POSUser:
    """
    Dependency to get current authenticated user from JWT token
    """
    token = credentials.credentials
    
    try:
        payload = decode_token(token)
        
        # Verify token type
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        
        # Create user object from token
        user = POSUser(
            user_id=payload['user_id'],
            username=payload['username'],
            email=f"{payload['username']}@pos.system",  # Would come from DB
            role=POSUserRole(payload['role']),
            merchant_id=payload.get('merchant_id'),
            terminal_ids=payload.get('terminal_ids', []),
            is_active=True,
            created_at=datetime.utcnow()
        )
        
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(status_code=401, detail="Could not validate credentials")

# ============================================================================
# AUTHORIZATION (RBAC)
# ============================================================================

class PermissionChecker:
    """Check if user has required permission"""
    
    def __init__(self, required_permission: POSPermission):
        self.required_permission = required_permission
    
    async def __call__(self, current_user: POSUser = Depends(get_current_user)) -> POSUser:
        """Check if user has permission"""
        user_permissions = ROLE_PERMISSIONS.get(current_user.role, [])
        
        if self.required_permission not in user_permissions:
            raise HTTPException(
                status_code=403,
                detail=f"Permission denied. Required: {self.required_permission.value}"
            )
        
        return current_user

class RoleChecker:
    """Check if user has required role"""
    
    def __init__(self, allowed_roles: List[POSUserRole]):
        self.allowed_roles = allowed_roles
    
    async def __call__(self, current_user: POSUser = Depends(get_current_user)) -> POSUser:
        """Check if user has required role"""
        if current_user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Access denied. Required roles: {[r.value for r in self.allowed_roles]}"
            )
        
        return current_user

class MerchantAccessChecker:
    """Check if user has access to specific merchant"""
    
    async def __call__(
        self,
        merchant_id: str,
        current_user: POSUser = Depends(get_current_user)
    ) -> POSUser:
        """Check merchant access"""
        # Super admin has access to all merchants
        if current_user.role == POSUserRole.SUPER_ADMIN:
            return current_user
        
        # Check if user belongs to this merchant
        if current_user.merchant_id != merchant_id:
            raise HTTPException(
                status_code=403,
                detail="Access denied to this merchant"
            )
        
        return current_user

class TerminalAccessChecker:
    """Check if user has access to specific terminal"""
    
    async def __call__(
        self,
        terminal_id: str,
        current_user: POSUser = Depends(get_current_user)
    ) -> POSUser:
        """Check terminal access"""
        # Super admin and merchant admin have access to all terminals
        if current_user.role in [POSUserRole.SUPER_ADMIN, POSUserRole.MERCHANT_ADMIN]:
            return current_user
        
        # Check if user has access to this terminal
        if terminal_id not in current_user.terminal_ids:
            raise HTTPException(
                status_code=403,
                detail="Access denied to this terminal"
            )
        
        return current_user

# ============================================================================
# PREDEFINED PERMISSION CHECKERS
# ============================================================================

# Permission-based access
require_process_payment = PermissionChecker(POSPermission.PROCESS_PAYMENT)
require_refund_payment = PermissionChecker(POSPermission.REFUND_PAYMENT)
require_view_transactions = PermissionChecker(POSPermission.VIEW_TRANSACTIONS)
require_manage_devices = PermissionChecker(POSPermission.MANAGE_DEVICES)
require_manage_terminals = PermissionChecker(POSPermission.MANAGE_TERMINALS)
require_manage_merchants = PermissionChecker(POSPermission.MANAGE_MERCHANTS)
require_view_analytics = PermissionChecker(POSPermission.VIEW_ANALYTICS)
require_configure_system = PermissionChecker(POSPermission.CONFIGURE_SYSTEM)

# Role-based access
require_super_admin = RoleChecker([POSUserRole.SUPER_ADMIN])
require_merchant_admin = RoleChecker([POSUserRole.SUPER_ADMIN, POSUserRole.MERCHANT_ADMIN])
require_operator = RoleChecker([
    POSUserRole.SUPER_ADMIN,
    POSUserRole.MERCHANT_ADMIN,
    POSUserRole.TERMINAL_OPERATOR
])

# ============================================================================
# USER STORE (loaded from environment / external DB in production)
# ============================================================================

def _load_pos_users() -> Dict[str, Dict[str, Any]]:
    """Load POS users from environment variables.
    
    Expected env vars per user: POS_USER_{IDX}_USERNAME, _PASSWORD, _EMAIL, _ROLE, _MERCHANT_ID, _TERMINAL_IDS
    """
    users: Dict[str, Dict[str, Any]] = {}
    idx = 0
    while True:
        prefix = f"POS_USER_{idx}"
        username = os.getenv(f"{prefix}_USERNAME")
        if not username:
            break
        password = os.getenv(f"{prefix}_PASSWORD", "")
        email = os.getenv(f"{prefix}_EMAIL", f"{username}@pos.system")
        role_str = os.getenv(f"{prefix}_ROLE", "viewer")
        merchant_id = os.getenv(f"{prefix}_MERCHANT_ID") or None
        terminal_ids_str = os.getenv(f"{prefix}_TERMINAL_IDS", "")
        terminal_ids = [t.strip() for t in terminal_ids_str.split(",") if t.strip()] if terminal_ids_str else []
        try:
            role = POSUserRole(role_str)
        except ValueError:
            role = POSUserRole.VIEWER
        users[username] = {
            "user_id": f"user_{idx:03d}",
            "username": username,
            "email": email,
            "password_hash": PasswordHasher.hash_password(password),
            "role": role,
            "merchant_id": merchant_id,
            "terminal_ids": terminal_ids,
        }
        idx += 1
    return users

POS_USERS = _load_pos_users()

async def authenticate_user(username: str, password: str) -> Optional[POSUser]:
    """Authenticate user with username and password"""
    user_data = POS_USERS.get(username)
    
    if not user_data:
        return None
    
    if not PasswordHasher.verify_password(password, user_data['password_hash']):
        return None
    
    user = POSUser(
        user_id=user_data['user_id'],
        username=user_data['username'],
        email=user_data['email'],
        role=user_data['role'],
        merchant_id=user_data['merchant_id'],
        terminal_ids=user_data['terminal_ids'],
        is_active=True,
        created_at=datetime.utcnow(),
        last_login=datetime.utcnow()
    )
    
    return user

