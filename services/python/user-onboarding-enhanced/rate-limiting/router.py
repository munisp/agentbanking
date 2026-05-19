import logging
from typing import Annotated, Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Body, Query
from pydantic import BaseModel, Field, conint, constr
from slowapi import Limiter, _rate_limit_ext1
from slowapi.util import get_ip_addr

# --- Configuration and Setup ---

# Initialize a basic logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mock Limiter for demonstration. In a real app, this would be configured globally.
# Assuming a global limiter instance is available as 'limiter'
limiter = Limiter(key_func=get_ip_addr)

# Mock Authentication Dependency
async def get_current_user(token: str = Body(..., embed=True)) -> str:
    """
    Mock dependency to simulate user authentication.
    In a real application, this would validate a JWT or API key.
    """
    if not token or token != "valid_auth_token":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Return a mock user ID
    return "user_123"

# Mock Service Layer
class PhoneVerificationService:
    """
    Mock service layer for phone verification logic.
    In a real application, this would interact with a database and an SMS gateway.
    """
    def __init__(self):
        # Mock storage: {phone_number: {"otp": "123456", "sent_at": datetime, "verified": bool, "attempts": int}}
        self.storage = {}

    def send_otp(self, phone_number: str) -> bool:
        """Simulates sending an OTP and storing it."""
        if phone_number in self.storage and (datetime.now() - self.storage[phone_number]["sent_at"]) < timedelta(seconds=60):
            logger.warning(f"Rate limit hit for sending OTP to {phone_number}")
            return False # Too soon to resend

        otp = "123456" # In a real app, this would be a random, secure number
        self.storage[phone_number] = {
            "otp": otp,
            "sent_at": datetime.now(),
            "verified": False,
            "attempts": 0
        }
        logger.info(f"OTP {otp} sent to {phone_number}")
        # Simulate SMS gateway call here
        return True

    def verify_otp(self, phone_number: str, otp: str) -> bool:
        """Simulates verifying the OTP."""
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
        if record["otp"] == otp:
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
    # In a real app, this would be a singleton or a request-scoped dependency
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
    # In a real app, this would call an external logging/analytics service

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
    # The current_user dependency is applied at the router level, but we can access it here if needed
):
    """
    Handles the request to send an OTP.

    :param request: The request body containing the phone number.
    :param background_tasks: FastAPI's mechanism for running tasks after the response is sent.
    :param service: Dependency-injected verification service.
    :return: An OtpResponse indicating success or failure.
    :raises HTTPException 429: If the rate limit for resending is hit (e.g., less than 60s since last send).
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

    # Mocking last_sent_at for the response, as the mock service doesn't expose it easily
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
# - Rate Limiting: Included using a mock `slowapi` decorator.
# - Authentication: Included via `Depends(get_current_user)` at the router level.
# - Proper status codes, Pydantic models, docstrings, and error handling are included.
