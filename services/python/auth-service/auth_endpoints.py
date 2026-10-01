"""
Authentication API Endpoints
"""
from fastapi import APIRouter, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime, timedelta
from typing import Dict, List
import secrets

router = APIRouter(prefix="/api/auth", tags=["authentication"])

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

def generate_otp() -> str:
    return str(secrets.randbelow(1000000)).zfill(6)

def check_rate_limit(identifier: str, max_attempts: int = 5) -> bool:
    return _rl_hit(identifier, max_attempts, window_seconds=900)

@router.post("/verify-email", response_model=VerificationResponse)
async def verify_email(data: EmailVerification):
    """Verify email with OTP code."""
    if not check_rate_limit(f"email_verify:{data.email}"):
        raise HTTPException(status_code=429, detail="Too many attempts")
    
    otp_key = f"email:{data.email}"
    stored_otp = _otp_get(otp_key)
    if stored_otp is None:
        raise HTTPException(status_code=404, detail="No verification code found, or it has expired")

    attempts = _otp_incr_attempts(otp_key)
    if attempts > 5:
        _otp_del(otp_key)
        raise HTTPException(status_code=400, detail="Maximum verification attempts exceeded")

    if data.code != stored_otp["code"]:
        return {"success": False, "message": "Invalid code", "verified": False}

    _otp_del(otp_key)
    return {"success": True, "message": "Email verified", "verified": True}

@router.post("/verify-phone", response_model=VerificationResponse)
async def verify_phone(data: PhoneVerification):
    """Verify phone with OTP code."""
    if not check_rate_limit(f"phone_verify:{data.phone}"):
        raise HTTPException(status_code=429, detail="Too many attempts")
    
    otp_key = f"phone:{data.phone}"
    stored_otp = _otp_get(otp_key)
    if stored_otp is None:
        raise HTTPException(status_code=404, detail="No verification code found, or it has expired")

    attempts = _otp_incr_attempts(otp_key)
    if attempts > 5:
        _otp_del(otp_key)
        raise HTTPException(status_code=400, detail="Maximum verification attempts exceeded")

    if data.code != stored_otp["code"]:
        return {"success": False, "message": "Invalid code", "verified": False}

    _otp_del(otp_key)
    return {"success": True, "message": "Phone verified", "verified": True}
