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

# round-11: OTP + rate-limit state moved from in-process dicts to Redis.
# OTP entries expire via Redis TTL (300s); rate limits use a fixed window.
import os as _r11_os
import json as _r11_json
import redis as _r11_redis

_r11 = _r11_redis.Redis.from_url(
    _r11_os.environ.get("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True
)
_OTP_TTL_SECONDS = 300  # 5 minutes


def _otp_set(key: str, code: str) -> None:
    _r11.setex(f"otp:{key}", _OTP_TTL_SECONDS, _r11_json.dumps({"code": code, "attempts": 0}))


def _otp_get(key: str):
    raw = _r11.get(f"otp:{key}")
    return _r11_json.loads(raw) if raw else None


def _otp_del(key: str) -> None:
    _r11.delete(f"otp:{key}")


def _otp_incr_attempts(key: str) -> int:
    """Increment the attempts counter, preserving the entry TTL (write-back fix)."""
    raw = _r11.get(f"otp:{key}")
    if not raw:
        return 0
    payload = _r11_json.loads(raw)
    payload["attempts"] = int(payload.get("attempts", 0)) + 1
    ttl = _r11.ttl(f"otp:{key}")
    _r11.setex(f"otp:{key}", ttl if ttl and ttl > 0 else _OTP_TTL_SECONDS, _r11_json.dumps(payload))
    return payload["attempts"]


def _rl_hit(identifier: str, max_attempts: int, window_seconds: int) -> bool:
    """Fixed-window rate limiter on Redis. Returns True if the attempt is allowed."""
    k = f"rl:{identifier}"
    n = _r11.incr(k)
    if n == 1:
        _r11.expire(k, window_seconds)
    return n <= max_attempts

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
    return _rl_hit(identifier, max_attempts, window_seconds=window_minutes * 60)

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
    
    _otp_set(f"email:{data.email}", email_otp)
    _otp_set(f"phone:{data.phone}", phone_otp)
    
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
    stored_otp = _otp_get(otp_key)
    if stored_otp is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No verification code found, or it has expired."
        )

    attempts = _otp_incr_attempts(otp_key)
    if attempts > 5:
        _otp_del(otp_key)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum verification attempts exceeded."
        )

    if data.code != stored_otp["code"]:
        return {
            "success": False,
            "message": f"Invalid verification code. {6 - attempts} attempts remaining.",
            "verified": False
        }

    _otp_del(otp_key)

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
    stored_otp = _otp_get(otp_key)
    if stored_otp is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No verification code found, or it has expired."
        )

    attempts = _otp_incr_attempts(otp_key)
    if attempts > 5:
        _otp_del(otp_key)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum verification attempts exceeded."
        )

    if data.code != stored_otp["code"]:
        return {
            "success": False,
            "message": f"Invalid verification code. {6 - attempts} attempts remaining.",
            "verified": False
        }

    _otp_del(otp_key)

    return {
        "success": True,
        "message": "Phone verified successfully",
        "verified": True
    }
