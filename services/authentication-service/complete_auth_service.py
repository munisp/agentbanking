"""
Complete Authentication Service
Implements: JWT, MFA, Sessions, Password Reset, API Keys
"""

from fastapi import FastAPI, HTTPException, Depends, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, validator
from typing import Optional, List, Dict
from datetime import datetime, timedelta
import jwt
import bcrypt
import pyotp
import qrcode
import io
import base64
import secrets
import hashlib
import redis
import asyncpg
from enum import Enum
import logging

# Configuration from environment variables - NO hardcoded secrets
import os

JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise ValueError("JWT_SECRET environment variable is required - cannot start without it")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
RESET_TOKEN_EXPIRE_HOURS = int(os.getenv("RESET_TOKEN_EXPIRE_HOURS", "24"))
SESSION_EXPIRE_HOURS = int(os.getenv("SESSION_EXPIRE_HOURS", "24"))

# Initialize
app = FastAPI(title="Complete Authentication Service")
security = HTTPBearer()
logger = logging.getLogger(__name__)

# Redis for sessions - from environment
REDIS_HOST = os.getenv("REDIS_HOST")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")
if not REDIS_HOST:
    raise ValueError("REDIS_HOST environment variable is required")
redis_client = redis.Redis(
    host=REDIS_HOST, 
    port=REDIS_PORT, 
    password=REDIS_PASSWORD,
    decode_responses=True
)

# Database connection pool
db_pool = None

# Models
class UserRole(str, Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    AGENT = "agent"
    CUSTOMER = "customer"
    VIEWER = "viewer"

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    role: UserRole = UserRole.CUSTOMER
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain digit')
        return v

class UserLogin(BaseModel):
    username: str
    password: str
    mfa_code: Optional[str] = None

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

class MFASetup(BaseModel):
    secret: str
    qr_code: str
    backup_codes: List[str]

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordReset(BaseModel):
    token: str
    new_password: str

class APIKeyCreate(BaseModel):
    name: str
    expires_days: Optional[int] = 365
    scopes: List[str] = []

class SessionInfo(BaseModel):
    session_id: str
    user_id: str
    created_at: datetime
    expires_at: datetime
    ip_address: str
    user_agent: str

# Database initialization
async def init_db():
    global db_pool
    
    # Get configuration from environment variables - NO hardcoded defaults
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT", "5432")
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_name = os.getenv("DB_NAME", "remittance")
    
    if not all([db_host, db_user, db_password]):
        raise ValueError(
            "Database configuration missing. Set DB_HOST, DB_USER, DB_PASSWORD environment variables"
        )
    
    db_pool = await asyncpg.create_pool(
        host=db_host,
        port=int(db_port),
        database=db_name,
        user=db_user,
        password=db_password,
        min_size=5,
        max_size=20
    )
    
    # Create tables
    async with db_pool.acquire() as conn:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(255) UNIQUE NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(50) NOT NULL,
                mfa_enabled BOOLEAN DEFAULT FALSE,
                mfa_secret VARCHAR(255),
                backup_codes TEXT[],
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                last_login TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE
            )
        ''')
        
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                token VARCHAR(255) UNIQUE NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                used BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS api_keys (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                name VARCHAR(255) NOT NULL,
                key_hash VARCHAR(255) UNIQUE NOT NULL,
                key_prefix VARCHAR(20) NOT NULL,
                scopes TEXT[],
                expires_at TIMESTAMP,
                last_used TIMESTAMP,
                created_at TIMESTAMP DEFAULT NOW(),
                is_active BOOLEAN DEFAULT TRUE
            )
        ''')
        
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS refresh_tokens (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                token_hash VARCHAR(255) UNIQUE NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                revoked BOOLEAN DEFAULT FALSE
            )
        ''')

# Helper functions
def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    """Verify password against hash"""
    return bcrypt.checkpw(password.encode(), hashed.encode())

def create_access_token(user_id: int, username: str, role: str) -> str:
    """Create JWT access token"""
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "type": "access",
        "exp": datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def create_refresh_token(user_id: int) -> str:
    """Create JWT refresh token"""
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "exp": datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_token(token: str) -> Dict:
    """Verify and decode JWT token"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current user from JWT token"""
    token = credentials.credentials
    payload = verify_token(token)
    
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")
    
    user_id = int(payload.get("sub"))
    
    async with db_pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT * FROM users WHERE id = $1 AND is_active = TRUE",
            user_id
        )
        
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        return dict(user)

def generate_mfa_secret() -> str:
    """Generate MFA secret"""
    return pyotp.random_base32()

def generate_qr_code(username: str, secret: str) -> str:
    """Generate QR code for MFA setup"""
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(username, issuer_name="Remittance Platform")
    
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(uri)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    
    return base64.b64encode(buffer.getvalue()).decode()

def generate_backup_codes(count: int = 10) -> List[str]:
    """Generate backup codes for MFA"""
    return [secrets.token_hex(4).upper() for _ in range(count)]

def verify_mfa_code(secret: str, code: str) -> bool:
    """Verify MFA code"""
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)

def create_session(user_id: int, ip_address: str, user_agent: str) -> str:
    """Create user session"""
    session_id = secrets.token_urlsafe(32)
    session_data = {
        "user_id": user_id,
        "created_at": datetime.utcnow().isoformat(),
        "ip_address": ip_address,
        "user_agent": user_agent
    }
    
    # Store in Redis with expiration
    redis_client.setex(
        f"session:{session_id}",
        SESSION_EXPIRE_HOURS * 3600,
        str(session_data)
    )
    
    return session_id

def generate_api_key() -> tuple:
    """Generate API key"""
    key = f"abp_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(key.encode()).hexdigest()
    key_prefix = key[:12]
    return key, key_hash, key_prefix

# API Endpoints

@app.on_event("startup")
async def startup():
    await init_db()

@app.on_event("shutdown")
async def shutdown():
    if db_pool:
        await db_pool.close()

@app.post("/register", response_model=TokenResponse)
async def register(user: UserCreate):
    """Register new user"""
    async with db_pool.acquire() as conn:
        # Check if user exists
        existing = await conn.fetchrow(
            "SELECT id FROM users WHERE username = $1 OR email = $2",
            user.username, user.email
        )
        
        if existing:
            raise HTTPException(status_code=400, detail="User already exists")
        
        # Create user
        password_hash = hash_password(user.password)
        user_id = await conn.fetchval(
            """
            INSERT INTO users (username, email, password_hash, role)
            VALUES ($1, $2, $3, $4)
            RETURNING id
            """,
            user.username, user.email, password_hash, user.role.value
        )
        
        # Generate tokens
        access_token = create_access_token(user_id, user.username, user.role.value)
        refresh_token = create_refresh_token(user_id)
        
        # Store refresh token
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        await conn.execute(
            """
            INSERT INTO refresh_tokens (user_id, token_hash, expires_at)
            VALUES ($1, $2, $3)
            """,
            user_id, token_hash,
            datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        )
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )

@app.post("/login", response_model=TokenResponse)
async def login(
    credentials: UserLogin,
    x_forwarded_for: Optional[str] = Header(None),
    user_agent: Optional[str] = Header(None)
):
    """Login user"""
    async with db_pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT * FROM users WHERE username = $1 AND is_active = TRUE",
            credentials.username
        )
        
        if not user or not verify_password(credentials.password, user['password_hash']):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        # Check MFA if enabled
        if user['mfa_enabled']:
            if not credentials.mfa_code:
                raise HTTPException(status_code=401, detail="MFA code required")
            
            if not verify_mfa_code(user['mfa_secret'], credentials.mfa_code):
                # Check backup codes
                if credentials.mfa_code not in (user['backup_codes'] or []):
                    raise HTTPException(status_code=401, detail="Invalid MFA code")
                
                # Remove used backup code
                backup_codes = list(user['backup_codes'])
                backup_codes.remove(credentials.mfa_code)
                await conn.execute(
                    "UPDATE users SET backup_codes = $1 WHERE id = $2",
                    backup_codes, user['id']
                )
        
        # Update last login
        await conn.execute(
            "UPDATE users SET last_login = NOW() WHERE id = $1",
            user['id']
        )
        
        # Create session
        session_id = create_session(
            user['id'],
            x_forwarded_for or "unknown",
            user_agent or "unknown"
        )
        
        # Generate tokens
        access_token = create_access_token(user['id'], user['username'], user['role'])
        refresh_token = create_refresh_token(user['id'])
        
        # Store refresh token
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        await conn.execute(
            """
            INSERT INTO refresh_tokens (user_id, token_hash, expires_at)
            VALUES ($1, $2, $3)
            """,
            user['id'], token_hash,
            datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        )
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )

@app.post("/refresh", response_model=TokenResponse)
async def refresh_token(refresh_token: str):
    """Refresh access token"""
    payload = verify_token(refresh_token)
    
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")
    
    user_id = int(payload.get("sub"))
    token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
    
    async with db_pool.acquire() as conn:
        # Verify refresh token
        token_record = await conn.fetchrow(
            """
            SELECT * FROM refresh_tokens
            WHERE token_hash = $1 AND user_id = $2 AND revoked = FALSE
            AND expires_at > NOW()
            """,
            token_hash, user_id
        )
        
        if not token_record:
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        
        # Get user
        user = await conn.fetchrow(
            "SELECT * FROM users WHERE id = $1 AND is_active = TRUE",
            user_id
        )
        
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        # Generate new tokens
        access_token = create_access_token(user['id'], user['username'], user['role'])
        new_refresh_token = create_refresh_token(user['id'])
        
        # Revoke old refresh token
        await conn.execute(
            "UPDATE refresh_tokens SET revoked = TRUE WHERE id = $1",
            token_record['id']
        )
        
        # Store new refresh token
        new_token_hash = hashlib.sha256(new_refresh_token.encode()).hexdigest()
        await conn.execute(
            """
            INSERT INTO refresh_tokens (user_id, token_hash, expires_at)
            VALUES ($1, $2, $3)
            """,
            user_id, new_token_hash,
            datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        )
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )

@app.post("/mfa/setup", response_model=MFASetup)
async def setup_mfa(current_user: dict = Depends(get_current_user)):
    """Setup MFA for user"""
    secret = generate_mfa_secret()
    qr_code = generate_qr_code(current_user['username'], secret)
    backup_codes = generate_backup_codes()
    
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE users
            SET mfa_secret = $1, backup_codes = $2
            WHERE id = $3
            """,
            secret, backup_codes, current_user['id']
        )
    
    return MFASetup(
        secret=secret,
        qr_code=qr_code,
        backup_codes=backup_codes
    )

@app.post("/mfa/enable")
async def enable_mfa(
    mfa_code: str,
    current_user: dict = Depends(get_current_user)
):
    """Enable MFA after verification"""
    if not current_user['mfa_secret']:
        raise HTTPException(status_code=400, detail="MFA not setup")
    
    if not verify_mfa_code(current_user['mfa_secret'], mfa_code):
        raise HTTPException(status_code=400, detail="Invalid MFA code")
    
    async with db_pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET mfa_enabled = TRUE WHERE id = $1",
            current_user['id']
        )
    
    return {"message": "MFA enabled successfully"}

@app.post("/mfa/disable")
async def disable_mfa(
    password: str,
    current_user: dict = Depends(get_current_user)
):
    """Disable MFA"""
    if not verify_password(password, current_user['password_hash']):
        raise HTTPException(status_code=401, detail="Invalid password")
    
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE users
            SET mfa_enabled = FALSE, mfa_secret = NULL, backup_codes = NULL
            WHERE id = $1
            """,
            current_user['id']
        )
    
    return {"message": "MFA disabled successfully"}

@app.post("/password/reset-request")
async def request_password_reset(request: PasswordResetRequest):
    """Request password reset"""
    async with db_pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT id, email FROM users WHERE email = $1",
            request.email
        )
        
        if not user:
            # Don't reveal if email exists
            return {"message": "If email exists, reset link will be sent"}
        
        # Generate reset token
        token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(hours=RESET_TOKEN_EXPIRE_HOURS)
        
        await conn.execute(
            """
            INSERT INTO password_reset_tokens (user_id, token, expires_at)
            VALUES ($1, $2, $3)
            """,
            user['id'], token, expires_at
        )
        
        # Send email with reset link
        try:
            import requests
            email_service_url = os.getenv('EMAIL_SERVICE_URL', 'http://localhost:8001')
            reset_link = f"{os.getenv('FRONTEND_URL', 'http://localhost:3000')}/reset-password?token={token}"
            requests.post(f"{email_service_url}/api/v1/email/send", json={
                "to": request.email,
                "subject": "Password Reset Request",
                "body": f"Click this link to reset your password: {reset_link}\n\nThis link expires in 1 hour."
            }, timeout=5)
        except Exception as e:
            logger.error(f"Failed to send password reset email: {e}")
        logger.info(f"Password reset token for {request.email}: {token}")
        
        return {"message": "If email exists, reset link will be sent"}

@app.post("/password/reset")
async def reset_password(reset: PasswordReset):
    """Reset password using token"""
    async with db_pool.acquire() as conn:
        token_record = await conn.fetchrow(
            """
            SELECT * FROM password_reset_tokens
            WHERE token = $1 AND used = FALSE AND expires_at > NOW()
            """,
            reset.token
        )
        
        if not token_record:
            raise HTTPException(status_code=400, detail="Invalid or expired token")
        
        # Update password
        password_hash = hash_password(reset.new_password)
        await conn.execute(
            "UPDATE users SET password_hash = $1, updated_at = NOW() WHERE id = $2",
            password_hash, token_record['user_id']
        )
        
        # Mark token as used
        await conn.execute(
            "UPDATE password_reset_tokens SET used = TRUE WHERE id = $1",
            token_record['id']
        )
        
        # Revoke all refresh tokens
        await conn.execute(
            "UPDATE refresh_tokens SET revoked = TRUE WHERE user_id = $1",
            token_record['user_id']
        )
        
        return {"message": "Password reset successfully"}

@app.post("/api-keys", response_model=dict)
async def create_api_key(
    key_create: APIKeyCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create API key"""
    key, key_hash, key_prefix = generate_api_key()
    
    expires_at = None
    if key_create.expires_days:
        expires_at = datetime.utcnow() + timedelta(days=key_create.expires_days)
    
    async with db_pool.acquire() as conn:
        key_id = await conn.fetchval(
            """
            INSERT INTO api_keys (user_id, name, key_hash, key_prefix, scopes, expires_at)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id
            """,
            current_user['id'], key_create.name, key_hash, key_prefix,
            key_create.scopes, expires_at
        )
    
    return {
        "id": key_id,
        "key": key,  # Only shown once
        "prefix": key_prefix,
        "name": key_create.name,
        "expires_at": expires_at
    }

@app.get("/api-keys")
async def list_api_keys(current_user: dict = Depends(get_current_user)):
    """List user's API keys"""
    async with db_pool.acquire() as conn:
        keys = await conn.fetch(
            """
            SELECT id, name, key_prefix, scopes, expires_at, last_used, created_at, is_active
            FROM api_keys
            WHERE user_id = $1
            ORDER BY created_at DESC
            """,
            current_user['id']
        )
        
        return [dict(key) for key in keys]

@app.delete("/api-keys/{key_id}")
async def revoke_api_key(
    key_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Revoke API key"""
    async with db_pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE api_keys
            SET is_active = FALSE
            WHERE id = $1 AND user_id = $2
            """,
            key_id, current_user['id']
        )
        
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="API key not found")
        
        return {"message": "API key revoked"}

@app.get("/sessions")
async def list_sessions(current_user: dict = Depends(get_current_user)):
    """List user's active sessions"""
    # Get all sessions from Redis
    sessions = []
    for key in redis_client.scan_iter(f"session:*"):
        session_data = eval(redis_client.get(key))
        if session_data.get('user_id') == current_user['id']:
            sessions.append({
                "session_id": key.split(':')[1],
                **session_data
            })
    
    return sessions

@app.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Revoke session"""
    session_key = f"session:{session_id}"
    session_data = redis_client.get(session_key)
    
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session_data = eval(session_data)
    if session_data.get('user_id') != current_user['id']:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    redis_client.delete(session_key)
    return {"message": "Session revoked"}

@app.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    """Get current user info"""
    user_info = {
        "id": current_user['id'],
        "username": current_user['username'],
        "email": current_user['email'],
        "role": current_user['role'],
        "mfa_enabled": current_user['mfa_enabled'],
        "created_at": current_user['created_at'],
        "last_login": current_user['last_login']
    }
    return user_info

@app.get("/health")
async def health_check():
    """Health check"""
    return {
        "status": "healthy",
        "service": "authentication",
        "timestamp": datetime.utcnow().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)

