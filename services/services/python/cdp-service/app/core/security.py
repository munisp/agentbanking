"""
Security Utilities
JWT token management, password hashing, etc.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict
from jose import JWTError, jwt
from passlib.context import CryptContext
import secrets
import hashlib

from app.core.config import settings

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt
    
    Args:
        password: Plain text password
        
    Returns:
        Hashed password
    """
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against a hash
    
    Args:
        plain_password: Plain text password
        hashed_password: Hashed password
        
    Returns:
        True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: Dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create JWT access token
    
    Args:
        data: Data to encode in token
        expires_delta: Token expiration time
        
    Returns:
        JWT token string
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "jti": secrets.token_urlsafe(32)
    })
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )
    
    return encoded_jwt

def create_refresh_token(user_id: int) -> str:
    """
    Create JWT refresh token
    
    Args:
        user_id: User ID
        
    Returns:
        JWT refresh token string
    """
    data = {
        "sub": str(user_id),
        "type": "refresh"
    }
    
    expires_delta = timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    
    return create_access_token(data, expires_delta)

def decode_token(token: str) -> Dict:
    """
    Decode and verify JWT token
    
    Args:
        token: JWT token string
        
    Returns:
        Decoded token payload
        
    Raises:
        JWTError: If token is invalid or expired
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError as e:
        raise JWTError(f"Invalid token: {str(e)}")

def generate_otp() -> str:
    """
    Generate cryptographically secure OTP
    
    Returns:
        6-digit OTP string
    """
    otp = secrets.randbelow(1000000)
    return f"{otp:06d}"

def hash_otp(otp: str, salt: str) -> str:
    """
    Hash OTP with salt using PBKDF2
    
    Args:
        otp: OTP string
        salt: Salt string
        
    Returns:
        Hashed OTP
    """
    return hashlib.pbkdf2_hmac(
        'sha256',
        otp.encode('utf-8'),
        salt.encode('utf-8'),
        100000  # iterations
    ).hex()

def verify_otp(otp: str, hashed_otp: str, salt: str) -> bool:
    """
    Verify OTP against hash (constant-time comparison)
    
    Args:
        otp: Plain OTP
        hashed_otp: Hashed OTP
        salt: Salt used for hashing
        
    Returns:
        True if OTP matches, False otherwise
    """
    computed_hash = hash_otp(otp, salt)
    return secrets.compare_digest(computed_hash, hashed_otp)

def generate_salt() -> str:
    """
    Generate random salt for OTP hashing
    
    Returns:
        Random salt string
    """
    return secrets.token_hex(16)
