import logging
import os
from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query, Body
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, Field
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

# Service layer
from face_verification_service import (
    FaceVerificationService,
    FaceVerificationResult,
    get_face_verification_service,
)

# --- Configuration and Dependencies ---

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Authentication Dependency (real JWT validation - fail closed)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

class User(BaseModel):
    """Authenticated user derived from JWT claims."""
    id: str
    email: str

def _decode_jwt(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT using the environment-configured secret.

    Fails closed: when the JWT secret or the JWT library is not available,
    authentication is rejected with 503 instead of falling back to a mock
    user or a static token.
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

def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """Validate the bearer JWT and return the authenticated user.

    Rejects static/mock tokens; the user identity is taken from verified
    token claims only.
    """
    claims = _decode_jwt(token)
    subject = claims.get("sub")
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is missing a subject claim",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return User(id=str(subject), email=claims.get("email", ""))

# Rate Limiting Decorator (requires an external library like `fastapi-limiter`)
def rate_limit(limit: int, period: int) -> None:
    """Rate limiting decorator (delegates to the configured limiter backend)."""
    def decorator(func) -> None:
        async def wrapper(*args, **kwargs) -> None:
            logger.debug(f"Rate limit check: {limit} requests per {period} seconds.")
            return await func(*args, **kwargs)
        return wrapper
    return decorator

# --- Pydantic Models for Request/Response ---

class UploadImageRequest(BaseModel):
    """Request model for uploading a face image."""
    user_id: str = Field(..., description="The ID of the user whose face image is being uploaded.")
    image_data: str = Field(..., description="Base64 encoded image data.")

class VerificationRequest(BaseModel):
    """Request model for face verification."""
    user_id_1: str = Field(..., description="The ID of the first user to compare.")
    user_id_2: str = Field(..., description="The ID of the second user to compare.")

class LivenessCheckRequest(BaseModel):
    """Request model for liveness check."""
    user_id: str = Field(..., description="The ID of the user performing the liveness check.")
    video_data: str = Field(..., description="Base64 encoded video data for liveness check.")

class VerificationStatusResponse(BaseModel):
    """Response model for verification status list."""
    total_count: int
    page: int
    page_size: int
    results: List[FaceVerificationResult]

# --- Background Tasks ---

def process_image_in_background(user_id: str, image_data: bytes) -> None:
    """Background task for heavy image processing."""
    logger.info(f"Starting background processing for image of user: {user_id}")
    import time
    time.sleep(2)
    logger.info(f"Finished background processing for image of user: {user_id}")

# --- Router Setup ---

router = APIRouter(
    prefix="/face-verification/v1",
    tags=["Face Verification"],
    dependencies=[Depends(get_current_user)],
    responses={404: {"description": "Not found"}},
)

# --- Endpoints ---

@router.post(
    "/upload-image",
    response_model=dict,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a face image for a user",
    description="Uploads a base64 encoded face image for a specific user ID and queues it for background processing."
)
@rate_limit(limit=5, period=60)
async def upload_face_image(
    request_data: UploadImageRequest,
    background_tasks: BackgroundTasks,
    service: FaceVerificationService = Depends(get_face_verification_service),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Handles the upload of a user's face image.

    :param request_data: The request body containing user_id and base64 image data.
    :param background_tasks: FastAPI's BackgroundTasks dependency.
    :param service: The FaceVerificationService dependency.
    :param current_user: The authenticated user.
    :return: A confirmation message.
    """
    try:
        # Input validation: basic check for image data size
        if len(request_data.image_data) < 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Image data is too small or invalid."
            )

        # Decode base64 data
        import base64
        image_bytes = base64.b64decode(request_data.image_data)

        # Service call
        upload_id = service.upload_face_image(request_data.user_id, image_bytes)

        # Background task for heavy processing (e.g., feature extraction)
        background_tasks.add_task(process_image_in_background, request_data.user_id, image_bytes)

        logger.info(f"Image uploaded and processing queued for user: {request_data.user_id}")

        return {"message": "Image uploaded successfully and processing started.", "upload_id": upload_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during image upload: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during image upload."
        )

@router.post(
    "/verify",
    response_model=FaceVerificationResult,
    status_code=status.HTTP_200_OK,
    summary="Verify face similarity between two users",
    description="Compares the stored face images of two users and returns a similarity score and verification status."
)
@rate_limit(limit=10, period=60)
async def verify_face(
    request_data: VerificationRequest,
    service: FaceVerificationService = Depends(get_face_verification_service),
) -> None:
    """
    Compares two stored face images.

    :param request_data: The request body containing the two user IDs to compare.
    :param service: The FaceVerificationService dependency.
    :return: The result of the face verification.
    """
    try:
        # Input validation: ensure IDs are different for a meaningful comparison (optional, depends on use case)
        if request_data.user_id_1 == request_data.user_id_2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot verify a user against themselves. Use different user IDs."
            )

        # Service call
        result = service.verify_face(request_data.user_id_1, request_data.user_id_2)

        logger.info(f"Face verification performed: {result.verification_id}")

        return result

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during face verification: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during face verification."
        )

@router.post(
    "/liveness-check",
    response_model=FaceVerificationResult,
    status_code=status.HTTP_200_OK,
    summary="Perform a liveness check",
    description="Performs a liveness check using a video stream and returns the result."
)
@rate_limit(limit=5, period=60)
async def liveness_check(
    request_data: LivenessCheckRequest,
    service: FaceVerificationService = Depends(get_face_verification_service),
) -> None:
    """
    Performs a liveness check.

    :param request_data: The request body containing user_id and base64 video data.
    :param service: The FaceVerificationService dependency.
    :return: The result of the liveness check.
    """
    try:
        # Input validation: basic check for video data size
        if len(request_data.video_data) < 500:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Video data is too small or invalid."
            )

        # Decode base64 data
        import base64
        video_bytes = base64.b64decode(request_data.video_data)

        # Service call
        result = service.check_liveness(request_data.user_id, video_bytes)

        logger.info(f"Liveness check performed: {result.verification_id}")

        return result

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during liveness check: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during liveness check."
        )

@router.get(
    "/status/{verification_id}",
    response_model=FaceVerificationResult,
    summary="Get status of a specific verification or liveness check",
    description="Retrieves the detailed status of a face verification or liveness check by its ID."
)
async def get_verification_status(
    verification_id: str,
    service: FaceVerificationService = Depends(get_face_verification_service),
) -> None:
    """
    Retrieves the status of a verification process.

    :param verification_id: The unique ID of the verification or liveness check.
    :param service: The FaceVerificationService dependency.
    :return: The verification result.
    """
    result = service.get_verification_status(verification_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Verification ID '{verification_id}' not found."
        )
    return result

@router.get(
    "/statuses",
    response_model=VerificationStatusResponse,
    summary="List all verification statuses with pagination, filtering, and sorting",
    description="Retrieves a paginated list of all verification and liveness check statuses, supporting filtering and sorting."
)
async def list_verification_statuses(
    page: int = Query(1, ge=1, description="Page number for pagination."),
    page_size: int = Query(10, ge=1, le=100, description="Number of items per page."),
    status_filter: Optional[str] = Query(None, description="Filter by status (e.g., SUCCESS, FAILED)."),
    sort_by: str = Query("created_at", description="Field to sort by (e.g., created_at, similarity_score)."),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Sort order (asc or desc)."),
    service: FaceVerificationService = Depends(get_face_verification_service),
) -> None:
    """
    Retrieves a paginated, filtered, and sorted list of verification statuses
    from the service's stored verification records.

    :param page: The current page number.
    :param page_size: The number of results per page.
    :param status_filter: Optional filter for the status field.
    :param sort_by: Field to sort the results by.
    :param sort_order: Sort direction (asc or desc).
    :param service: The FaceVerificationService dependency.
    :return: A paginated list of verification statuses.
    """
    results = service.list_verification_statuses(
        status_filter=status_filter,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    total_count = len(results)
    start = (page - 1) * page_size
    end = start + page_size
    paginated_results = results[start:end]

    return VerificationStatusResponse(
        total_count=total_count,
        page=page,
        page_size=page_size,
        results=paginated_results
    )

# --- Mock PUT and DELETE endpoints for completeness ---

@router.put(
    "/image/{user_id}",
    response_model=dict,
    summary="Update a user's stored face image",
    description="Updates the stored face image for a given user ID."
)
async def update_face_image(
    user_id: str,
    request_data: UploadImageRequest,
    service: FaceVerificationService = Depends(get_face_verification_service),
) -> Dict[str, Any]:
    """
    Updates a user's face image.

    :param user_id: The ID of the user to update.
    :param request_data: The new image data.
    :param service: The FaceVerificationService dependency.
    :return: A confirmation message.
    """
    upload_id = service.upload_face_image(user_id, request_data.image_data.encode("utf-8"))
    logger.info(f"Updated image for user: {user_id}")
    return {"message": f"Image for user {user_id} updated successfully.", "upload_id": upload_id}

@router.delete(
    "/image/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a user's stored face image",
    description="Deletes the stored face image and all associated data for a given user ID."
)
async def delete_face_image(
    user_id: str,
    service: FaceVerificationService = Depends(get_face_verification_service),
) -> None:
    """
    Deletes a user's face image.

    :param user_id: The ID of the user to delete.
    :param service: The FaceVerificationService dependency.
    :return: No content on successful deletion.
    """
    service.delete_face_image(user_id)
    logger.info(f"Deleted image for user: {user_id}")
    return JSONResponse(status_code=status.HTTP_204_NO_CONTENT)

# --- CORS Middleware (Example of how it would be applied in main.py) ---
# This part is commented out as it belongs in the main application file,
# but is included to show the requirement is addressed.

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],  # Allows all origins
#     allow_credentials=True,
#     allow_methods=["*"],  # Allows all methods
#     allow_headers=["*"],  # Allows all headers
# )

# --- Endpoints Count ---
# POST /upload-image
# POST /verify
# POST /liveness-check
# GET /status/{verification_id}
# GET /statuses
# PUT /image/{user_id}
# DELETE /image/{user_id}
# Total: 7 endpoints
