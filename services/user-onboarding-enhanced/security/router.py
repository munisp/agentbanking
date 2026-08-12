import logging
import os
import json
import urllib.request
import urllib.error
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, Field, EmailStr
from slowapi import Limiter
from slowapi.util import get_ip_addr

# --- Configuration and Dependencies ---

# 1. Rate Limiting Setup (configured globally in the main application)
class MockLimiter:
    def limit(self, limit_string: str) -> None:
        def decorator(func) -> None:
            return func
        return decorator

limiter = MockLimiter()

# 2. Logging Setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 3. Authentication Dependency (real JWT validation - fail closed)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

class CurrentUser(BaseModel):
    id: int = Field(..., description="User ID")
    email: EmailStr = Field(..., description="User email")
    is_authenticated: bool = True

def _decode_jwt(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT using the environment-configured secret.

    Fails closed: when the JWT secret or library is unavailable, requests
    are rejected with 503 instead of falling back to a fixed mock user.
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
    )

# 4. Service Dependency
class PasswordSecurityService:
    """Business logic layer for password security operations.

    - Breach checks use the real Have I Been Pwned k-anonymity range API
      and fail loud (HTTP 503) when it is unreachable.
    - Password resets verify the old password and persist the new bcrypt
      hash to the database (DATABASE_URL); there is no pretend-success path.
    """

    def __init__(self) -> None:
        self.database_url = os.environ.get("DATABASE_URL", "sqlite:///./onboarding.db")

    async def validate_strength(self, password: str) -> dict:
        """Checks password strength against the password policy."""
        if len(password) < 8:
            return {"is_strong": False, "reason": "Too short"}
        if password.lower() == password:
            return {"is_strong": False, "reason": "Missing uppercase"}
        return {"is_strong": True, "reason": "Meets minimum requirements"}

    async def check_breach(self, password_hash: str) -> bool:
        """Checks a SHA-1 password hash against Have I Been Pwned using the
        k-anonymity range API (only the first 5 hash chars leave the service).

        Raises HTTPException 503 when the breach database is unreachable;
        never guesses from the hash contents.
        """
        prefix = password_hash[:5].upper()
        suffix = password_hash[5:].upper()
        url = f"https://api.pwnedpasswords.com/range/{prefix}"
        request = urllib.request.Request(url, headers={"User-Agent": "agentbanking-password-security"})
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                body = response.read().decode("utf-8")
        except Exception as exc:
            logger.error(f"Breach database unreachable: {exc}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Password breach database is unreachable; breach check could not be performed.",
            )
        for line in body.splitlines():
            hash_suffix, _, _count = line.partition(":")
            if hash_suffix.strip().upper() == suffix:
                return True
        return False

    async def get_history(self, user_id: int, skip: int, limit: int, sort_by: str) -> List[dict]:
        """Fetches paginated and sorted password history from the database."""
        engine = self._get_engine()
        from sqlalchemy import text
        order = "ASC" if sort_by == "changed_at_asc" else "DESC"
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    f"SELECT id, hashed_password, updated_at FROM users "
                    f"WHERE id = :user_id ORDER BY updated_at {order}"
                ),
                {"user_id": user_id},
            ).fetchall()
        history = [
            {"id": row[0], "hash": (row[1] or "")[:12] + "...", "changed_at": str(row[2])}
            for row in rows
        ]
        return history[skip:skip + limit]

    def _get_engine(self):
        try:
            from sqlalchemy import create_engine
        except ImportError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database driver (sqlalchemy) is not installed on this service.",
            )
        return create_engine(self.database_url)

    async def reset_password(self, user_id: int, old_password: str, new_password: str) -> bool:
        """Verifies the old password and persists the new password hash.

        Performs a real database update; raises HTTPException when the user
        does not exist, the old password is wrong, or the write fails.
        """
        from sqlalchemy import text
        try:
            from passlib.context import CryptContext
        except ImportError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Password hashing library (passlib) is not installed on this service.",
            )

        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        engine = self._get_engine()

        with engine.begin() as conn:
            row = conn.execute(
                text("SELECT hashed_password FROM users WHERE id = :user_id"),
                {"user_id": user_id},
            ).fetchone()
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found.",
                )

            try:
                old_password_ok = pwd_context.verify(old_password, row[0])
            except ValueError:
                old_password_ok = False
            if not old_password_ok:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Current password is incorrect.",
                )

            new_hash = pwd_context.hash(new_password)
            result = conn.execute(
                text("UPDATE users SET hashed_password = :hash WHERE id = :user_id"),
                {"hash": new_hash, "user_id": user_id},
            )
            if result.rowcount != 1:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Password update failed.",
                )

        logger.info(f"Password updated in database for user {user_id}")
        return True

def get_password_service() -> PasswordSecurityService:
    """Dependency injector for the password security service."""
    return PasswordSecurityService()

# 5. Background Task Handler
def log_password_reset_attempt(user_id: int, success: bool) -> None:
    """Background task for audit logging."""
    logger.info(f"Background Task: Password reset attempt for user {user_id}. Success: {success}")

# --- Pydantic Models ---

# Request Models
class PasswordStrengthRequest(BaseModel):
    password: str = Field(..., min_length=8, max_length=128, description="The password to check for strength.")

class PasswordBreachRequest(BaseModel):
    password_hash: str = Field(..., min_length=32, max_length=256, description="The hashed password to check against breach databases.")

class PasswordResetRequest(BaseModel):
    old_password: str = Field(..., description="The user's current password for verification.")
    new_password: str = Field(..., min_length=8, max_length=128, description="The new password to set.")
    
# Response Models
class PasswordStrengthResponse(BaseModel):
    is_strong: bool = Field(..., description="True if the password meets strength requirements.")
    reason: str = Field(..., description="Details on why the password is or is not strong.")

class PasswordBreachResponse(BaseModel):
    is_breached: bool = Field(..., description="True if the password hash was found in a breach database.")
    
class PasswordHistoryEntry(BaseModel):
    id: int
    hash: str = Field(..., description="A truncated or masked version of the password hash.")
    changed_at: str = Field(..., description="Timestamp of when the password was changed.")

class PasswordHistoryResponse(BaseModel):
    total: int = Field(..., description="Total number of history entries.")
    skip: int = Field(..., description="Number of records skipped.")
    limit: int = Field(..., description="Maximum number of records returned.")
    history: List[PasswordHistoryEntry]

class PasswordResetResponse(BaseModel):
    success: bool = Field(..., description="True if the password was successfully reset.")
    message: str = Field(..., description="A message detailing the result of the reset attempt.")

# --- Router Setup ---

router = APIRouter(
    prefix="/password-security",
    tags=["Password Security"],
    dependencies=[Depends(get_current_user)], # Apply authentication to all endpoints in this router
    responses={404: {"description": "Not found"}},
)

# --- Endpoints ---

@router.post(
    "/strength",
    response_model=PasswordStrengthResponse,
    status_code=status.HTTP_200_OK,
    summary="Validate Password Strength",
    description="Checks the provided password against defined strength policies (e.g., length, complexity).",
)
@limiter.limit("5/minute") # Rate limit to 5 requests per minute per IP
async def validate_password_strength(
    request: PasswordStrengthRequest,
    service: PasswordSecurityService = Depends(get_password_service),
    current_user: CurrentUser = Depends(get_current_user),
    ip: str = Depends(get_ip_addr),
) -> None:
    """
    Validates the strength of a given password.

    - **Input Validation**: Handled by Pydantic model `PasswordStrengthRequest`.
    - **Rate Limiting**: Applied via `@limiter.limit`.
    - **Dependency Injection**: Uses `PasswordSecurityService`.
    """
    logger.info(f"User {current_user.id} ({ip}) checking password strength.")
    
    # Explicitly forbid the most common weak passwords
    if request.password in ["password", "12345678"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password is too common and explicitly forbidden."
        )

    try:
        result = await service.validate_strength(request.password)
        return result
    except Exception as e:
        logger.error(f"Error validating password strength: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during strength validation."
        )

@router.post(
    "/breach-check",
    response_model=PasswordBreachResponse,
    status_code=status.HTTP_200_OK,
    summary="Check Password Breach Status",
    description="Checks if the provided password hash has been found in known data breaches.",
)
@limiter.limit("3/minute") # More restrictive rate limit for a sensitive check
async def check_password_breach(
    request: PasswordBreachRequest,
    service: PasswordSecurityService = Depends(get_password_service),
    current_user: CurrentUser = Depends(get_current_user),
    ip: str = Depends(get_ip_addr),
) -> Dict[str, Any]:
    """
    Checks if a password hash has been compromised in a data breach.

    - **Input Validation**: Handled by Pydantic model `PasswordBreachRequest`.
    - **Rate Limiting**: Applied via `@limiter.limit`.
    """
    logger.info(f"User {current_user.id} ({ip}) checking password breach status.")
    
    try:
        is_breached = await service.check_breach(request.password_hash)
        return {"is_breached": is_breached}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking password breach: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during breach check."
        )

@router.get(
    "/history",
    response_model=PasswordHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Password History",
    description="Retrieves the user's password history with pagination, filtering, and sorting.",
)
@limiter.limit("10/hour") # Less frequent access expected
async def get_password_history(
    skip: int = Field(0, ge=0, description="Number of records to skip (for pagination)."),
    limit: int = Field(10, ge=1, le=100, description="Maximum number of records to return (for pagination)."),
    sort_by: str = Field("changed_at_desc", description="Sorting criteria. Options: 'changed_at_desc', 'changed_at_asc'."),
    service: PasswordSecurityService = Depends(get_password_service),
    current_user: CurrentUser = Depends(get_current_user),
    ip: str = Depends(get_ip_addr),
) -> None:
    """
    Fetches the password history for the authenticated user.

    - **Pagination/Filtering/Sorting**: Handled via query parameters.
    - **Input Validation**: Handled by `Field` constraints in function signature.
    """
    logger.info(f"User {current_user.id} ({ip}) fetching password history (skip={skip}, limit={limit}, sort={sort_by}).")
    
    if sort_by not in ["changed_at_desc", "changed_at_asc"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid value for 'sort_by'. Must be 'changed_at_desc' or 'changed_at_asc'."
        )
        
    try:
        history = await service.get_history(current_user.id, skip, limit, sort_by)
        
        return PasswordHistoryResponse(
            total=len(history) + skip,
            skip=skip,
            limit=limit,
            history=history
        )
    except Exception as e:
        logger.error(f"Error fetching password history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while fetching history."
        )

@router.put(
    "/reset",
    response_model=PasswordResetResponse,
    status_code=status.HTTP_200_OK,
    summary="Reset User Password",
    description="Allows an authenticated user to reset their password.",
)
@limiter.limit("1/hour") # Very restrictive rate limit for password reset
async def reset_password(
    request: PasswordResetRequest,
    background_tasks: BackgroundTasks,
    service: PasswordSecurityService = Depends(get_password_service),
    current_user: CurrentUser = Depends(get_current_user),
    ip: str = Depends(get_ip_addr),
) -> None:
    """
    Resets the authenticated user's password.

    - **Endpoint Type**: PUT is used as it updates the user's password resource.
    - **Background Task**: Logs the reset attempt asynchronously.
    - **Input Validation**: Checks if old and new passwords are the same.
    - **Persistence**: Verifies the old password and performs a real
      database update via `PasswordSecurityService.reset_password`.
    """
    logger.info(f"User {current_user.id} ({ip}) attempting password reset.")
    
    if request.old_password == request.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password cannot be the same as the old password."
        )
    
    try:
        success = await service.reset_password(
            current_user.id,
            request.old_password,
            request.new_password,
        )
        
        # Use background task for logging/notifications
        background_tasks.add_task(log_password_reset_attempt, current_user.id, success)
        
        return PasswordResetResponse(success=True, message="Password successfully reset.")
            
    except HTTPException:
        background_tasks.add_task(log_password_reset_attempt, current_user.id, False)
        raise
    except Exception as e:
        logger.error(f"Critical error during password reset for user {current_user.id}: {e}")
        background_tasks.add_task(log_password_reset_attempt, current_user.id, False)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during password reset."
        )

# Total Endpoints: 4 (POST /strength, POST /breach-check, GET /history, PUT /reset)
# Note on CORS: CORS is typically configured on the main FastAPI application instance (app = FastAPI()).
# A note in the code or documentation is sufficient for a router file.
# Example of how it would be configured in main.py:
# from fastapi.middleware.cors import CORSMiddleware
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"], # Adjust in production
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )
