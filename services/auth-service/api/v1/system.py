from fastapi import APIRouter, Depends, HTTPException, responses, Header
from sqlalchemy.orm import Session
from schemas.v1 import CreateAuth, SetupPassword, Context
from database import get_session
from utils import create_logger, get_config, UserRole
from services import AuthService
from utils.errors import raise_http_exception_handler

config = get_config()

logger = create_logger(__name__)

system_router = APIRouter()

DEFAULT_TENANT_ID = "54agent"
DEFAULT_KEYCLOAK_REALM = config.DEFAULT_KEYCLOAK_REALM
DEFAULT_KEYCLOAK_PUBLIC_KEY = config.DEFAULT_KEYCLOAK_PUBLIC_KEY
DEFAULT_SUPER_ADMIN_NAME = config.DEFAULT_SUPER_ADMIN_NAME
DEFAULT_SUPER_ADMIN_EMAIL = config.DEFAULT_SUPER_ADMIN_EMAIL
DEFAULT_SUPER_ADMIN_PASSWORD = config.DEFAULT_SUPER_ADMIN_PASSWORD

@system_router.post("/seed/admin")
def seed_default_admin(db: Session = Depends(get_session)):
    """Seed default admin route handler."""

    try:
        auth_service = AuthService(db)

        context = Context(
            tenant_id=DEFAULT_TENANT_ID,
            keycloak_realm=DEFAULT_KEYCLOAK_REALM,
            keycloak_pub_key=DEFAULT_KEYCLOAK_PUBLIC_KEY,
        )

        create_auth_payload = CreateAuth(
            name=DEFAULT_SUPER_ADMIN_NAME,
            email=DEFAULT_SUPER_ADMIN_EMAIL,
            user_role=UserRole.SUPERADMIN,
        )

        auth = auth_service.create_auth(create_auth_payload, context)

        setup_password_payload = SetupPassword(
            keycloak_id=auth.keycloak_id,
            password=DEFAULT_SUPER_ADMIN_PASSWORD,
            confirm_password=DEFAULT_SUPER_ADMIN_PASSWORD,
        )

        auth_service.setup_password(setup_password_payload, context)

        return responses.JSONResponse(
            content={"message": "success", "auth": auth.to_dict()}, status_code=200
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during create_auth: {str(e)}")
        raise_http_exception_handler(
            status_code=500,
            message="Create auth failed.",
            code="AUTH-AUTH-INT-5000",
        )
