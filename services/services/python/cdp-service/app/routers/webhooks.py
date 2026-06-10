import hmac
import hashlib
import json
import logging
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request, HTTPException, Depends, status
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from fastapi_limiter.depends import RateLimiter

# --- Configuration and Setup ---

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables for secrets (replace with a proper secret management solution in production)
# For demonstration, we'll use placeholders and assume they are loaded from environment
CDP_WEBHOOK_SECRET = os.environ.get("CDP_WEBHOOK_SECRET", "default_cdp_secret")
BASE_NETWORK_WEBHOOK_SECRET = os.environ.get("BASE_NETWORK_WEBHOOK_SECRET", "default_base_secret")

# Initialize FastAPI Router
router = APIRouter(
    prefix="/webhooks",
    tags=["Webhooks"],
    responses={404: {"description": "Not found"}},
)

# --- Pydantic Schemas for Webhook Payloads ---

class CDPWebhookData(BaseModel):
    """Schema for the data payload of a CDP webhook event."""
    user_id: str = Field(..., description="Unique identifier for the user.")
    event_type: str = Field(..., description="Type of the event, e.g., 'transaction_completed'.")
    timestamp: int = Field(..., description="Unix timestamp of the event.")
    payload: Dict[str, Any] = Field(..., description="The main event payload details.")

class BaseNetworkWebhookData(BaseModel):
    """Schema for the data payload of a Base Network webhook event."""
    transaction_hash: str = Field(..., description="Hash of the blockchain transaction.")
    status: str = Field(..., description="Status of the transaction, e.g., 'confirmed', 'failed'.")
    block_number: int = Field(..., description="Block number where the transaction was included.")
    details: Dict[str, Any] = Field(..., description="Additional transaction details.")

# --- Utility Functions and Dependencies ---

async def verify_hmac_signature(request: Request, secret: str, signature_header: str = "X-Signature") -> None:
    """
    Verifies the HMAC signature of the incoming request body against a secret key.

    This function is intended to be used as a dependency for webhook endpoints.

    :param request: The incoming FastAPI Request object.
    :param secret: The secret key used to generate the expected signature.
    :param signature_header: The name of the header containing the signature.
    :raises HTTPException: If the signature is missing or invalid.
    """
    signature = request.headers.get(signature_header)
    if not signature:
        logger.warning(f"Missing signature header: {signature_header}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Missing {signature_header} header."
        )

    # Read the raw body
    body = await request.body()

    # Calculate the expected signature
    try:
        # Assuming the signature is a hex digest of HMAC-SHA256
        # The secret must be bytes, and the body must be bytes
        expected_signature = hmac.new(
            secret.encode('utf-8'),
            body,
            hashlib.sha256
        ).hexdigest()
    except Exception as e:
        logger.error(f"Error calculating HMAC signature: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during signature verification."
        )

    # Securely compare the signatures
    if not hmac.compare_digest(signature, expected_signature):
        logger.warning(f"Invalid signature received. Expected: {expected_signature[:10]}..., Received: {signature[:10]}...")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid signature."
        )

    # Re-set the body so it can be read by the endpoint function (FastAPI's body reader is one-time)
    # This is a common pattern when reading the body in a dependency.
    request._body = body

# --- Webhook Endpoints ---

@router.post(
    "/cdp",
    status_code=status.HTTP_200_OK,
    summary="CDP Webhook Endpoint",
    description="Receives and processes events from the Customer Data Platform (CDP). Requires HMAC-SHA256 signature verification.",
    dependencies=[
        Depends(lambda r: verify_hmac_signature(r, CDP_WEBHOOK_SECRET, "X-CDP-Signature")),
        Depends(RateLimiter(times=10, seconds=1)) # 10 requests per second
    ]
)
async def cdp_webhook(
    request: Request,
    data: CDPWebhookData
):
    """
    Handles incoming CDP webhook events.

    The request is first authenticated via HMAC signature and then rate-limited.
    The payload is validated against the CDPWebhookData Pydantic schema.

    :param request: The incoming request object (used for logging context).
    :param data: The validated CDP webhook payload.
    :return: A success message.
    """
    try:
        # Log the incoming event for auditing and debugging
        logger.info(f"CDP Webhook received event_type: {data.event_type} for user_id: {data.user_id}")

        # --- Business Logic Placeholder ---
        # In a real application, this is where you would:
        # 1. Persist the event to a database.
        # 2. Enqueue a background job (e.g., using Celery or Redis Queue) for processing.
        # 3. Perform immediate, lightweight actions.
        # Example:
        # await process_cdp_event(data)
        # -----------------------------------

        # A successful webhook response should be fast and return 200 OK
        return {"message": "CDP Webhook received successfully", "event_type": data.event_type}

    except Exception as e:
        # Log the error with full traceback
        logger.error(f"Error processing CDP webhook: {e}", exc_info=True)
        # Return a 500 status code to the sender, indicating a server-side issue
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during webhook processing."
        )

@router.post(
    "/base_network",
    status_code=status.HTTP_200_OK,
    summary="Base Network Webhook Endpoint",
    description="Receives and processes transaction events from the Base network. Requires HMAC-SHA256 signature verification.",
    dependencies=[
        Depends(lambda r: verify_hmac_signature(r, BASE_NETWORK_WEBHOOK_SECRET, "X-Base-Signature")),
        Depends(RateLimiter(times=5, seconds=1)) # 5 requests per second
    ]
)
async def base_network_webhook(
    request: Request,
    data: BaseNetworkWebhookData
):
    """
    Handles incoming Base Network transaction webhook events.

    The request is first authenticated via HMAC signature and then rate-limited.
    The payload is validated against the BaseNetworkWebhookData Pydantic schema.

    :param request: The incoming request object (used for logging context).
    :param data: The validated Base Network webhook payload.
    :return: A success message.
    """
    try:
        # Log the incoming event for auditing and debugging
        logger.info(f"Base Network Webhook received transaction_hash: {data.transaction_hash} with status: {data.status}")

        # --- Business Logic Placeholder ---
        # In a real application, this is where you would:
        # 1. Update the status of a pending transaction in your database.
        # 2. Trigger a user notification.
        # Example:
        # await update_transaction_status(data)
        # -----------------------------------

        # A successful webhook response should be fast and return 200 OK
        return {"message": "Base Network Webhook received successfully", "transaction_hash": data.transaction_hash}

    except Exception as e:
        # Log the error with full traceback
        logger.error(f"Error processing Base Network webhook: {e}", exc_info=True)
        # Return a 500 status code to the sender, indicating a server-side issue
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during webhook processing."
        )

# --- Example of how to integrate this router into a main FastAPI app ---
# from fastapi import FastAPI
# from fastapi_limiter import FastAPILimiter
# import redis.asyncio as redis
#
# app = FastAPI()
#
# @app.on_event("startup")
# async def startup():
#     # In a real app, use a proper Redis connection pool
#     redis_conn = redis.from_url("redis://localhost:6379", encoding="utf-8", decode_responses=True)
#     await FastAPILimiter.init(redis_conn)
#
# app.include_router(router)
# ----------------------------------------------------------------------

# Note: The `fastapi-limiter` requires a Redis connection and initialization in the main app.
# The RateLimiter dependency is included in the router for completeness.