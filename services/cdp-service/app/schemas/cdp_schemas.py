"""
CDP Pydantic Schemas
Request/Response validation schemas
"""

from pydantic import BaseModel, EmailStr, validator
from typing import Optional, List
from datetime import datetime
import re

# ============= Request Schemas =============

class SendOTPRequest(BaseModel):
    """Send OTP request schema"""
    email: EmailStr
    purpose: str
    
    @validator('purpose')
    def validate_purpose(cls, v):
        allowed = ['signup', 'login', 'verify_email']
        if v not in allowed:
            raise ValueError(f'Invalid purpose. Must be one of: {allowed}')
        return v

class VerifyOTPRequest(BaseModel):
    """Verify OTP request schema"""
    email: EmailStr
    otp: str
    device_id: Optional[str] = None
    device_name: Optional[str] = None
    device_type: Optional[str] = None
    
    @validator('otp')
    def validate_otp(cls, v):
        if not re.match(r'^\d{6}$', v):
            raise ValueError('OTP must be 6 digits')
        return v
    
    @validator('device_type')
    def validate_device_type(cls, v):
        if v and v not in ['ios', 'android', 'web', 'flutter', 'react-native']:
            raise ValueError('Invalid device type')
        return v

class RefreshTokenRequest(BaseModel):
    """Refresh token request schema"""
    refresh_token: str

class LogoutRequest(BaseModel):
    """Logout request schema"""
    revoke_all_devices: bool = False

class UpdateProfileRequest(BaseModel):
    """Update profile request schema"""
    phone: Optional[str] = None
    full_name: Optional[str] = None
    date_of_birth: Optional[str] = None

class CreateEscrowRequest(BaseModel):
    """Create escrow request schema"""
    recipient_email: EmailStr
    amount: str
    token: str
    message: Optional[str] = None
    
    @validator('amount')
    def validate_amount(cls, v):
        try:
            amount = float(v)
            if amount <= 0:
                raise ValueError('Amount must be greater than 0')
        except ValueError:
            raise ValueError('Invalid amount format')
        return v
    
    @validator('token')
    def validate_token(cls, v):
        allowed = ['ETH', 'USDC', 'USDT']
        if v.upper() not in allowed:
            raise ValueError(f'Invalid token. Must be one of: {allowed}')
        return v.upper()

class ClaimEscrowRequest(BaseModel):
    """Claim escrow request schema"""
    escrow_id: str

class RefundEscrowRequest(BaseModel):
    """Refund escrow request schema"""
    escrow_id: str

class EstimateGasRequest(BaseModel):
    """Estimate gas request schema"""
    to_address: str
    value: str
    token: str = "ETH"
    
    @validator('to_address')
    def validate_address(cls, v):
        if not re.match(r'^0x[a-fA-F0-9]{40}$', v):
            raise ValueError('Invalid Ethereum address')
        return v

# ============= Response Schemas =============

class TokenResponse(BaseModel):
    """Token response schema"""
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int

class UserResponse(BaseModel):
    """User response schema"""
    id: int
    cdp_user_id: str
    email: str
    wallet_address: str
    email_verified: bool
    created_at: datetime
    last_login_at: Optional[datetime]
    
    class Config:
        from_attributes = True

class DeviceResponse(BaseModel):
    """Device response schema"""
    id: int
    device_id: str
    device_name: Optional[str]
    device_type: Optional[str]
    is_active: bool
    last_used_at: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True

class WalletBalanceResponse(BaseModel):
    """Wallet balance response schema"""
    token: str
    symbol: str
    name: str
    balance: str
    balance_wei: Optional[str] = None
    balance_raw: Optional[str] = None
    usd_value: str
    decimals: int
    address: Optional[str] = None

class TransactionResponse(BaseModel):
    """Transaction response schema"""
    id: int
    transaction_hash: str
    from_address: str
    to_address: str
    value: str
    token: str
    network: str
    status: str
    block_number: Optional[int]
    gas_used: Optional[int]
    gas_price: Optional[str]
    created_at: datetime
    confirmed_at: Optional[datetime]
    
    class Config:
        from_attributes = True

class EscrowResponse(BaseModel):
    """Escrow response schema"""
    escrow_id: str
    sender: str
    recipient_email: str
    amount: str
    token: str
    message: Optional[str]
    status: str
    created_at: datetime
    expires_at: datetime
    claim_url: str

class PaginationResponse(BaseModel):
    """Pagination response schema"""
    page: int
    limit: int
    total: int
    total_pages: int
    has_next: bool
    has_prev: bool

# ============= Standard Response Wrapper =============

class SuccessResponse(BaseModel):
    """Standard success response"""
    success: bool = True
    message: Optional[str] = None
    data: Optional[dict] = None

class ErrorDetail(BaseModel):
    """Error detail schema"""
    code: str
    message: str
    field: Optional[str] = None
    details: Optional[dict] = None

class ErrorResponse(BaseModel):
    """Standard error response"""
    success: bool = False
    error: ErrorDetail
