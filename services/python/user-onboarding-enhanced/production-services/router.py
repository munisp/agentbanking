import logging
from typing import List, Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from pydantic import BaseModel, Field, validator

# --- Configuration and Dependencies ---

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mock Authentication Dependency
class User(BaseModel):
    id: int
    username: str
    is_admin: bool = False

def get_current_user(is_admin_required: bool = False) -> User:
    """
    Mock dependency to simulate user authentication.
    In a real application, this would validate a token and fetch user data.
    """
    # Simulate a successful authentication
    mock_user = User(id=1, username="test_user", is_admin=True)
    
    if is_admin_required and not mock_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation requires administrator privileges"
        )
    return mock_user

# Mock Rate Limiting Dependency (Decorator)
# In a real scenario, this would interact with a Redis/Memcached store.
def rate_limit(limit: int, period: timedelta) -> None:
    """
    Mock decorator for rate limiting.
    In a real application, this would check and enforce the limit.
    """
    def decorator(func) -> None:
        async def wrapper(*args, **kwargs) -> None:
            # Simulate rate limit check
            client_id = kwargs.get("client_id", "default")
            logger.info(f"Checking rate limit for client: {client_id}. Limit: {limit} per {period.total_seconds()}s")
            # For demonstration, we just proceed
            return await func(*args, **kwargs)
        return wrapper
    return decorator

# Mock Service Layer Dependency
class RateLimitingService:
    """
    Mock service layer for rate limiting operations.
    """
    def __init__(self) -> None:
        # Mock database/store for rate limit configurations
        self.configs = {
            "user_default": RateLimitConfig(
                client_type="user", client_id="default", limit=100, period_seconds=3600,
                created_at=datetime.now(), updated_at=datetime.now()
            )
        }
        self.status_store = {} # Mock store for current usage

    def get_config(self, client_type: str, client_id: str) -> Optional["RateLimitConfig"]:
        key = f"{client_type}_{client_id}"
        return self.configs.get(key)

    def create_config(self, config: "RateLimitConfigCreate") -> "RateLimitConfig":
        key = f"{config.client_type}_{config.client_id}"
        if key in self.configs:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Rate limit configuration already exists")
        
        new_config = RateLimitConfig(**config.dict(), created_at=datetime.now(), updated_at=datetime.now())
        self.configs[key] = new_config
        return new_config

    def update_config(self, client_type: str, client_id: str, config: "RateLimitConfigUpdate") -> "RateLimitConfig":
        key = f"{client_type}_{client_id}"
        if key not in self.configs:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rate limit configuration not found")
        
        current_config = self.configs[key]
        update_data = config.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(current_config, field, value)
        current_config.updated_at = datetime.now()
        return current_config

    def delete_config(self, client_type: str, client_id: str) -> None:
        key = f"{client_type}_{client_id}"
        if key not in self.configs:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rate limit configuration not found")
        del self.configs[key]

    def get_all_configs(self, skip: int = 0, limit: int = 10, sort_by: str = "client_type", filter_by: Optional[str] = None) -> List["RateLimitConfig"]:
        configs_list = list(self.configs.values())
        
        # Filtering (simple mock)
        if filter_by:
            configs_list = [c for c in configs_list if filter_by in c.client_type or filter_by in c.client_id]

        # Sorting (simple mock)
        if sort_by in ["client_type", "client_id", "limit"]:
            configs_list.sort(key=lambda x: getattr(x, sort_by))

        return configs_list[skip : skip + limit]

    def get_status(self, client_type: str, client_id: str) -> "RateLimitStatus":
        key = f"{client_type}_{client_id}"
        config = self.get_config(client_type, client_id)
        if not config:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rate limit configuration not found")

        # Mock status
        status_data = self.status_store.get(key, {"count": 5, "reset_at": datetime.now() + timedelta(seconds=config.period_seconds)})
        
        return RateLimitStatus(
            client_type=client_type,
            client_id=client_id,
            limit=config.limit,
            remaining=config.limit - status_data["count"],
            reset_at=status_data["reset_at"],
            is_exceeded=(config.limit - status_data["count"]) <= 0
        )

    def reset_limit(self, client_type: str, client_id: str) -> None:
        key = f"{client_type}_{client_id}"
        if key not in self.configs:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rate limit configuration not found")
        
        # Mock reset
        if key in self.status_store:
            del self.status_store[key]
        logger.info(f"Rate limit for {key} has been reset.")

def get_rate_limiting_service() -> RateLimitingService:
    """Dependency injector for the RateLimitingService."""
    return RateLimitingService()

# --- Pydantic Models ---

class RateLimitConfigBase(BaseModel):
    client_type: str = Field(..., description="Type of client (e.g., 'user', 'ip', 'route').")
    client_id: str = Field(..., description="Identifier for the client (e.g., user ID, IP address, route path).")
    limit: int = Field(..., gt=0, description="Maximum number of requests allowed.")
    period_seconds: int = Field(..., gt=0, description="Time period in seconds for the limit to apply.")
    
    @validator('client_type', 'client_id')
    def check_non_empty_strings(cls, v) -> None:
        if not v or not v.strip():
            raise ValueError('Must not be empty')
        return v

class RateLimitConfigCreate(RateLimitConfigBase):
    """Model for creating a new rate limit configuration."""
    pass

class RateLimitConfigUpdate(BaseModel):
    """Model for updating an existing rate limit configuration."""
    limit: Optional[int] = Field(None, gt=0, description="Maximum number of requests allowed.")
    period_seconds: Optional[int] = Field(None, gt=0, description="Time period in seconds for the limit to apply.")

class RateLimitConfig(RateLimitConfigBase):
    """Model representing a complete rate limit configuration."""
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

class RateLimitStatus(BaseModel):
    """Model representing the current status of a rate limit."""
    client_type: str
    client_id: str
    limit: int = Field(..., description="The configured limit.")
    remaining: int = Field(..., description="The number of remaining requests.")
    reset_at: datetime = Field(..., description="Timestamp when the limit will reset.")
    is_exceeded: bool = Field(..., description="True if the limit has been exceeded.")

class MessageResponse(BaseModel):
    """Generic response model for success messages."""
    message: str

# --- Router Setup ---

router = APIRouter(
    prefix="/rate-limits",
    tags=["Rate Limiting"],
    dependencies=[Depends(get_current_user)], # Apply authentication to all endpoints
    responses={404: {"description": "Not found"}},
)

# --- Endpoints ---

@router.get(
    "/status/{client_type}/{client_id}",
    response_model=RateLimitStatus,
    summary="Check Rate Limit Status",
    description="Retrieves the current rate limit status for a specific client (e.g., user, IP, route).",
    status_code=status.HTTP_200_OK
)
@rate_limit(limit=5, period=timedelta(seconds=10)) # Example of applying a global rate limit to the status check endpoint itself
async def check_rate_limit_status(
    client_type: str,
    client_id: str,
    service: RateLimitingService = Depends(get_rate_limiting_service),
    current_user: User = Depends(get_current_user) # Explicit dependency for documentation
) -> None:
    """
    **Check Rate Limit Status**

    Retrieves the current rate limit status for a specific client, including the limit,
    remaining requests, and the time until the limit resets.

    - **client_type**: The type of entity being limited (e.g., 'user', 'ip').
    - **client_id**: The unique identifier for the entity (e.g., user ID, IP address).
    """
    logger.info(f"User {current_user.username} checking status for {client_type}/{client_id}")
    return service.get_status(client_type, client_id)

@router.get(
    "/configs",
    response_model=List[RateLimitConfig],
    summary="Get All Rate Limit Configurations",
    description="Retrieves a paginated, sortable, and filterable list of all rate limit configurations.",
    status_code=status.HTTP_200_OK
)
async def get_all_configs(
    skip: int = Query(0, ge=0, description="Number of items to skip (for pagination)."),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of items to return (for pagination)."),
    sort_by: str = Query("client_type", description="Field to sort by (e.g., 'client_type', 'limit')."),
    filter_by: Optional[str] = Query(None, description="Filter configurations by client type or ID (partial match)."),
    service: RateLimitingService = Depends(get_rate_limiting_service),
    current_user: User = Depends(get_current_user, is_admin_required=True)
) -> None:
    """
    **Get All Rate Limit Configurations**

    Requires administrator privileges. Returns a list of all configured rate limits.

    - **skip**: Pagination offset.
    - **limit**: Pagination limit.
    - **sort_by**: Field to sort the results by.
    - **filter_by**: String to filter results by client type or ID.
    """
    logger.info(f"Admin user {current_user.username} fetching all configurations.")
    return service.get_all_configs(skip=skip, limit=limit, sort_by=sort_by, filter_by=filter_by)

@router.post(
    "/configs",
    response_model=RateLimitConfig,
    summary="Create New Rate Limit Configuration",
    description="Creates a new rate limit configuration rule.",
    status_code=status.HTTP_201_CREATED
)
async def create_config(
    config: RateLimitConfigCreate,
    service: RateLimitingService = Depends(get_rate_limiting_service),
    current_user: User = Depends(get_current_user, is_admin_required=True)
) -> None:
    """
    **Create New Rate Limit Configuration**

    Requires administrator privileges. Defines a new rate limit rule for a specific client type and ID.

    - **config**: The configuration details (client_type, client_id, limit, period_seconds).
    """
    logger.info(f"Admin user {current_user.username} creating new configuration: {config.client_type}/{config.client_id}")
    return service.create_config(config)

@router.put(
    "/configs/{client_type}/{client_id}",
    response_model=RateLimitConfig,
    summary="Update Existing Rate Limit Configuration",
    description="Updates the limit and/or period of an existing rate limit configuration.",
    status_code=status.HTTP_200_OK
)
async def update_config(
    client_type: str,
    client_id: str,
    config_update: RateLimitConfigUpdate,
    service: RateLimitingService = Depends(get_rate_limiting_service),
    current_user: User = Depends(get_current_user, is_admin_required=True)
) -> None:
    """
    **Update Existing Rate Limit Configuration**

    Requires administrator privileges. Modifies an existing rate limit rule.

    - **client_type**: The type of entity being limited.
    - **client_id**: The unique identifier for the entity.
    - **config_update**: The fields to update (limit and/or period_seconds).
    """
    logger.info(f"Admin user {current_user.username} updating configuration for {client_type}/{client_id}")
    return service.update_config(client_type, client_id, config_update)

@router.delete(
    "/configs/{client_type}/{client_id}",
    response_model=MessageResponse,
    summary="Delete Rate Limit Configuration",
    description="Deletes an existing rate limit configuration rule.",
    status_code=status.HTTP_200_OK
)
async def delete_config(
    client_type: str,
    client_id: str,
    service: RateLimitingService = Depends(get_rate_limiting_service),
    current_user: User = Depends(get_current_user, is_admin_required=True)
) -> None:
    """
    **Delete Rate Limit Configuration**

    Requires administrator privileges. Removes a rate limit rule.

    - **client_type**: The type of entity being limited.
    - **client_id**: The unique identifier for the entity.
    """
    service.delete_config(client_type, client_id)
    logger.info(f"Admin user {current_user.username} deleted configuration for {client_type}/{client_id}")
    return MessageResponse(message=f"Rate limit configuration for {client_type}/{client_id} deleted successfully.")

@router.post(
    "/reset/{client_type}/{client_id}",
    response_model=MessageResponse,
    summary="Reset Rate Limit Counter",
    description="Immediately resets the current usage counter for a specific rate limit.",
    status_code=status.HTTP_200_OK
)
async def reset_limit(
    client_type: str,
    client_id: str,
    background_tasks: BackgroundTasks,
    service: RateLimitingService = Depends(get_rate_limiting_service),
    current_user: User = Depends(get_current_user, is_admin_required=True)
) -> None:
    """
    **Reset Rate Limit Counter**

    Requires administrator privileges. Resets the usage counter for a specific client's rate limit.
    The actual reset operation is performed as a background task.

    - **client_type**: The type of entity being limited.
    - **client_id**: The unique identifier for the entity.
    """
    # The actual reset logic is simple and synchronous in the mock service, 
    # but we use BackgroundTasks to demonstrate the requirement.
    background_tasks.add_task(service.reset_limit, client_type, client_id)
    logger.info(f"Admin user {current_user.username} requested reset for {client_type}/{client_id}. Processing in background.")
    return MessageResponse(message=f"Rate limit for {client_type}/{client_id} reset requested and processing in background.")

# --- CORS Handling (Mock) ---
# In a real FastAPI app, CORS is typically added to the main app instance, 
# but we can include a note here or a mock middleware-like function for completeness.

# Note: CORS configuration is usually applied to the main FastAPI application instance.
# Example:
# from fastapi.middleware.cors import CORSMiddleware
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"], # Adjust in production
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# Since this is a router file, we assume the main app handles CORS.
# The router itself does not directly handle CORS.
