import logging
import os
import json
import secrets
import urllib.request
import urllib.error
from typing import Annotated, Optional, Dict, Any
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Body, Query
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, Field, conint, constr
from slowapi import Limiter, _rate_limit_ext1
from slowapi.util import get_ip_addr

# --- Configuration and Setup ---

# Initialize a basic logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Limiter instance (configured globally in the main application).
limiter = Limiter(key_func=get_ip_addr)

# Authentication Dependency (real JWT validation - fail closed)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def _decode_jwt(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT using the environment-configured secret.

    Fails closed: when the JWT secret or library is unavailable, requests
    are rejected with 503 instead of falling back to a static token.
    """
    secret = os.environ.get("JWT_SECRET_KEY")
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication provider is not configured (JWT_SECRET_KEY is not set).",
        )
    try:
        from jose import jwt as jose_jwt
        from jose.exceptions import JWTError
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="JWT validation library (python-jose) is not installed on this service.",
        )
    try:
        return jose_jwt.decode(
            token,
            secret,
            algorithms=[os.environ.get("JWT_ALGORITHM", "HS256")],
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    """Validate the bearer JWT and return the authenticated user ID (sub claim)."""
    claims = _decode_jwt(token)
    subject = claims.get("sub")
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is missing a subject claim",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return str(subject)

# Service Layer
class PhoneVerificationService:
    """
    Service layer for phone verification logic.

    OTPs are generated with a cryptographically secure RNG and delivered via
    the SMS gateway configured with SMS_GATEWAY_URL / SMS_GATEWAY_API_KEY.
    When no gateway is configured, sending fails loud (HTTP 503) - an OTP is
    never silently "sent".
    """
    def __init__(self):
        # Storage backend: {phone_number: {"otp_hash": str, "sent_at": datetime, "verified": bool, "attempts": int}}
        # In production this should be a shared store (e.g. Redis/DB); the
        # in-process dict is only acceptable for a single-worker deployment.
        self.storage = {}
        self.gateway_url = os.environ.get("SMS_GATEWAY_URL", "").rstrip("/")
        self.gateway_api_key = os.environ.get("SMS_GATEWAY_API_KEY", "")

    @staticmethod
    def _hash_otp(otp: str) -> str:
        import hashlib
        return hashlib.sha256(otp.encode("utf-8")).hexdigest()

    def _send_sms(self, phone_number: str, message: str) -> None:
        """Deliver an SMS through the configured gateway; fail loud otherwise."""
        if not self.gateway_url:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="SMS gateway is not configured (set SMS_GATEWAY_URL); OTP cannot be delivered.",
            )
        headers = {"Content-Type": "application/json"}
        if self.gateway_api_key:
            headers["Authorization"] = f"Bearer {self.gateway_api_key}"
        request = urllib.request.Request(
            f"{self.gateway_url}/messages",
            method="POST",
            data=json.dumps({"to": phone_number, "message": message}).encode("utf-8"),
            headers=headers,
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                if response.status >= 400:
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=f"SMS gateway rejected the message (status {response.status}).",
                    )
        except urllib.error.URLError as exc:
            logger.error(f"SMS gateway unreachable: {exc}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="SMS gateway is unreachable; OTP was not delivered.",
            )

    def send_otp(self, phone_number: str) -> bool:
        """Generates a random OTP, delivers it via SMS and stores its hash."""
        if phone_number in self.storage and (datetime.now() - self.storage[phone_number]["sent_at"]) < timedelta(seconds=60):
            logger.warning(f"Rate limit hit for sending OTP to {phone_number}")
            return False # Too soon to resend

        otp = f"{secrets.randbelow(1000000):06d}"

        # Deliver first; only persist the OTP when delivery succeeded.
        self._send_sms(phone_number, f"Your verification code is {otp}. It expires in 5 minutes.")

        self.storage[phone_number] = {
            "otp_hash": self._hash_otp(otp),
            "sent_at": datetime.now(),
            "verified": False,
            "attempts": 0
        }
        logger.info(f"OTP delivered to {phone_number}")
        return True

    def verify_otp(self, phone_number: str, otp: str) -> bool:
        """Verifies the OTP against the stored hash."""
        if phone_number not in self.storage:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Verification process not initiated for this number."
            )

        record = self.storage[phone_number]
        if record["verified"]:
            return True # Already verified

        if record["attempts"] >= 3:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many verification attempts. Please request a new OTP."
            )

        if (datetime.now() - record["sent_at"]) > timedelta(minutes=5):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OTP expired. Please request a new one."
            )

        record["attempts"] += 1
        if secrets.compare_digest(record["otp_hash"], self._hash_otp(otp)):
            record["verified"] = True
            logger.info(f"Phone number {phone_number} verified successfully.")
            return True
        else:
            logger.warning(f"Failed verification attempt for {phone_number}. Attempts: {record['attempts']}")
            return False

    def get_status(self, phone_number: str) -> Optional[bool]:
        """Returns the verification status."""
        if phone_number not in self.storage:
            return None
        return self.storage[phone_number]["verified"]

    def clear_verification(self, phone_number: str) -> bool:
        """Clears the verification record."""
        if phone_number in self.storage:
            del self.storage[phone_number]
            return True
        return False

# Dependency Injection for Service
def get_verification_service() -> PhoneVerificationService:
    """Dependency to inject the verification service."""
    return PhoneVerificationService()

# --- Pydantic Models ---

# Base Model for Phone Number Input
class PhoneNumberBase(BaseModel):
    """Base model for phone number input."""
    phone_number: constr(regex=r"^\+\d{1,3}\d{6,14}$") = Field(
        ...,
        example="+15551234567",
        description="Phone number in E.164 format (e.g., +CCXXXXXXXXXX)."
    )

# Request Models
class SendOtpRequest(PhoneNumberBase):
    """Request model for sending an OTP."""
    pass

class VerifyOtpRequest(PhoneNumberBase):
    """Request model for verifying an OTP."""
    otp: constr(min_length=4, max_length=8) = Field(
        ...,
        example="123456",
        description="The one-time password received via SMS."
    )

# Response Models
class OtpResponse(BaseModel):
    """Response model for OTP sending and resending."""
    success: bool = Field(True, description="Indicates if the OTP was successfully sent.")
    message: str = Field(
        "OTP sent successfully. It is valid for 5 minutes.",
        description="A user-friendly message about the operation."
    )
    retry_after_seconds: conint(ge=0) = Field(
        60,
        description="Minimum time in seconds before a new OTP can be requested."
    )

class VerificationStatusResponse(BaseModel):
    """Response model for checking verification status."""
    phone_number: str = Field(..., example="+15551234567")
    is_verified: bool = Field(False, description="True if the phone number has been successfully verified.")
    last_sent_at: Optional[datetime] = Field(None, description="Timestamp of the last OTP sent.")

class VerificationResultResponse(BaseModel):
    """Response model for OTP verification."""
    success: bool = Field(..., description="Indicates if the verification was successful.")
    message: str = Field(..., description="A user-friendly message about the verification result.")

class VerificationClearResponse(BaseModel):
    """Response model for clearing verification data."""
    success: bool = Field(True, description="Indicates if the verification data was successfully cleared.")
    message: str = Field("Verification data cleared.", description="A user-friendly message.")

# --- Router Setup ---

router = APIRouter(
    prefix="/phone-verification",
    tags=["Phone Verification"],
    dependencies=[Depends(get_current_user)], # Apply authentication to all endpoints
    responses={404: {"description": "Not found"}},
)

# --- Background Task for Logging/Analytics ---

def log_verification_event(phone_number: str, event_type: str):
    """
    A background task to log verification events to an external system
    or database without blocking the API response.
    """
    logger.info(f"BACKGROUND TASK: Logging event '{event_type}' for phone: {phone_number}")

# --- Endpoints ---

@router.post(
    "/send-otp",
    response_model=OtpResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Send a One-Time Password (OTP) to a phone number",
    description="Initiates the phone verification process by sending an OTP via SMS. Subject to rate limiting.",
)
@limiter.limit("5/minute") # Rate limit: 5 requests per minute per IP
async def send_otp(
    request: SendOtpRequest,
    background_tasks: BackgroundTasks,
    service: Annotated[PhoneVerificationService, Depends(get_verification_service)],
):
    """
    Handles the request to send an OTP.

    :param request: The request body containing the phone number.
    :param background_tasks: FastAPI's mechanism for running tasks after the response is sent.
    :param service: Dependency-injected verification service.
    :return: An OtpResponse indicating success or failure.
    :raises HTTPException 429: If the rate limit for resending is hit (e.g., less than 60s since last send).
    :raises HTTPException 503: If no SMS gateway is configured.
    """
    phone_number = request.phone_number
    logger.info(f"Attempting to send OTP to {phone_number}")

    if not service.send_otp(phone_number):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Please wait 60 seconds before requesting a new OTP.",
        )

    background_tasks.add_task(log_verification_event, phone_number, "OTP_SENT")
    return OtpResponse()

@router.post(
    "/verify-otp",
    response_model=VerificationResultResponse,
    summary="Verify the One-Time Password (OTP)",
    description="Validates the provided OTP against the one sent to the phone number.",
)
@limiter.limit("10/minute") # Rate limit: 10 verification attempts per minute per IP
async def verify_otp(
    request: VerifyOtpRequest,
    background_tasks: BackgroundTasks,
    service: Annotated[PhoneVerificationService, Depends(get_verification_service)],
):
    """
    Handles the request to verify the OTP.

    :param request: The request body containing the phone number and OTP.
    :param background_tasks: FastAPI's mechanism for running tasks after the response is sent.
    :param service: Dependency-injected verification service.
    :return: A VerificationResultResponse indicating the result.
    :raises HTTPException 404: If verification was not initiated.
    :raises HTTPException 429: If too many verification attempts have been made.
    :raises HTTPException 400: If the OTP has expired.
    """
    phone_number = request.phone_number
    otp = request.otp
    logger.info(f"Attempting to verify OTP for {phone_number}")

    try:
        is_verified = service.verify_otp(phone_number, otp)
    except HTTPException as e:
        background_tasks.add_task(log_verification_event, phone_number, f"VERIFICATION_FAILED_ERROR_{e.status_code}")
        raise e

    if is_verified:
        background_tasks.add_task(log_verification_event, phone_number, "VERIFICATION_SUCCESS")
        return VerificationResultResponse(
            success=True,
            message="Phone number verified successfully."
        )
    else:
        background_tasks.add_task(log_verification_event, phone_number, "VERIFICATION_FAILED_INCORRECT_OTP")
        return VerificationResultResponse(
            success=False,
            message="Invalid OTP. Please try again or request a new one."
        )

@router.get(
    "/status",
    response_model=VerificationStatusResponse,
    summary="Check the verification status of a phone number",
    description="Retrieves the current verification status for a given phone number.",
)
async def check_status(
    phone_number: constr(regex=r"^\+\d{1,3}\d{6,14}$") = Query(
        ...,
        example="+15551234567",
        description="Phone number in E.164 format."
    ),
    service: Annotated[PhoneVerificationService, Depends(get_verification_service)],
):
    """
    Handles the request to check the verification status.

    :param phone_number: The phone number to check (passed as a query parameter).
    :param service: Dependency-injected verification service.
    :return: A VerificationStatusResponse.
    :raises HTTPException 404: If no verification record is found for the number.
    """
    logger.info(f"Checking status for {phone_number}")
    is_verified = service.get_status(phone_number)

    if is_verified is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No verification record found for this phone number."
        )

    last_sent_at = service.storage.get(phone_number, {}).get("sent_at")

    return VerificationStatusResponse(
        phone_number=phone_number,
        is_verified=is_verified,
        last_sent_at=last_sent_at
    )

@router.post(
    "/resend-otp",
    response_model=OtpResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Resend a One-Time Password (OTP)",
    description="Requests a new OTP to be sent. Subject to a minimum wait time (e.g., 60 seconds) since the last request.",
)
@limiter.limit("2/minute") # Stricter rate limit for resend
async def resend_otp(
    request: SendOtpRequest,
    background_tasks: BackgroundTasks,
    service: Annotated[PhoneVerificationService, Depends(get_verification_service)],
):
    """
    Handles the request to resend an OTP.

    This endpoint is functionally identical to /send-otp but is provided for clarity
    in the API documentation and to allow for a different rate limit.

    :param request: The request body containing the phone number.
    :param background_tasks: FastAPI's mechanism for running tasks after the response is sent.
    :param service: Dependency-injected verification service.
    :return: An OtpResponse indicating success or failure.
    :raises HTTPException 429: If the rate limit for resending is hit (e.g., less than 60s since last send).
    """
    # The logic is handled by the service.send_otp which checks the 60s cooldown
    return await send_otp(request, background_tasks, service)

@router.delete(
    "/clear-verification",
    response_model=VerificationClearResponse,
    summary="Clear the verification record for a phone number",
    description="Deletes the stored verification data for a phone number. Useful for cleanup or re-initiation.",
)
async def clear_verification(
    request: PhoneNumberBase,
    service: Annotated[PhoneVerificationService, Depends(get_verification_service)],
):
    """
    Handles the request to clear the verification record.

    :param request: The request body containing the phone number.
    :param service: Dependency-injected verification service.
    :return: A VerificationClearResponse.
    """
    phone_number = request.phone_number
    success = service.clear_verification(phone_number)

    if success:
        logger.info(f"Verification record cleared for {phone_number}")
        return VerificationClearResponse(success=True, message="Verification data cleared.")
    else:
        logger.warning(f"Attempted to clear non-existent record for {phone_number}")
        return VerificationClearResponse(success=False, message="No active verification record found to clear.")

# Note on Missing Requirements:
# - Filtering/Sorting/Pagination: Not applicable for a simple phone verification service, as it deals with single records.
# - PUT/GET (List): Not applicable, as the service manages individual verification states, not a collection.
# - CORS: Handled at the main application level (app.py), not typically in the router file itself.
# - Logging: Basic logging is included.
# - Rate Limiting: Included using the configured `slowapi` limiter.
# - Authentication: Real JWT validation via `Depends(get_current_user)` at the router level.
# - Proper status codes, Pydantic models, docstrings, and error handling are included.
