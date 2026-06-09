"""
Complete Authentication Module with MFA and PostgreSQL
Production-ready authentication with JWT, MFA (TOTP), and database persistence
"""

import os
import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from enum import Enum

from fastapi import HTTPException, Security, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from database import (
    UserDatabase, RefreshTokenDatabase, AuditLogDatabase,
    UserRole, MFAMethod, init_db_pool, close_db_pool
)
from mfa import MFAManager, MFAVerifier, MFASetupResponse, MFAVerifyRequest

# ============================================================================
# CONFIGURATION
# ============================================================================

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("JWT_SECRET_KEY env var is required")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60  # 1 hour
REFRESH_TOKEN_EXPIRE_DAYS = 7  # 7 days

security = HTTPBearer()

# ============================================================================
# MODELS
# ============================================================================

class LoginRequest(BaseModel):
    """Login request model"""
    username: str
    password: str

class LoginResponse(BaseModel):
    """Login response model"""
    requires_mfa: bool
    mfa_token: Optional[str] = None  # Temporary token for MFA verification
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: Optional[int] = None
    user: Optional[Dict[str, Any]] = None

class MFALoginRequest(BaseModel):
    """MFA login request model"""
    mfa_token: str
    mfa_code: str
    use_backup_code: bool = False

class TokenResponse(BaseModel):
    """Token response model"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: Dict[str, Any]

class User(BaseModel):
    """User model (without sensitive data)"""
    user_id: str
    username: str
    email: str
    role: UserRole
    is_active: bool
    mfa_enabled: bool
    created_at: datetime
    last_login: Optional[datetime] = None

# ============================================================================
# JWT TOKEN FUNCTIONS
# ============================================================================

def create_access_token(user: Dict[str, Any]) -> str:
    """Create JWT access token"""
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    payload = {
        "user_id": str(user['user_id']),
        "username": user['username'],
        "role": user['role'],
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access"
    }
    
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token

def create_refresh_token(user: Dict[str, Any]) -> str:
    """Create JWT refresh token"""
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    
    payload = {
        "user_id": str(user['user_id']),
        "username": user['username'],
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "refresh"
    }
    
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token

def create_mfa_token(user: Dict[str, Any]) -> str:
    """Create temporary MFA token (short-lived, 5 minutes)"""
    expire = datetime.utcnow() + timedelta(minutes=5)
    
    payload = {
        "user_id": str(user['user_id']),
        "username": user['username'],
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "mfa"
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
# AUTHENTICATION FUNCTIONS
# ============================================================================

async def login(login_request: LoginRequest, request: Request) -> LoginResponse:
    """
    Authenticate user and return JWT tokens (or MFA challenge)
    """
    # Authenticate user
    user = await UserDatabase.authenticate_user(
        login_request.username,
        login_request.password
    )
    
    if not user:
        # Log failed attempt
        await AuditLogDatabase.log_action(
            user_id=None,
            username=login_request.username,
            action="login",
            success=False,
            error_message="Invalid credentials",
            ip_address=request.client.host if request.client else None
        )
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password"
        )
    
    # Check if MFA is enabled
    if user.get('mfa_enabled', False):
        # Return MFA challenge
        mfa_token = create_mfa_token(user)
        
        await AuditLogDatabase.log_action(
            user_id=str(user['user_id']),
            username=user['username'],
            action="login_mfa_required",
            success=True,
            ip_address=request.client.host if request.client else None
        )
        
        return LoginResponse(
            requires_mfa=True,
            mfa_token=mfa_token
        )
    
    # No MFA required, issue tokens
    access_token = create_access_token(user)
    refresh_token = create_refresh_token(user)
    
    # Store refresh token in database
    await RefreshTokenDatabase.store_refresh_token(
        user_id=str(user['user_id']),
        token=refresh_token,
        expires_at=datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        device_type="web",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )
    
    # Log successful login
    await AuditLogDatabase.log_action(
        user_id=str(user['user_id']),
        username=user['username'],
        action="login",
        success=True,
        ip_address=request.client.host if request.client else None
    )
    
    return LoginResponse(
        requires_mfa=False,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user={
            "user_id": str(user['user_id']),
            "username": user['username'],
            "email": user['email'],
            "role": user['role']
        }
    )

async def login_with_mfa(mfa_request: MFALoginRequest, request: Request) -> TokenResponse:
    """
    Complete login with MFA verification
    """
    # Verify MFA token
    try:
        payload = decode_token(mfa_request.mfa_token)
        if payload.get("type") != "mfa":
            raise HTTPException(status_code=401, detail="Invalid MFA token")
    except HTTPException:
        raise
    
    # Get user
    user = await UserDatabase.get_user_by_id(payload['user_id'])
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    # Verify MFA code
    mfa_verifier = MFAVerifier()
    success, error_message = await mfa_verifier.verify_code(
        user_id=str(user['user_id']),
        secret=user['mfa_secret'],
        code=mfa_request.mfa_code,
        backup_codes=user.get('mfa_backup_codes'),
        use_backup_code=mfa_request.use_backup_code,
        ip_address=request.client.host if request.client else None
    )
    
    if not success:
        await AuditLogDatabase.log_action(
            user_id=str(user['user_id']),
            username=user['username'],
            action="mfa_verification",
            success=False,
            error_message=error_message,
            ip_address=request.client.host if request.client else None
        )
        raise HTTPException(status_code=401, detail=error_message)
    
    # MFA verified, issue tokens
    access_token = create_access_token(user)
    refresh_token = create_refresh_token(user)
    
    # Store refresh token
    await RefreshTokenDatabase.store_refresh_token(
        user_id=str(user['user_id']),
        token=refresh_token,
        expires_at=datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        device_type="web",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )
    
    # Log successful login
    await AuditLogDatabase.log_action(
        user_id=str(user['user_id']),
        username=user['username'],
        action="login_with_mfa",
        success=True,
        ip_address=request.client.host if request.client else None
    )
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user={
            "user_id": str(user['user_id']),
            "username": user['username'],
            "email": user['email'],
            "role": user['role']
        }
    )

async def refresh_access_token(refresh_token: str, request: Request) -> TokenResponse:
    """
    Refresh access token using refresh token
    """
    # Verify refresh token in database
    token_data = await RefreshTokenDatabase.verify_refresh_token(refresh_token)
    
    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    
    # Get user
    user = await UserDatabase.get_user_by_id(token_data['user_id'])
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    # Create new tokens
    new_access_token = create_access_token(user)
    new_refresh_token = create_refresh_token(user)
    
    # Revoke old refresh token
    await RefreshTokenDatabase.revoke_refresh_token(refresh_token, "Token refreshed")
    
    # Store new refresh token
    await RefreshTokenDatabase.store_refresh_token(
        user_id=str(user['user_id']),
        token=new_refresh_token,
        expires_at=datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        device_type="web",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )
    
    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user={
            "user_id": str(user['user_id']),
            "username": user['username'],
            "email": user['email'],
            "role": user['role']
        }
    )

async def logout(refresh_token: str, request: Request):
    """Logout user by revoking refresh token"""
    await RefreshTokenDatabase.revoke_refresh_token(refresh_token, "User logout")

async def logout_all_devices(user_id: str, request: Request):
    """Logout user from all devices"""
    await RefreshTokenDatabase.revoke_all_user_tokens(user_id, "Logout all devices")

# ============================================================================
# MFA MANAGEMENT FUNCTIONS
# ============================================================================

async def setup_mfa_for_user(user_id: str, username: str) -> MFASetupResponse:
    """
    Setup MFA for a user
    Returns QR code and backup codes
    """
    # Generate MFA setup
    mfa_setup = MFAManager.setup_mfa(username)
    
    # Store MFA secret and backup codes in database
    backup_codes_hashed = MFAManager.hash_backup_codes(
        [code.replace('-', '') for code in mfa_setup.backup_codes]
    )
    
    await UserDatabase.enable_mfa(
        user_id=user_id,
        mfa_secret=mfa_setup.secret,
        mfa_method=MFAMethod.TOTP,
        backup_codes=backup_codes_hashed
    )
    
    return mfa_setup

async def disable_mfa_for_user(user_id: str):
    """Disable MFA for a user"""
    await UserDatabase.disable_mfa(user_id)

# ============================================================================
# AUTHENTICATION DEPENDENCIES
# ============================================================================

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> User:
    """
    Dependency to get current authenticated user from JWT token
    """
    token = credentials.credentials
    
    try:
        payload = decode_token(token)
        
        # Verify token type
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        
        # Get user from database
        user = await UserDatabase.get_user_by_id(payload['user_id'])
        
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        if not user.get('is_active', False):
            raise HTTPException(status_code=401, detail="User is inactive")
        
        # Return user model
        return User(
            user_id=str(user['user_id']),
            username=user['username'],
            email=user['email'],
            role=UserRole(user['role']),
            is_active=user['is_active'],
            mfa_enabled=user.get('mfa_enabled', False),
            created_at=user['created_at'],
            last_login=user.get('last_login')
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Could not validate credentials: {str(e)}")

# ============================================================================
# ROLE-BASED ACCESS CONTROL (RBAC)
# ============================================================================

class RoleChecker:
    """Check if user has required role"""
    
    def __init__(self, allowed_roles: list):
        self.allowed_roles = allowed_roles
    
    async def __call__(self, current_user: User = Depends(get_current_user)) -> User:
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

