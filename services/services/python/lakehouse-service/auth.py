"""
Authentication and Authorization Module for Lakehouse API
Implements JWT-based authentication with role-based access control (RBAC)
"""

import os
import jwt
import bcrypt
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from enum import Enum
from functools import wraps

from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

# ============================================================================
# CONFIGURATION
# ============================================================================

# In production, use environment variables
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("JWT_SECRET_KEY env var is required")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60  # 1 hour
REFRESH_TOKEN_EXPIRE_DAYS = 7  # 7 days

# ============================================================================
# ENUMS AND MODELS
# ============================================================================

class UserRole(str, Enum):
    """User roles for RBAC"""
    ADMIN = "admin"              # Full access to everything
    DATA_ENGINEER = "data_engineer"  # Can create tables, run pipelines
    ANALYST = "analyst"          # Read-only access to analytics
    VIEWER = "viewer"            # Read-only access to catalog

class User(BaseModel):
    """User model"""
    user_id: str
    username: str
    email: str
    role: UserRole
    is_active: bool = True
    created_at: datetime
    last_login: Optional[datetime] = None

class UserInDB(User):
    """User model with hashed password"""
    hashed_password: str

class LoginRequest(BaseModel):
    """Login request model"""
    username: str
    password: str

class TokenResponse(BaseModel):
    """Token response model"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: Dict[str, Any]

class TokenData(BaseModel):
    """Token payload data"""
    user_id: str
    username: str
    role: UserRole
    exp: datetime

# ============================================================================
# SECURITY
# ============================================================================

security = HTTPBearer()

# ============================================================================
# USER DATABASE (In production, use PostgreSQL/Redis)
# ============================================================================

class UserDatabase:
    """User database backed by environment-configured credentials"""
    
    def __init__(self):
        self.users: Dict[str, UserInDB] = {}
        self._init_users_from_env()
    
    def _init_users_from_env(self):
        """Initialize users from environment variables.
        
        Expected env vars per user: LAKEHOUSE_USER_{IDX}_USERNAME, _PASSWORD, _EMAIL, _ROLE
        Example: LAKEHOUSE_USER_0_USERNAME=admin, LAKEHOUSE_USER_0_PASSWORD=..., etc.
        """
        idx = 0
        while True:
            prefix = f"LAKEHOUSE_USER_{idx}"
            username = os.getenv(f"{prefix}_USERNAME")
            if not username:
                break
            password = os.getenv(f"{prefix}_PASSWORD", "")
            email = os.getenv(f"{prefix}_EMAIL", f"{username}@agentbanking.com")
            role_str = os.getenv(f"{prefix}_ROLE", "viewer")
            try:
                role = UserRole(role_str)
            except ValueError:
                role = UserRole.VIEWER

            hashed_password = self._hash_password(password)
            user = UserInDB(
                user_id=f"user-{idx:03d}",
                username=username,
                email=email,
                role=role,
                hashed_password=hashed_password,
                created_at=datetime.utcnow()
            )
            self.users[user.username] = user
            idx += 1
    
    def _hash_password(self, password: str) -> str:
        """Hash password using bcrypt"""
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    def _verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    
    def get_user(self, username: str) -> Optional[UserInDB]:
        """Get user by username"""
        return self.users.get(username)
    
    def authenticate_user(self, username: str, password: str) -> Optional[UserInDB]:
        """Authenticate user with username and password"""
        user = self.get_user(username)
        if not user:
            return None
        if not self._verify_password(password, user.hashed_password):
            return None
        if not user.is_active:
            return None
        return user

# Global user database
user_db = UserDatabase()

# ============================================================================
# JWT TOKEN FUNCTIONS
# ============================================================================

def create_access_token(user: UserInDB) -> str:
    """Create JWT access token"""
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    payload = {
        "user_id": user.user_id,
        "username": user.username,
        "role": user.role.value,
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access"
    }
    
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token

def create_refresh_token(user: UserInDB) -> str:
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
) -> User:
    """
    Dependency to get current authenticated user from JWT token
    Usage: current_user: User = Depends(get_current_user)
    """
    token = credentials.credentials
    
    try:
        payload = decode_token(token)
        
        # Verify token type
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        
        # Get user from database
        username = payload.get("username")
        user = user_db.get_user(username)
        
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        
        if not user.is_active:
            raise HTTPException(status_code=401, detail="User is inactive")
        
        # Return user without password
        return User(**user.dict(exclude={"hashed_password"}))
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Could not validate credentials: {str(e)}")

async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Dependency to get current active user
    Usage: current_user: User = Depends(get_current_active_user)
    """
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

# ============================================================================
# ROLE-BASED ACCESS CONTROL (RBAC)
# ============================================================================

class RoleChecker:
    """Check if user has required role"""
    
    def __init__(self, allowed_roles: List[UserRole]):
        self.allowed_roles = allowed_roles
    
    def __call__(self, current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Access denied. Required roles: {[r.value for r in self.allowed_roles]}"
            )
        return current_user

# Predefined role checkers
require_admin = RoleChecker([UserRole.ADMIN])
require_data_engineer = RoleChecker([UserRole.ADMIN, UserRole.DATA_ENGINEER])
require_analyst = RoleChecker([UserRole.ADMIN, UserRole.DATA_ENGINEER, UserRole.ANALYST])
require_any_role = RoleChecker([UserRole.ADMIN, UserRole.DATA_ENGINEER, UserRole.ANALYST, UserRole.VIEWER])

# ============================================================================
# AUTHENTICATION FUNCTIONS
# ============================================================================

async def login(login_request: LoginRequest) -> TokenResponse:
    """
    Authenticate user and return JWT tokens
    """
    # Authenticate user
    user = user_db.authenticate_user(login_request.username, login_request.password)
    
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password"
        )
    
    # Create tokens
    access_token = create_access_token(user)
    refresh_token = create_refresh_token(user)
    
    # Update last login
    user.last_login = datetime.utcnow()
    
    # Return response
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # in seconds
        user={
            "user_id": user.user_id,
            "username": user.username,
            "email": user.email,
            "role": user.role.value
        }
    )

async def refresh_access_token(refresh_token: str) -> TokenResponse:
    """
    Refresh access token using refresh token
    """
    try:
        payload = decode_token(refresh_token)
        
        # Verify token type
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        
        # Get user
        username = payload.get("username")
        user = user_db.get_user(username)
        
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        # Create new tokens
        new_access_token = create_access_token(user)
        new_refresh_token = create_refresh_token(user)
        
        return TokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user={
                "user_id": user.user_id,
                "username": user.username,
                "email": user.email,
                "role": user.role.value
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Could not refresh token: {str(e)}")

# ============================================================================
# AUDIT LOGGING
# ============================================================================

async def log_access(
    user: User,
    endpoint: str,
    action: str,
    resource: Optional[str] = None,
    status: str = "success"
):
    """
    Log user access for audit trail
    In production, write to database or logging service
    """
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "user_id": user.user_id,
        "username": user.username,
        "role": user.role.value,
        "endpoint": endpoint,
        "action": action,
        "resource": resource,
        "status": status
    }
    
    # In production, write to database
    print(f"[AUDIT] {log_entry}")
    
    return log_entry

