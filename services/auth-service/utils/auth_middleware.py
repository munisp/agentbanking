import jwt
from fastapi import Header, HTTPException
from services.token import token_service
from schemas.v1 import Context


def get_current_user(
    authorization: str = Header(..., alias="authorization"),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_realm: str = Header(..., alias="x-keycloak-realm"),
    keycloak_pub_key: str = Header(..., alias="x-keycloak-pub-key"),
):
    """Extract and validate user from JWT token."""
    try:
        # Extract token from Bearer header
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid authorization header")

        token = authorization.replace("Bearer ", "")

        context = Context(
            tenant_id=tenant_id,
            keycloak_realm=keycloak_realm,
            keycloak_pub_key=keycloak_pub_key,
        )

        decoded_token = token_service.validate_token(token, context)

        return {
            "keycloak_id": decoded_token.get("sub"),
            "email": decoded_token.get("email"),
            "preferred_username": decoded_token.get("preferred_username"),
            "tenant_id": tenant_id,
            "context": context,
        }
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
