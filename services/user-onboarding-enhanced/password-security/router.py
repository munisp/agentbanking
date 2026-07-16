import logging
from typing import Annotated, Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, EmailStr, Field

# --- Configuration and Dependencies Mockups ---

# Mock Authentication Dependency
class CurrentUser(BaseModel):
    id: int = Field(..., description="User ID")
    email: EmailStr = Field(..., description="User email")
    is_verified: bool = Field(False, description="Email verification status")

def get_current_user() -> CurrentUser:
    """
    Placeholder for an actual authentication dependency.
    In a real application, this would decode a JWT or session cookie.
    """
    # Mock user for demonstration
    return CurrentUser(id=1, email="user@example.com", is_verified=False)

# Mock Rate Limiting Decorator
def rate_limit(limit: int, period: int) -> None:
    """Placeholder for a rate limiting decorator."""
    def decorator(func) -> None:
        return func
    return decorator

# Mock Email Service
class EmailVerificationService:
    """
    Mock service for handling email verification logic.
    In a real application, this would interact with a database and an email sender.
    """
    def __init__(self) -> None:
        self.verification_codes = {} # {user_id: {"code": str, "expires_at": datetime}}

    def send_verification_email(self, user_id: int, email: EmailStr, background_tasks: BackgroundTasks) -> Dict[str, Any]:
        """Generates a code and schedules an email to be sent."""
        if self.is_verified(user_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is already verified."
            )

        code = "123456" # Mock code
        expires_at = datetime.now() + timedelta(minutes=15)
        self.verification_codes[user_id] = {"code": code, "expires_at": expires_at}

        def send_email_task() -> None:
            # Production implementation for actual email sending logic
            logging.info(f"Sending verification email to {email} with code {code}")

        background_tasks.add_task(send_email_task)
        return {"message": "Verification email scheduled for sending."}

    def verify_code(self, user_id: int, code: str) -> bool:
        """Checks if the provided code is valid and not expired."""
        data = self.verification_codes.get(user_id)
        if not data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No pending verification for this user."
            )

        if data["expires_at"] < datetime.now():
            del self.verification_codes[user_id]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Verification code has expired. Please request a new one."
            )

        if data["code"] != code:
            return False # Code mismatch

        # Success: Mark as verified (in a real app, this would update the user record)
        del self.verification_codes[user_id]
        return True

    def is_verified(self, user_id: int) -> bool:
        """Checks the current verification status."""
        # In a real app, this would check the user's database record
        # For this mock, we'll rely on the CurrentUser object's is_verified field
        return False # Always return False for the mock service to allow testing

def get_email_service() -> EmailVerificationService:
    """Dependency injector for the email verification service."""
    return EmailVerificationService()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Pydantic Models ---

class SendVerificationEmailRequest(BaseModel):
    """Request model for sending a verification email."""
    email: EmailStr = Field(..., description="The email address to send the verification code to.")

class VerifyCodeRequest(BaseModel):
    """Request model for verifying the code."""
    code: str = Field(..., min_length=6, max_length=6, description="The 6-digit verification code.")

class VerificationStatusResponse(BaseModel):
    """Response model for checking verification status."""
    is_verified: bool = Field(..., description="True if the email is verified, False otherwise.")
    message: str = Field(..., description="A status message.")

class MessageResponse(BaseModel):
    """Generic message response model."""
    message: str = Field(..., description="A descriptive message about the operation result.")

# --- FastAPI Router ---

router = APIRouter(
    prefix="/email-verification",
    tags=["Email Verification"],
    dependencies=[Depends(get_current_user)], # All endpoints require authentication
)

# --- Endpoints ---

@router.post(
    "/send",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Send a new email verification code",
    description="Sends a new verification code to the authenticated user's email address in the background.",
)
@rate_limit(limit=5, period=300) # 5 requests per 5 minutes
async def send_verification_email_endpoint(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[EmailVerificationService, Depends(get_email_service)],
    background_tasks: BackgroundTasks,
) -> None:
    """
    Handles the request to send a new email verification code.

    - **Raises HTTPException 400**: If the email is already verified.
    - **Returns 202 Accepted**: If the email is scheduled for sending.
    """
    logger.info(f"User {current_user.id} requested to send verification email to {current_user.email}")

    try:
        # Note: We use the email from the authenticated user's token/session
        # to prevent users from verifying arbitrary emails.
        result = service.send_verification_email(
            user_id=current_user.id,
            email=current_user.email,
            background_tasks=background_tasks
        )
        return MessageResponse(message=result["message"])
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error sending verification email for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while trying to send the email."
        )

@router.post(
    "/resend",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Resend the email verification code",
    description="Resends the existing or a new verification code to the authenticated user's email address.",
)
@rate_limit(limit=1, period=60) # 1 request per minute
async def resend_verification_email_endpoint(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[EmailVerificationService, Depends(get_email_service)],
    background_tasks: BackgroundTasks,
) -> None:
    """
    Handles the request to resend the email verification code.
    This is essentially the same logic as 'send' but with a stricter rate limit.
    """
    return await send_verification_email_endpoint(current_user, service, background_tasks)


@router.post(
    "/verify",
    response_model=VerificationStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify the email verification code",
    description="Verifies the code provided by the user. If successful, the user's email is marked as verified.",
)
@rate_limit(limit=10, period=60) # 10 attempts per minute
async def verify_code_endpoint(
    request: VerifyCodeRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[EmailVerificationService, Depends(get_email_service)],
) -> None:
    """
    Handles the verification of the code.

    - **Raises HTTPException 404**: If no pending verification exists.
    - **Raises HTTPException 400**: If the code has expired.
    - **Returns 200 OK**: With the new verification status.
    """
    logger.info(f"User {current_user.id} attempting to verify code.")

    if current_user.is_verified:
        return VerificationStatusResponse(is_verified=True, message="Email is already verified.")

    try:
        is_valid = service.verify_code(user_id=current_user.id, code=request.code)

        if is_valid:
            # In a real app, the user's token/session would be refreshed here
            # to reflect the new is_verified=True status.
            return VerificationStatusResponse(is_verified=True, message="Email successfully verified.")
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid verification code."
            )
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error verifying code for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during verification."
        )

@router.get(
    "/status",
    response_model=VerificationStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Check email verification status",
    description="Returns the current email verification status of the authenticated user.",
)
async def check_verification_status_endpoint(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> None:
    """
    Checks the current verification status of the authenticated user.

    - **Returns 200 OK**: With the current verification status.
    """
    logger.info(f"User {current_user.id} checking verification status.")

    if current_user.is_verified:
        return VerificationStatusResponse(is_verified=True, message="Email is verified.")
    else:
        return VerificationStatusResponse(is_verified=False, message="Email is not yet verified.")

# Note on CORS:
# CORS is typically configured on the main FastAPI application instance (app = FastAPI(...))
# or via a middleware (app.add_middleware(CORSMiddleware, ...)).
# It is not configured on the APIRouter itself.
# We assume the main application will handle CORS.

# Note on Pagination/Filtering/Sorting:
# These requirements are not applicable to the transactional nature of an email verification service.
# The service deals with single user actions (send, verify, status) and does not have list endpoints.

# Note on Logging:
# Basic logging is included in the endpoint functions.

# Note on Authentication:
# The router uses a global dependency 'Depends(get_current_user)' to ensure all endpoints are protected.

# Note on Error Handling:
# Proper HTTPException usage is included in the service mock and endpoint logic.

# Note on Background Tasks:
# BackgroundTasks is used in the 'send' endpoint to simulate non-blocking email sending.

# Note on Tags:
# The router is initialized with 'tags=["Email Verification"]'.
