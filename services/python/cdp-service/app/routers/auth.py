import logging
import os
import random
import time
from datetime import datetime, timedelta, timezone
from typing import Annotated, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, Field, EmailStr, constr
import jwt  # Migrated from python-jose (CVE-2024-33663) to PyJWT
from jwt.exceptions import InvalidTokenError as JWTError
from passlib.context import CryptContext
from starlette.responses import JSONResponse

# --- Configuration and Constants ---

# In a real application, these would be loaded from environment variables or a secure vault
SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "super-secret-key-for-testing-only-change-in-prod")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7
OTP_EXPIRE_SECONDS = 300  # 5 minutes
RATE_LIMIT_SECONDS = 60  # 1 minute cooldown for OTP requests

# Mock database/cache for user data, OTPs, and rate limiting
# In production, this would be Redis or a proper database
MOCK_DB = {
    "user@example.com": {"id": 1, "email": "user@example.com", "is_active": True},
}
OTP_CACHE: Dict[str, Dict[str, Any]] = {}
RATE_LIMIT_CACHE: Dict[str, float] = {}

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Password hashing context (not strictly needed for OTP but good practice for user management)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme for token dependency
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

# --- Pydantic Schemas ---

class SendOtpRequest(BaseModel):
    """Schema for requesting an OTP."""
    email: EmailStr = Field(..., description="User's email address.")

class VerifyOtpRequest(BaseModel):
    """Schema for verifying an OTP."""
    email: EmailStr = Field(..., description="User's email address.")
    otp: constr(min_length=6, max_length=6) = Field(..., description="The 6-digit OTP received.")

class TokenResponse(BaseModel):
    """Schema for returning JWT tokens."""
    access_token: str = Field(..., description="The short-lived access token.")
    refresh_token: str = Field(..., description="The long-lived refresh token.")
    token_type: str = Field("bearer", description="Type of the token.")
    expires_in: int = Field(..., description="Access token expiration time in seconds.")

class RefreshTokenRequest(BaseModel):
    """Schema for refreshing the access token."""
    refresh_token: str = Field(..., description="The refresh token.")

class User(BaseModel):
    """Minimal user schema for token payload."""
    id: int
    email: EmailStr
    is_active: bool

class TokenData(BaseModel):
    """Schema for JWT payload data."""
    sub: str | None = None  # Subject (user identifier)
    token_type: str | None = None # 'access' or 'refresh'

# --- Utility Functions (Services) ---

def generate_otp() -> str:
    """Generates a 6-digit random OTP."""
    return str(random.randint(100000, 999999))

def send_otp_mechanism(email: str, otp: str) -> bool:
    """
    Mocks sending the OTP to the user's email.
    In a real app, this would integrate with an email/SMS service.
    """
    logger.info(f"MOCK: Sending OTP {otp} to {email}. Expires in {OTP_EXPIRE_SECONDS}s.")
    # Simulate success
    return True

def create_jwt_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Creates a JWT token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_access_token(data: dict) -> str:
    """Creates a short-lived access token."""
    data["token_type"] = "access"
    return create_jwt_token(data, expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))

def create_refresh_token(data: dict) -> str:
    """Creates a long-lived refresh token."""
    data["token_type"] = "refresh"
    return create_jwt_token(data, expires_delta=timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))

def decode_jwt_token(token: str) -> TokenData:
    """Decodes and validates a JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        token_type: str = payload.get("token_type")
        if email is None or token_type is None:
            raise JWTError
        token_data = TokenData(sub=email, token_type=token_type)
    except JWTError as e:
        logger.warning(f"JWT validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token or token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token_data

def get_user_from_db(email: str) -> User | None:
    """Mocks fetching a user from the database."""
    user_data = MOCK_DB.get(email)
    if user_data:
        return User(**user_data)
    return None

# --- Dependencies ---

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> User:
    """Dependency to get the current authenticated user from an access token."""
    token_data = decode_jwt_token(token)
    if token_data.token_type != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type. Access token required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = get_user_from_db(token_data.sub)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

# --- Rate Limiting Middleware/Dependency (Simplified) ---

def rate_limit_dependency(request: Request):
    """
    Simple rate limiting based on client IP or email for OTP requests.
    In a real app, use a dedicated library like 'fastapi-limiter'.
    """
    client_id = request.client.host if request.client else "unknown"
    
    last_request_time = RATE_LIMIT_CACHE.get(client_id, 0.0)
    current_time = time.time()
    
    if current_time - last_request_time < RATE_LIMIT_SECONDS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Try again in {RATE_LIMIT_SECONDS - (current_time - last_request_time):.0f} seconds.",
        )
    
    RATE_LIMIT_CACHE[client_id] = current_time
    logger.info(f"Rate limit check passed for client: {client_id}")
    return True

# --- FastAPI Router ---

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
    responses={404: {"description": "Not found"}},
)

@router.post(
    "/send-otp",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Request an OTP for login/verification",
    dependencies=[Depends(rate_limit_dependency)]
)
async def send_otp(request_data: SendOtpRequest):
    """
    Requests a One-Time Password (OTP) to be sent to the user's email.
    
    The OTP is stored temporarily and rate-limiting is applied to prevent abuse.
    """
    email = request_data.email
    user = get_user_from_db(email)
    
    if not user:
        # Security best practice: return a generic success message even if user doesn't exist
        logger.warning(f"Attempted OTP request for non-existent user: {email}")
        return {"message": "If the email is registered, an OTP has been sent."}

    otp = generate_otp()
    expiry_time = time.time() + OTP_EXPIRE_SECONDS
    
    # Store OTP in cache
    OTP_CACHE[email] = {"otp": otp, "expiry": expiry_time}
    
    # Send OTP (mocked)
    if not send_otp_mechanism(email, otp):
        logger.error(f"Failed to send OTP to {email}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send OTP. Please try again later."
        )

    logger.info(f"OTP generated and stored for {email}")
    return {"message": "OTP sent successfully. Check your email."}

@router.post(
    "/verify-otp",
    response_model=TokenResponse,
    summary="Verify OTP and receive JWT tokens"
)
async def verify_otp(request_data: VerifyOtpRequest):
    """
    Verifies the provided OTP. If successful, returns a new access token and refresh token.
    """
    email = request_data.email
    user_otp = request_data.otp
    
    user = get_user_from_db(email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials or user not found"
        )

    cached_otp_data = OTP_CACHE.get(email)
    
    if not cached_otp_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP not requested or has expired. Please request a new one."
        )

    if time.time() > cached_otp_data["expiry"]:
        del OTP_CACHE[email] # Clean up expired OTP
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP has expired. Please request a new one."
        )

    if user_otp != cached_otp_data["otp"]:
        # Security best practice: use generic error message
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid OTP"
        )

    # OTP is valid, remove from cache and generate tokens
    del OTP_CACHE[email]
    
    # Payload for JWT
    token_payload = {"sub": user.email, "user_id": user.id}
    
    access_token = create_access_token(token_payload)
    refresh_token = create_refresh_token(token_payload)
    
    logger.info(f"User {email} successfully verified OTP and received tokens.")
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )

@router.post(
    "/refresh-token",
    response_model=TokenResponse,
    summary="Refresh access token using a valid refresh token"
)
async def refresh_token(request_data: RefreshTokenRequest):
    """
    Exchanges a valid refresh token for a new access token and a new refresh token.
    """
    refresh_token = request_data.refresh_token
    
    try:
        token_data = decode_jwt_token(refresh_token)
    except HTTPException as e:
        # Re-raise the 401 from decode_jwt_token
        raise e
    
    if token_data.token_type != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type. Refresh token required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    user = get_user_from_db(token_data.sub)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Generate new tokens
    token_payload = {"sub": user.email, "user_id": user.id}
    
    new_access_token = create_access_token(token_payload)
    new_refresh_token = create_refresh_token(token_payload)
    
    logger.info(f"Tokens refreshed for user {user.email}")
    
    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )

@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Invalidate the current access token (optional: refresh token)"
)
async def logout(current_user: Annotated[User, Depends(get_current_user)]):
    """
    Logs out the current user. 
    
    In a token-based system, this typically means blacklisting the access token.
    For simplicity, this mock implementation just logs the event.
    In a production system, you would add the token to a blacklist/revocation list in Redis.
    """
    logger.info(f"User {current_user.email} logged out. Access token should be blacklisted.")
    # In a real system:
    # 1. Blacklist the current access token (e.g., in Redis with its expiry time)
    # 2. Optionally, invalidate the refresh token associated with this session
    
    # Return 204 No Content on successful logout
    return JSONResponse(status_code=status.HTTP_204_NO_CONTENT, content=None)

# Example of a protected route (for testing the dependency)
@router.get(
    "/me",
    response_model=User,
    summary="Get current user details (Protected Route)"
)
async def read_users_me(current_user: Annotated[User, Depends(get_current_user)]):
    """
    A protected endpoint that requires a valid access token.
    Returns the details of the currently authenticated user.
    """
    return current_user

# --- Main Application Example (for context/testing) ---
# This part is for demonstration and is not part of the router file itself.
# from fastapi import FastAPI
# app = FastAPI()
# app.include_router(router)
#
# if __name__ == "__main__":
#     # Add a mock user for testing
#     MOCK_DB["test@user.com"] = {"id": 2, "email": "test@user.com", "is_active": True}
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)