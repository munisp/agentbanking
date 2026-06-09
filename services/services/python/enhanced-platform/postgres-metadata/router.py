import logging
from typing import List, Annotated

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, Field
from starlette.requests import Request

# --- Configuration and Dependencies (Mocks for a complete file) ---

# 1. Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 2. Rate Limiting Dependency (Mock)
# In a real application, this would use a library like 'fastapi-limiter'
async def rate_limit_dependency(request: Request) -> None:
    # Simple mock check. Real implementation would check IP/user ID against a store (e.g., Redis)
    # and raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS) if limit exceeded.
    pass

RateLimit = Annotated[None, Depends(rate_limit_dependency)]

# 3. Authentication Dependency (Mock)
# In a real application, this would decode a JWT, look up the user, and return a User object.
class CurrentUser(BaseModel):
    id: int = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    is_2fa_enabled: bool = Field(False, description="Is 2FA currently enabled for the user")

async def get_current_user() -> CurrentUser:
    # Mock user for demonstration. In production, this would be a real auth check.
    # We assume the user is authenticated to access these endpoints.
    return CurrentUser(id=1, email="user@example.com", is_2fa_enabled=False)

async def get_current_user_with_2fa_enabled() -> CurrentUser:
    user = await get_current_user()
    if not user.is_2fa_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="2FA is not enabled for this account."
        )
    return user

async def get_current_user_with_2fa_disabled() -> CurrentUser:
    user = await get_current_user()
    if user.is_2fa_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="2FA is already enabled for this account."
        )
    return user

AuthUser = Annotated[CurrentUser, Depends(get_current_user)]
AuthUserEnabled = Annotated[CurrentUser, Depends(get_current_user_with_2fa_enabled)]
AuthUserDisabled = Annotated[CurrentUser, Depends(get_current_user_with_2fa_disabled)]

# 4. Service Dependency (Mock)
# This would be the actual business logic layer for 2FA operations.
class TwoFAService:
    """Mock service for 2FA operations."""

    def generate_secret(self, user_id: int) -> str:
        """Generates a new 2FA secret and returns the provisioning URI/QR code data."""
        logger.info(f"User {user_id} is generating a new 2FA secret.")
        # In a real app, this would use pyotp or similar to generate a secret and a QR code URI
        return "otpauth://totp/Example:user@example.com?secret=JBSWY3DPEHPK3PXP&issuer=Example"

    def verify_totp(self, user_id: int, totp_code: str) -> bool:
        """Verifies a TOTP code."""
        logger.info(f"User {user_id} is verifying TOTP code.")
        # Mock verification
        return totp_code == "123456"

    def enable_2fa(self, user_id: int) -> None:
        """Finalizes 2FA setup and marks it as enabled in the database."""
        logger.info(f"User {user_id} is enabling 2FA.")
        # Real implementation: update user record in DB
        pass

    def generate_backup_codes(self, user_id: int) -> List[str]:
        """Generates a list of one-time backup codes."""
        logger.info(f"User {user_id} is generating backup codes.")
        return ["CODE-A1B2", "CODE-C3D4", "CODE-E5F6"]

    def verify_backup_code(self, user_id: int, backup_code: str) -> bool:
        """Verifies and consumes a backup code."""
        logger.info(f"User {user_id} is verifying backup code: {backup_code}")
        # Real implementation: check code against stored codes and delete it if valid
        return backup_code == "CODE-A1B2"

    def disable_2fa(self, user_id: int) -> None:
        """Disables 2FA for the user."""
        logger.info(f"User {user_id} is disabling 2FA.")
        # Real implementation: clear 2FA secret and mark as disabled in DB
        pass

    def send_2fa_disabled_email(self, email: str) -> None:
        """Background task to notify user of 2FA disablement."""
        logger.info(f"Sending 2FA disabled notification email to {email}.")
        # Real implementation: use an email service client to send the notification
        pass

def get_2fa_service() -> TwoFAService:
    """Dependency injector for the 2FA service."""
    return TwoFAService()

TwoFAServiceDep = Annotated[TwoFAService, Depends(get_2fa_service)]

# --- Pydantic Models ---

class TwoFASecretResponse(BaseModel):
    """Response model for 2FA secret generation."""
    qr_code_uri: str = Field(..., description="Provisioning URI for the authenticator app (e.g., otpauth://...)")
    secret: str = Field(..., description="The raw 2FA secret key (for manual entry)")

class TOTPVerificationRequest(BaseModel):
    """Request model for verifying a TOTP code."""
    totp_code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$", description="The 6-digit TOTP code from the authenticator app.")

class BackupCodesResponse(BaseModel):
    """Response model for generated backup codes."""
    backup_codes: List[str] = Field(..., description="A list of one-time use backup codes. **MUST be saved immediately by the user.**")

class BackupCodeVerificationRequest(BaseModel):
    """Request model for verifying a backup code."""
    backup_code: str = Field(..., min_length=8, max_length=16, description="One of the generated backup codes.")

class Disable2FARequest(BaseModel):
    """Request model for disabling 2FA, requiring a TOTP code for confirmation."""
    totp_code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$", description="The current 6-digit TOTP code to confirm disablement.")

class StatusResponse(BaseModel):
    """Generic status response model."""
    status: str = Field("success", description="The status of the operation.")
    message: str = Field(..., description="A descriptive message about the operation result.")

# --- Router Definition ---

router = APIRouter(
    prefix="/security/2fa",
    tags=["Security - Two-Factor Authentication (2FA)"],
    responses={404: {"description": "Not found"}},
)

# --- Endpoints ---

@router.post(
    "/enable/start",
    response_model=TwoFASecretResponse,
    status_code=status.HTTP_200_OK,
    summary="Start 2FA setup: Generate secret and QR code URI",
    description="Generates a new 2FA secret key and a provisioning URI (for QR code generation) for the authenticated user. This step does not enable 2FA yet.",
)
async def start_2fa_setup(
    user: AuthUserDisabled,
    service: TwoFAServiceDep,
    rate_limit: RateLimit,
) -> None:
    """
    Starts the 2FA setup process by generating a new secret key.
    The user must then scan the QR code (from the URI) and verify the TOTP code
    in the next step to finalize enablement.
    """
    try:
        qr_code_uri = service.generate_secret(user.id)
        # In a real implementation, the raw secret would be stored temporarily (e.g., in session/cache)
        # until the user verifies the TOTP code. For this mock, we return a placeholder secret.
        return TwoFASecretResponse(
            qr_code_uri=qr_code_uri,
            secret="JBSWY3DPEHPK3PXP" # Production implementation for the raw secret
        )
    except Exception as e:
        logger.error(f"Error starting 2FA setup for user {user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate 2FA secret."
        )

@router.post(
    "/enable/verify",
    response_model=StatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Finalize 2FA setup: Verify TOTP code and enable 2FA",
    description="Verifies the TOTP code provided by the user's authenticator app and finalizes the 2FA enablement process.",
)
async def finalize_2fa_setup(
    request_body: TOTPVerificationRequest,
    user: AuthUserDisabled,
    service: TwoFAServiceDep,
    rate_limit: RateLimit,
) -> None:
    """
    Verifies the TOTP code against the temporarily stored secret.
    If valid, 2FA is permanently enabled for the user.
    """
    if not service.verify_totp(user.id, request_body.totp_code):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid TOTP code."
        )

    # If verification is successful, enable 2FA permanently
    service.enable_2fa(user.id)

    return StatusResponse(
        status="success",
        message="Two-Factor Authentication successfully enabled."
    )

@router.post(
    "/backup-codes/generate",
    response_model=BackupCodesResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate new one-time backup codes",
    description="Generates a new set of one-time use backup codes. This should only be called after 2FA is enabled.",
)
async def generate_backup_codes(
    user: AuthUserEnabled,
    service: TwoFAServiceDep,
    rate_limit: RateLimit,
) -> None:
    """
    Generates and returns a new set of backup codes.
    The user MUST be instructed to save these codes immediately.
    """
    codes = service.generate_backup_codes(user.id)
    return BackupCodesResponse(backup_codes=codes)

@router.post(
    "/backup-codes/verify",
    response_model=StatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify and consume a backup code",
    description="Verifies a backup code and consumes it (marks it as used/invalidates it). This is typically used as an alternative to TOTP during login.",
)
async def verify_backup_code(
    request_body: BackupCodeVerificationRequest,
    user: AuthUser, # Can be used for login flow, so 2FA status doesn't matter here
    service: TwoFAServiceDep,
    rate_limit: RateLimit,
) -> None:
    """
    Verifies a backup code. If valid, the code is consumed.
    """
    if not service.verify_backup_code(user.id, request_body.backup_code):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or already used backup code."
        )

    return StatusResponse(
        status="success",
        message="Backup code verified and consumed successfully."
    )

@router.post(
    "/disable",
    response_model=StatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Disable 2FA",
    description="Disables Two-Factor Authentication for the user after verifying the current TOTP code.",
)
async def disable_2fa(
    request_body: Disable2FARequest,
    user: AuthUserEnabled,
    service: TwoFAServiceDep,
    background_tasks: BackgroundTasks,
    rate_limit: RateLimit,
) -> None:
    """
    Requires the current TOTP code to confirm the user's intent to disable 2FA.
    If successful, 2FA is disabled, and a notification email is sent as a background task.
    """
    if not service.verify_totp(user.id, request_body.totp_code):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid TOTP code. Cannot disable 2FA."
        )

    service.disable_2fa(user.id)

    # Background task for notification
    background_tasks.add_task(service.send_2fa_disabled_email, user.email)

    return StatusResponse(
        status="success",
        message="Two-Factor Authentication successfully disabled. A confirmation email has been sent."
    )

# Note on CORS: CORS middleware is typically added to the main FastAPI application instance (e.g., in main.py)
# and not within individual routers.
# Example of how it would look in main.py:
# from fastapi.middleware.cors import CORSMiddleware
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"], # Adjust in production
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )
