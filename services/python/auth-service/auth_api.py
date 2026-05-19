"""
Authentication and Authorization API Endpoints
Handles user registration, login, email/phone verification
"""
from fastapi import APIRouter, HTTPException, status, BackgroundTasks
from typing import Dict, List, Optional
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime, timedelta
import secrets
from passlib.context import CryptContext
import jwt

router = APIRouter(prefix="/api/auth", tags=["authentication"])

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT configuration
SECRET_KEY = "your-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# OTP storage (in production, use Redis)
otp_storage: Dict[str, Dict] = {}
rate_limit_storage: Dict[str, List[datetime]] = {}

# Pydantic models
class UserRegister(BaseModel):
    email: EmailStr
    phone: str = Field(..., regex=r'^\+?[1-9]\d{1,14}$')
    password: str = Field(..., min_length=8)
    first_name: str
    last_name: str

class EmailVerification(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6)

class PhoneVerification(BaseModel):
    phone: str = Field(..., regex=r'^\+?[1-9]\d{1,14}$')
    code: str = Field(..., min_length=6, max_length=6)

class VerificationResponse(BaseModel):
    success: bool
    message: str
    verified: bool = False

# Helper functions
def generate_otp() -> str:
    return str(secrets.randbelow(1000000)).zfill(6)

def check_rate_limit(identifier: str, max_attempts: int = 5, window_minutes: int = 15) -> bool:
    now = datetime.utcnow()
    window_start = now - timedelta(minutes=window_minutes)
    
    if identifier not in rate_limit_storage:
        rate_limit_storage[identifier] = []
    
    rate_limit_storage[identifier] = [
        attempt for attempt in rate_limit_storage[identifier]
        if attempt > window_start
    ]
    
    if len(rate_limit_storage[identifier]) >= max_attempts:
        return False
    
    rate_limit_storage[identifier].append(now)
    return True

async def send_email_otp(email: str, code: str):
    print(f"[EMAIL] Sending OTP {code} to {email}")
    return True

async def send_sms_otp(phone: str, code: str):
    print(f"[SMS] Sending OTP {code} to {phone}")
    return True

# API Endpoints
@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(data: UserRegister, background_tasks: BackgroundTasks):
    """Register a new user and send verification codes."""
    email_otp = generate_otp()
    phone_otp = generate_otp()
    
    expiration = datetime.utcnow() + timedelta(minutes=5)
    otp_storage[f"email:{data.email}"] = {
        "code": email_otp,
        "expires": expiration,
        "attempts": 0
    }
    otp_storage[f"phone:{data.phone}"] = {
        "code": phone_otp,
        "expires": expiration,
        "attempts": 0
    }
    
    background_tasks.add_task(send_email_otp, data.email, email_otp)
    background_tasks.add_task(send_sms_otp, data.phone, phone_otp)
    
    return {
        "id": 1,
        "email": data.email,
        "phone": data.phone,
        "first_name": data.first_name,
        "last_name": data.last_name,
        "email_verified": False,
        "phone_verified": False,
        "kyc_status": "pending",
        "created_at": datetime.utcnow()
    }

@router.post("/verify-email", response_model=VerificationResponse)
async def verify_email(data: EmailVerification):
    """Verify email address with OTP code."""
    if not check_rate_limit(f"email_verify:{data.email}", max_attempts=5):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many verification attempts. Please try again later."
        )
    
    otp_key = f"email:{data.email}"
    if otp_key not in otp_storage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No verification code found for this email."
        )
    
    stored_otp = otp_storage[otp_key]
    
    if datetime.utcnow() > stored_otp["expires"]:
        del otp_storage[otp_key]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code has expired."
        )
    
    stored_otp["attempts"] += 1
    
    if stored_otp["attempts"] > 5:
        del otp_storage[otp_key]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum verification attempts exceeded."
        )
    
    if data.code != stored_otp["code"]:
        return {
            "success": False,
            "message": f"Invalid verification code. {6 - stored_otp['attempts']} attempts remaining.",
            "verified": False
        }
    
    del otp_storage[otp_key]
    
    return {
        "success": True,
        "message": "Email verified successfully",
        "verified": True
    }

@router.post("/verify-phone", response_model=VerificationResponse)
async def verify_phone(data: PhoneVerification):
    """Verify phone number with OTP code."""
    if not check_rate_limit(f"phone_verify:{data.phone}", max_attempts=5):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many verification attempts. Please try again later."
        )
    
    otp_key = f"phone:{data.phone}"
    if otp_key not in otp_storage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No verification code found for this phone."
        )
    
    stored_otp = otp_storage[otp_key]
    
    if datetime.utcnow() > stored_otp["expires"]:
        del otp_storage[otp_key]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code has expired."
        )
    
    stored_otp["attempts"] += 1
    
    if stored_otp["attempts"] > 5:
        del otp_storage[otp_key]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum verification attempts exceeded."
        )
    
    if data.code != stored_otp["code"]:
        return {
            "success": False,
            "message": f"Invalid verification code. {6 - stored_otp['attempts']} attempts remaining.",
            "verified": False
        }
    
    del otp_storage[otp_key]
    
    return {
        "success": True,
        "message": "Phone verified successfully",
        "verified": True
    }
