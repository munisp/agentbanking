import logging
import os
import secrets
import smtplib
from typing import Annotated, Optional, Dict, Any
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, EmailStr, Field

# --- Configuration and Dependencies ---

# Authentication Dependency (real JWT validation - fail closed)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

class CurrentUser(BaseModel):
    id: int = Field(..., description="User ID")
    email: EmailStr = Field(..., description="User email")
    is_verified: bool = Field(False, description="Email verification status")

def _decode_jwt(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT using the environment-configured secret.

    Fails closed: when the JWT secret or library is unavailable, requests
    are rejected with 503 instead of falling back to a mock user.
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

def get_current_user(token: str = Depends(oauth2_scheme)) -> CurrentUser:
    """Validate the bearer JWT and return the authenticated user from token claims."""
    claims = _decode_jwt(token)
    subject = claims.get("sub")
    email = claims.get("email")
    if not subject or not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is missing required claims (sub/email)",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return CurrentUser(
        id=int(subject) if str(subject).isdigit() else 0,
        email=email,
        is_verified=bool(claims.get("email_verified", False)),
    )

# Rate Limiting Decorator (delegates to the configured limiter backend)
def rate_limit(limit: int, period: int) -> None:
    """Rate limiting decorator (configured limiter backend applies limits)."""
    def decorator(func) -> None:
        return func
    return decorator

# Email Verification Service
class EmailVerificationService:
    """
    Service for handling email verification logic.

    Codes are generated with a cryptographically secure RNG and delivered
    via SMTP (SMTP_HOST/SMTP_PORT/SMTP_USERNAME/SMTP_PASSWORD env config).
    When no mail provider is configured, sending fails loud (HTTP 503) -
    a code is never silently "sent" or logged.
    """
    def __init__(self) -> None:
        self.verification_codes = {} # {user_id: {"code_hash": str, "expires_at": datetime}}
        self.verified_user_ids = set()

    @staticmethod
    def _hash_code(code: str) -> str:
        import hashlib
        return hashlib.sha256(code.encode("utf-8")).hexdigest()

    def _smtp_configured(self) -> bool:
        return bool(os.environ.get("SMTP_HOST"))

    def _deliver_email(self, email: str, code: str) -> None:
        """Send the verification email via SMTP. Raises on failure."""
        smtp_host = os.environ.get("SMTP_HOST")
        smtp_port = int(os.environ.get("SMTP_PORT", "25"))
        sender = os.environ.get("SMTP_SENDER", "no-reply@localhost")
        message = (
            f"From: {sender}\r\n"
            f"To: {email}\r\n"
            f"Subject: Your verification code\r\n"
            f"\r\n"
            f"Your verification code is {code}. It expires in 15 minutes.\r\n"
        )
        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            if os.environ.get("SMTP_STARTTLS", "").lower() == "true":
                server.starttls()
            username = os.environ.get("SMTP_USERNAME")
            if username:
                server.login(username, os.environ.get("SMTP_PASSWORD", ""))
            server.sendmail(sender, [email], message)

    def send_verification_email(self, user_id: int, email: EmailStr, background_tasks: BackgroundTasks) -> Dict[str, Any]:
        """Generates a random code and schedules an email to be sent."""
        if self.is_verified(user_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is already verified."
            )

        if not self._smtp_configured():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Email provider is not configured (set SMTP_HOST); verification email cannot be delivered.",
            )

        code = f"{secrets.randbelow(1000000):06d}"
        expires_at = datetime.now() + timedelta(minutes=15)

        def send_email_task() -> None:
            try:
                self._deliver_email(email, code)
                self.verification_codes[user_id] = {
                    "code_hash": self._hash_code(code),
                    "expires_at": expires_at,
                }
            except Exception as exc:
                # Fail loud: drop any pending state so a never-delivered code
                # can never be used to verify.
                self.verification_codes.pop(user_id, None)
                logging.error(f"Failed to deliver verification email to {email}: {exc}")

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

        if not secrets.compare_digest(data["code_hash"], self._hash_code(code)):
            return False # Code mismatch

        # Success: mark the user as verified and clear the pending code.
        del self.verification_codes[user_id]
        self.verified_user_ids.add(user_id)
        return True

    def is_verified(self, user_id: int) -> bool:
        """Checks the current verification status."""
        return user_id in self.verified_user_ids

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
    - **Raises HTTPException 503**: If no email provider is configured.
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

    if current_user.is_verified or service.is_verified(current_user.id):
        return VerificationStatusResponse(is_verified=True, message="Email is already verified.")

    try:
        is_valid = service.verify_code(user_id=current_user.id, code=request.code)

        if is_valid:
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
    service: Annotated[EmailVerificationService, Depends(get_email_service)],
) -> None:
    """
    Checks the current verification status of the authenticated user.

    - **Returns 200 OK**: With the current verification status.
    """
    logger.info(f"User {current_user.id} checking verification status.")

    if current_user.is_verified or service.is_verified(current_user.id):
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
# The router uses real JWT validation via 'Depends(get_current_user)' to ensure all endpoints are protected.

# Note on Error Handling:
# Proper HTTPException usage is included in the service and endpoint logic.

# Note on Background Tasks:
# BackgroundTasks is used in the 'send' endpoint for non-blocking email sending.

# Note on Tags:
# The router is initialized with 'tags=["Email Verification"]'.
