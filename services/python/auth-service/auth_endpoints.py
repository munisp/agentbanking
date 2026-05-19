"""
Authentication API Endpoints
"""
from fastapi import APIRouter, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime, timedelta
from typing import Dict, List
import secrets

router = APIRouter(prefix="/api/auth", tags=["authentication"])

# Storage (use Redis in production)
otp_storage: Dict[str, Dict] = {}
rate_limit_storage: Dict[str, List[datetime]] = {}

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
    now = datetime.utcnow()
    window_start = now - timedelta(minutes=15)
    
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

@router.post("/verify-email", response_model=VerificationResponse)
async def verify_email(data: EmailVerification):
    """Verify email with OTP code."""
    if not check_rate_limit(f"email_verify:{data.email}"):
        raise HTTPException(status_code=429, detail="Too many attempts")
    
    otp_key = f"email:{data.email}"
    if otp_key not in otp_storage:
        raise HTTPException(status_code=404, detail="No verification code found")
    
    stored_otp = otp_storage[otp_key]
    
    if datetime.utcnow() > stored_otp["expires"]:
        del otp_storage[otp_key]
        raise HTTPException(status_code=400, detail="Code expired")
    
    stored_otp["attempts"] += 1
    
    if data.code != stored_otp["code"]:
        return {"success": False, "message": "Invalid code", "verified": False}
    
    del otp_storage[otp_key]
    return {"success": True, "message": "Email verified", "verified": True}

@router.post("/verify-phone", response_model=VerificationResponse)
async def verify_phone(data: PhoneVerification):
    """Verify phone with OTP code."""
    if not check_rate_limit(f"phone_verify:{data.phone}"):
        raise HTTPException(status_code=429, detail="Too many attempts")
    
    otp_key = f"phone:{data.phone}"
    if otp_key not in otp_storage:
        raise HTTPException(status_code=404, detail="No verification code found")
    
    stored_otp = otp_storage[otp_key]
    
    if datetime.utcnow() > stored_otp["expires"]:
        del otp_storage[otp_key]
        raise HTTPException(status_code=400, detail="Code expired")
    
    stored_otp["attempts"] += 1
    
    if data.code != stored_otp["code"]:
        return {"success": False, "message": "Invalid code", "verified": False}
    
    del otp_storage[otp_key]
    return {"success": True, "message": "Phone verified", "verified": True}
