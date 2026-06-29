import jwt
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session
from schemas.v1 import GenerateToken, Context
from database import get_session
from utils import get_config, create_logger
from services import token_service
from utils.errors import raise_http_exception_handler, ApiError

config = get_config()
logger = create_logger(__name__)

token_router = APIRouter()


@token_router.post("/generate")
def generate_token(
    payload: GenerateToken,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_realm: str = Header(..., alias="x-keycloak-realm"),
    keycloak_pub_key: str = Header(..., alias="x-keycloak-pub-key"),
):
    """Generate access token route handler."""

    try:
        context = Context(
            tenant_id=tenant_id,
            keycloak_realm=keycloak_realm,
            keycloak_pub_key=keycloak_pub_key,
        )

        token_response = token_service.generate_token(payload, db, context)

        return {"message": "success", **token_response}
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during generate_token: {e}")
        raise_http_exception_handler(
            status_code=500,
            message="Failed to generate token.",
            code="AUTH-TOKEN-INT-5001",
        )


@token_router.get("/validate/{token}")
def validate_token(
    token: str,
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_realm: str = Header(..., alias="x-keycloak-realm"),
    keycloak_pub_key: str = Header(..., alias="x-keycloak-pub-key"),
):
    """Validate access token route handler."""

    try:
        context = Context(
            tenant_id=tenant_id,
            keycloak_realm=keycloak_realm,
            keycloak_pub_key=keycloak_pub_key,
        )

        decoded_token = token_service.validate_token(token, context)

        return {
            "keycloak_id": decoded_token.get("sub"),
            **decoded_token,
        }
    except jwt.ExpiredSignatureError:
        raise_http_exception_handler(
            status_code=401,
            message="Token has expired.",
            code="AUTH-TOKEN-INT-5002",
        )
    except Exception as e:
        logger.error(f"Unexpected error during validate_token: {e}")
        raise_http_exception_handler(
            status_code=401,
            message="Failed to validate token.",
            code="AUTH-TOKEN-INT-5003",
        )


class RefreshTokenBody(BaseModel):
    refresh_token: str


@token_router.post("/refresh")
def refresh_access_token_body(
    body: RefreshTokenBody,
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_realm: str = Header(..., alias="x-keycloak-realm"),
    keycloak_pub_key: str = Header(..., alias="x-keycloak-pub-key"),
):
    """Refresh access token (body-based) route handler"""
    try:
        context = Context(
            tenant_id=tenant_id,
            keycloak_realm=keycloak_realm,
            keycloak_pub_key=keycloak_pub_key,
        )
        refresh_token_response = token_service.refresh_token(body.refresh_token, context)
        return {"message": "success", **refresh_token_response}
    except HTTPException as e:
        raise e
    except ApiError as e:
        logger.error(f"Keycloak rejected refresh token: {e}")
        raise_http_exception_handler(
            status_code=401,
            message="Session expired. Please log in again.",
            code="AUTH-TOKEN-INT-4011",
        )
    except Exception as e:
        logger.error(f"Unexpected error during refresh_token: {e}")
        raise_http_exception_handler(
            status_code=500,
            message="Failed to refresh token.",
            code="AUTH-TOKEN-INT-5004",
        )


@token_router.post("/refresh/{token}")
def refresh_access_token(
    token: str,
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_realm: str = Header(..., alias="x-keycloak-realm"),
    keycloak_pub_key: str = Header(..., alias="x-keycloak-pub-key"),
):
    """Refresh access token route handler"""

    try:
        context = Context(
            tenant_id=tenant_id,
            keycloak_realm=keycloak_realm,
            keycloak_pub_key=keycloak_pub_key,
        )

        refresh_token_response = token_service.refresh_token(token, context)

        return {"message": "success", **refresh_token_response}
    except HTTPException as e:
        raise e
    except ApiError as e:
        logger.error(f"Keycloak rejected refresh token: {e}")
        raise_http_exception_handler(
            status_code=401,
            message="Session expired. Please log in again.",
            code="AUTH-TOKEN-INT-4011",
        )
    except Exception as e:
        logger.error(f"Unexpected error during refresh_token: {e}")
        raise_http_exception_handler(
            status_code=500,
            message="Failed to refresh token.",
            code="AUTH-TOKEN-INT-5004",
        )
