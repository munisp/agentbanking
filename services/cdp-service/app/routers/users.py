import logging
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, Field, EmailStr

# --- Configuration and Dependencies Simulation ---

# 1. Logging Setup
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
# In a real application, a handler would be configured, e.g., to send logs to a file or a log management system.
# For this example, we'll assume basic logging is set up.

# 2. Rate Limiting Simulation
# In a production environment, this would be an actual middleware or dependency, e.g., using `fastapi-limiter`.
# We'll use a simple placeholder dependency.
async def rate_limit_dependency(request: Request):
    """Simulates a rate limiting check."""
    # Production implementation logic: check a token bucket or a fixed window counter
    # For demonstration, we'll just pass, but in a real app, this would raise an HTTPException(429)
    pass

# 3. Authentication and Authorization Simulation
# In a production environment, this would be a dependency that verifies a JWT and fetches the user object.
class CurrentUser(BaseModel):
    """Model for the currently authenticated user."""
    user_id: str = Field(..., example="user-12345")
    email: EmailStr = Field(..., example="john.doe@example.com")
    first_name: str = Field(..., example="John")
    last_name: str = Field(..., example="Doe")
    is_active: bool = True
    roles: List[str] = ["user"]

async def get_current_active_user() -> CurrentUser:
    """
    Dependency to get the current active user from the request.
    Raises 401 Unauthorized if not authenticated or 403 Forbidden if inactive.
    """
    # Production implementation for actual JWT/Session verification logic
    # If verification fails:
    # raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication credentials")
    
    # Simulate a successful authentication
    user = CurrentUser(
        user_id="user-a1b2c3d4",
        email="test.user@nigerianremittance.com",
        first_name="Ayo",
        last_name="Oluwa",
    )
    
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")
        
    return user

# 4. Service Layer Simulation
# In a real application, these would be calls to a separate service/repository layer.
class Device(BaseModel):
    """Model for a user's device session."""
    device_id: str = Field(..., example="dev-xyz789")
    device_type: str = Field(..., example="Mobile App")
    last_login: datetime = Field(..., example=datetime.now())
    ip_address: str = Field(..., example="192.168.1.1")
    is_current: bool = False

class UserService:
    """Simulated service layer for user operations."""
    
    @staticmethod
    async def fetch_user_profile(user_id: str) -> CurrentUser:
        """Fetches user profile from the database."""
        # Simulate database lookup
        logger.info(f"Fetching profile for user_id: {user_id}")
        return CurrentUser(
            user_id=user_id,
            email="test.user@nigerianremittance.com",
            first_name="Ayo",
            last_name="Oluwa",
        )

    @staticmethod
    async def update_user_profile(user_id: str, update_data: 'ProfileUpdate') -> CurrentUser:
        """Updates user profile in the database."""
        logger.info(f"Updating profile for user_id: {user_id} with data: {update_data.dict()}")
        # Simulate database update and return the new profile
        updated_user = await UserService.fetch_user_profile(user_id)
        updated_user.first_name = update_data.first_name or updated_user.first_name
        updated_user.last_name = update_data.last_name or updated_user.last_name
        return updated_user

    @staticmethod
    async def fetch_user_devices(user_id: str) -> List[Device]:
        """Fetches all active device sessions for a user."""
        logger.info(f"Fetching devices for user_id: {user_id}")
        # Simulate database lookup
        return [
            Device(device_id="dev-abc123", device_type="Web Browser", last_login=datetime.now(), ip_address="10.0.0.1", is_current=True),
            Device(device_id="dev-xyz789", device_type="Mobile App", last_login=datetime(2025, 10, 20, 10, 30), ip_address="203.0.113.42"),
        ]

    @staticmethod
    async def revoke_user_device(user_id: str, device_id: str) -> bool:
        """Revokes a specific device session."""
        logger.warning(f"Revoking device {device_id} for user_id: {user_id}")
        # Simulate database operation
        if device_id == "dev-abc123":
            # Cannot revoke current device
            return False
        return True

# --- Pydantic Schemas for API ---

class ProfileUpdate(BaseModel):
    """Schema for updating a user's profile."""
    first_name: Optional[str] = Field(None, min_length=2, max_length=50, example="Jane")
    last_name: Optional[str] = Field(None, min_length=2, max_length=50, example="Doe")
    
    class Config:
        schema_extra = {
            "example": {
                "first_name": "Jane",
                "last_name": "Doe"
            }
        }

class DeviceRevokeRequest(BaseModel):
    """Schema for revoking a device."""
    device_id: str = Field(..., example="dev-xyz789", description="The ID of the device session to revoke.")

# --- FastAPI Router Definition ---

router = APIRouter(
    prefix="/users",
    tags=["User Management"],
    dependencies=[Depends(rate_limit_dependency)], # Apply rate limiting to all user endpoints
    responses={404: {"description": "Not found"}},
)

@router.get(
    "/me", 
    response_model=CurrentUser, 
    status_code=status.HTTP_200_OK,
    summary="Get Current User Profile",
    description="Retrieves the detailed profile information for the currently authenticated user."
)
async def get_current_user(
    current_user: CurrentUser = Depends(get_current_active_user)
):
    """
    Retrieves the detailed profile information for the currently authenticated user.

    This endpoint uses the `get_current_active_user` dependency to ensure
    the user is authenticated and active before proceeding.

    :param current_user: The authenticated user object provided by the dependency.
    :return: The CurrentUser model containing the user's profile details.
    """
    logger.info(f"User {current_user.user_id} requested their profile.")
    # The profile is already available from the dependency, but we can optionally
    # call the service layer for the freshest data if the dependency only returns a token payload.
    # profile = await UserService.fetch_user_profile(current_user.user_id)
    return current_user

@router.patch(
    "/me/profile", 
    response_model=CurrentUser, 
    status_code=status.HTTP_200_OK,
    summary="Update User Profile",
    description="Allows the currently authenticated user to update their profile details (e.g., first name, last name)."
)
async def update_profile(
    update_data: ProfileUpdate,
    current_user: CurrentUser = Depends(get_current_active_user)
):
    """
    Updates the profile of the currently authenticated user.

    Performs input validation using the `ProfileUpdate` Pydantic schema.
    Only non-None fields in the request body will be updated.

    :param update_data: The data to update, validated by ProfileUpdate schema.
    :param current_user: The authenticated user object.
    :raises HTTPException 400: If the update data is empty.
    :return: The updated CurrentUser model.
    """
    if not update_data.dict(exclude_unset=True):
        logger.warning(f"User {current_user.user_id} attempted to update profile with empty data.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No update data provided."
        )
        
    try:
        updated_profile = await UserService.update_user_profile(
            user_id=current_user.user_id,
            update_data=update_data
        )
        logger.info(f"Profile updated successfully for user {current_user.user_id}.")
        return updated_profile
    except Exception as e:
        logger.error(f"Failed to update profile for user {current_user.user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during profile update."
        )

@router.get(
    "/me/devices", 
    response_model=List[Device], 
    status_code=status.HTTP_200_OK,
    summary="List User Devices",
    description="Retrieves a list of all active device sessions for the current user."
)
async def list_devices(
    current_user: CurrentUser = Depends(get_current_active_user)
):
    """
    Retrieves a list of all active device sessions associated with the current user.

    This is crucial for security, allowing users to monitor and manage their active sessions.

    :param current_user: The authenticated user object.
    :return: A list of Device models.
    """
    try:
        devices = await UserService.fetch_user_devices(current_user.user_id)
        logger.info(f"Retrieved {len(devices)} devices for user {current_user.user_id}.")
        return devices
    except Exception as e:
        logger.error(f"Failed to list devices for user {current_user.user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve device list."
        )

@router.post(
    "/me/devices/revoke", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke Device Session",
    description="Revokes a specific device session by its ID, effectively logging out that device."
)
async def revoke_device(
    revoke_request: DeviceRevokeRequest,
    current_user: CurrentUser = Depends(get_current_active_user)
):
    """
    Revokes a specific device session, identified by `device_id`.

    This action terminates the session associated with the device ID, forcing a re-login.
    The current device session cannot be revoked via this endpoint.

    :param revoke_request: The request body containing the device ID to revoke.
    :param current_user: The authenticated user object.
    :raises HTTPException 400: If the user attempts to revoke their current device.
    :raises HTTPException 404: If the device ID is not found.
    :raises HTTPException 500: On internal server error.
    :return: 204 No Content on successful revocation.
    """
    device_id_to_revoke = revoke_request.device_id
    
    # In a real scenario, we would check if the device_id matches the current session's device_id
    # For simulation, we'll use a placeholder check from the service layer.
    
    try:
        success = await UserService.revoke_user_device(current_user.user_id, device_id_to_revoke)
        
        if not success:
            logger.warning(f"User {current_user.user_id} failed to revoke device {device_id_to_revoke}. Likely current device.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot revoke the current active device session."
            )
            
        logger.info(f"Device {device_id_to_revoke} revoked successfully for user {current_user.user_id}.")
        return status.HTTP_204_NO_CONTENT
        
    except HTTPException:
        # Re-raise the 400 if it came from the check above
        raise
    except Exception as e:
        logger.error(f"Failed to revoke device {device_id_to_revoke} for user {current_user.user_id}: {e}")
        # In a real app, we might distinguish between 404 (device not found) and 500 (db error)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during device revocation."
        )

# Example of how to integrate this router into a main FastAPI app:
# from fastapi import FastAPI
# from .user_router import router as user_router
# app = FastAPI()
# app.include_router(user_router)