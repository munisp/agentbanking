import logging
from typing import Annotated, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Header, Request
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN, HTTP_404_NOT_FOUND, HTTP_500_INTERNAL_SERVER_ERROR
from pydantic import BaseModel, Field

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("admin_router")

# ==============================================================================
# 1. Pydantic Schemas (Input Validation & Response Models)
# ==============================================================================

class ErrorResponse(BaseModel):
    """
    Standard error response model.
    """
    detail: str = Field(..., description="A detailed message about the error.")
    code: Optional[str] = Field(None, description="An optional error code.")

class AdminUserResponse(BaseModel):
    """
    Response model for a user retrieved by an admin.
    """
    user_id: str = Field(..., description="Unique identifier for the user.")
    wallet_address: str = Field(..., description="The user's primary wallet address.")
    email: Optional[str] = Field(None, description="The user's email address.")
    full_name: Optional[str] = Field(None, description="The user's full name.")
    kyc_status: str = Field(..., description="Current KYC verification status (e.g., 'verified', 'pending', 'rejected').")
    is_active: bool = Field(..., description="Whether the user account is currently active.")
    created_at: datetime = Field(..., description="Timestamp of user creation.")
    last_login: Optional[datetime] = Field(None, description="Timestamp of the user's last login.")

    class Config:
        from_attributes = True

class TransactionSummary(BaseModel):
    """
    Summary of transaction data.
    """
    total_count: int = Field(..., description="Total number of transactions.")
    total_volume_naira: float = Field(..., description="Total transaction volume in Naira.")
    total_volume_usd: float = Field(..., description="Total transaction volume in USD equivalent.")

class SystemStatsResponse(BaseModel):
    """
    Response model for system-wide statistics.
    """
    total_users: int = Field(..., description="Total number of registered users.")
    active_users_24h: int = Field(..., description="Number of users active in the last 24 hours.")
    transactions: TransactionSummary = Field(..., description="Summary of all transactions.")
    pending_kyc_count: int = Field(..., description="Number of users with pending KYC applications.")
    system_health_status: str = Field(..., description="Overall system health status (e.g., 'Operational', 'Degraded').")
    last_updated: datetime = Field(..., description="Timestamp when the statistics were last calculated.")

    class Config:
        from_attributes = True

# ==============================================================================
# 2. Dependencies (Auth, AuthZ, Rate Limiting)
# ==============================================================================

class AdminUser:
    """A placeholder class for an authenticated admin user."""
    def __init__(self, user_id: str, email: str, role: str = "admin"):
        self.user_id = user_id
        self.email = email
        self.role = role
        self.is_active = True

def get_current_user_from_token(authorization: Annotated[str, Header()]) -> Optional[AdminUser]:
    """
    Placeholder function to simulate token validation and user retrieval.
    Expects a header like 'Bearer <token>'.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = authorization.split(" ")[1]
    
    # Simulate token validation and user retrieval
    if token == "admin_token_12345":
        return AdminUser(user_id="admin_001", email="admin@platform.com", role="super_admin")
    elif token == "staff_token_67890":
        return AdminUser(user_id="staff_002", email="staff@platform.com", role="staff")
    else:
        logger.warning(f"Attempted access with invalid token: {token[:10]}...")
        return None

def get_current_admin_user(
    current_user: Annotated[AdminUser, Depends(get_current_user_from_token)]
) -> AdminUser:
    """
    Dependency to ensure the user is authenticated and has the required 'super_admin' role.
    """
    if current_user is None:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Authorization check: only 'super_admin' can access this router
    if current_user.role not in ["super_admin"]:
        logger.error(f"User {current_user.user_id} with role '{current_user.role}' attempted unauthorized access.")
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN,
            detail="The user does not have the necessary permissions (super_admin role required)."
        )
    
    logger.info(f"Admin user {current_user.user_id} authenticated successfully.")
    return current_user

def rate_limit_admin_access(request: Request):
    """
    Placeholder dependency for rate limiting admin access.
    A real implementation would use a library like 'fastapi-limiter' or a custom middleware.
    """
    client_host = request.client.host if request.client else "Unknown"
    logger.debug(f"Rate limit check passed for host: {client_host}")
    # If rate limit exceeded:
    # raise HTTPException(status_code=429, detail="Rate limit exceeded for admin operations.")
    pass

# Type aliases for cleaner route definitions
AdminAuth = Annotated[AdminUser, Depends(get_current_admin_user)]
RateLimit = Annotated[None, Depends(rate_limit_admin_access)]

# ==============================================================================
# 3. Service/Data Functions (Mocks)
# ==============================================================================

def get_user_data_from_db(wallet_address: str) -> Optional[dict]:
    """
    Simulates fetching user data from a database using the wallet address.
    
    In a production environment, this would involve a database query or service call.
    """
    logger.info(f"Attempting to fetch user data for wallet: {wallet_address}")
    
    # Production implementation logic: return data for a specific wallet, otherwise None
    if wallet_address == "0xAb5801a7d398351b8bE11C439e05C5B3259aeC9B":
        return {
            "user_id": "usr_12345",
            "wallet_address": wallet_address,
            "email": "john.doe@example.com",
            "full_name": "John Doe",
            "kyc_status": "verified",
            "is_active": True,
            "created_at": datetime(2023, 1, 15, 10, 30, 0),
            "last_login": datetime.now(),
        }
    elif wallet_address == "0x1234567890abcdef1234567890abcdef12345678":
        return {
            "user_id": "usr_67890",
            "wallet_address": wallet_address,
            "email": "jane.smith@example.com",
            "full_name": "Jane Smith",
            "kyc_status": "pending",
            "is_active": False,
            "created_at": datetime(2024, 5, 1, 15, 0, 0),
            "last_login": None,
        }
    else:
        return None

def get_system_statistics_from_service() -> dict:
    """
    Simulates fetching aggregated system statistics from a dedicated service.
    
    In a production environment, this would call a metrics or analytics service.
    """
    logger.info("Fetching system-wide statistics.")
    try:
        # Simulate complex calculation/retrieval
        stats = {
            "total_users": 150000,
            "active_users_24h": 45000,
            "transactions": {
                "total_count": 875000,
                "total_volume_naira": 5500000000.00, # 5.5 Billion NGN
                "total_volume_usd": 3500000.00, # 3.5 Million USD
            },
            "pending_kyc_count": 1200,
            "system_health_status": "Operational",
            "last_updated": datetime.now(),
        }
        return stats
    except Exception as e:
        logger.error(f"Failed to retrieve system statistics: {e}")
        # In a real app, handle specific service errors
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve system statistics due to an upstream service error."
        )

# ==============================================================================
# 4. FastAPI Router Implementation
# ==============================================================================

router = APIRouter(
    prefix="/admin",
    tags=["Admin Operations"],
    # Apply rate limiting and admin auth to all routes in this router
    dependencies=[Depends(RateLimit), Depends(AdminAuth)], 
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized access"},
        403: {"model": ErrorResponse, "description": "Forbidden access (Insufficient permissions)"},
        500: {"model": ErrorResponse, "description": "Internal Server Error"},
    }
)

@router.get(
    "/users/{wallet_address}",
    response_model=AdminUserResponse,
    summary="Get User Details by Wallet Address (Admin Only)",
    description="Retrieves comprehensive details for a user using their blockchain wallet address. Requires 'super_admin' role.",
    responses={404: {"model": ErrorResponse, "description": "User not found"}}
)
async def get_user_by_wallet(
    # Input validation using Query and regex for wallet address format
    wallet_address: Annotated[str, Query(
        min_length=42, 
        max_length=42, 
        regex=r"^0x[a-fA-F0-9]{40}$",
        description="The 42-character hexadecimal wallet address (e.g., Ethereum/EVM compatible)."
    )],
    current_admin: AdminAuth # Dependency ensures authentication and authorization
):
    """
    Retrieves a user's profile and status information using their wallet address.

    Args:
        wallet_address: The blockchain wallet address of the user.
        current_admin: The authenticated and authorized admin user object.

    Returns:
        AdminUserResponse: The user's details.

    Raises:
        HTTPException: 404 if the user is not found, 500 for internal server errors.
    """
    logger.info(f"Admin {current_admin.user_id} requested user data for wallet: {wallet_address}")
    
    try:
        user_data = get_user_data_from_db(wallet_address)
        
        if user_data is None:
            logger.warning(f"User not found for wallet: {wallet_address}")
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND,
                detail=f"User with wallet address '{wallet_address}' not found."
            )
            
        # Pydantic validation and serialization happens automatically
        return user_data
        
    except HTTPException:
        # Re-raise expected HTTP exceptions (like 404)
        raise
    except Exception as e:
        logger.error(f"Unexpected error fetching user data for {wallet_address}: {e}", exc_info=True)
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while processing the request."
        )


@router.get(
    "/stats",
    response_model=SystemStatsResponse,
    summary="Get System-Wide Statistics (Admin Only)",
    description="Retrieves key operational and financial statistics for the entire platform. Requires 'super_admin' role.",
)
async def get_system_statistics(
    current_admin: AdminAuth # Dependency ensures authentication and authorization
):
    """
    Retrieves aggregated system statistics, including user counts, transaction volumes, 
    and system health status.

    Args:
        current_admin: The authenticated and authorized admin user object.

    Returns:
        SystemStatsResponse: The aggregated system statistics.

    Raises:
        HTTPException: 500 for internal server errors during data retrieval.
    """
    logger.info(f"Admin {current_admin.user_id} requested system statistics.")
    
    try:
        stats_data = get_system_statistics_from_service()
        
        # Pydantic validation and serialization happens automatically
        return stats_data
        
    except HTTPException:
        # Re-raise expected HTTP exceptions (like 500 from service function)
        raise
    except Exception as e:
        logger.error(f"Unexpected error fetching system statistics: {e}", exc_info=True)
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving system statistics."
        )