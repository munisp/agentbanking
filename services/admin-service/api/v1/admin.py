from fastapi import APIRouter, Depends, HTTPException, responses, Header
from sqlalchemy.orm import Session
from database import get_session
from utils import create_logger
from services import AdminService
from schemas import CreateAdminSchema, Context
from utils import AdminEventTypes
from utils.kafka_instance import KafkaClientInstance


logger = create_logger(__name__)
admin_router = APIRouter()


@admin_router.post("")
def create_admin(
    payload: CreateAdminSchema,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
):
    """Create admin route handler."""

    context = Context(tenant_id=tenant_id)

    try:
        service = AdminService(db)
        admin = service.create_admin(payload, context)

        # Publish Kafka event
        KafkaClientInstance.publish_user_event(
            event_type=AdminEventTypes.ADMIN_CREATED,
            tenant_id=tenant_id,
            user_id=admin.id,
            metadata={
                "email": admin.email,
                "name": f"{admin.first_name} {admin.last_name}",
                "access_level": admin.access_level,
                "success": True,
            },
        )

        return responses.JSONResponse(
            content={"message": "success", "admin": admin.to_dict()}, status_code=200
        )

    except HTTPException as e:
        raise e
    except Exception as e:
        KafkaClientInstance.publish_user_event(
            event_type=AdminEventTypes.ADMIN_CREATED,
            tenant_id=tenant_id,
            user_id=payload.keycloak_id,
            metadata={
                "email": payload.email,
                "name": f"{payload.first_name} {payload.last_name}",
                "access_level": payload.resolved_role(),
                "success": False,
            },
        )

        logger.error(f"Unexpected error during create_admin: {str(e)}")
        raise HTTPException(status_code=500, detail="Create admin failed.")


@admin_router.get("/{admin_id}")
def get_admin_by_id(
    admin_id: str,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
):
    """Get admin by database ID"""

    context = Context(
        tenant_id=tenant_id,
    )

    try:
        service = AdminService(db)
        admin = service.get_admin_by_id(admin_id, context)

        return responses.JSONResponse(
            content={"message": "success", "admin": admin.to_dict()}, status_code=200
        )

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during get_admin_by_id: {str(e)}")
        raise HTTPException(status_code=500, detail="Get admin failed.")


@admin_router.get("/keycloak/{keycloak_id}")
def get_admin_by_keycloak(
    keycloak_id: str,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
):
    """Get admin by keycloak id"""

    context = Context(tenant_id=tenant_id)

    try:
        service = AdminService(db)
        admin = service.get_admin_by_keycloak_id(keycloak_id, context)

        return responses.JSONResponse(
            content={"message": "success", "admin": admin.to_dict()}, status_code=200
        )

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during get_admin_by_keycloak: {str(e)}")
        raise HTTPException(status_code=500, detail="Get admin failed.")


@admin_router.get("")
def get_admins(
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
):
    """Get all admins by tenant"""

    context = Context(tenant_id=tenant_id)

    try:
        service = AdminService(db)
        admins = service.get_admins(context)

        return responses.JSONResponse(
            content={"message": "success", "admins": [a.to_dict() for a in admins]},
            status_code=200,
        )

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during get_admins: {str(e)}")
        raise HTTPException(status_code=500, detail="Get admins failed.")


@admin_router.patch("/{admin_id}/suspend")
def suspend_admin(
    admin_id: str,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
):
    """Suspend an admin"""

    context = Context(tenant_id=tenant_id)

    try:
        service = AdminService(db)
        admin = service.suspend_admin(admin_id, context)

        # Publish Kafka event
        KafkaClientInstance.publish_user_event(
            event_type=AdminEventTypes.ADMIN_SUSPENDED,
            tenant_id=tenant_id,
            user_id=admin.id,
            metadata={
                "email": admin.email,
                "name": f"{admin.first_name} {admin.last_name}",
                "access_level": admin.access_level,
            },
        )

        return responses.JSONResponse(
            content={"message": "success", "admin": admin.to_dict()}, status_code=200
        )

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during suspend_admin: {str(e)}")
        raise HTTPException(status_code=500, detail="Suspend admin failed.")


@admin_router.patch("/{admin_id}/unsuspend")
def unsuspend_admin(
    admin_id: str,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
):
    """Unsuspend an admin"""

    context = Context(tenant_id=tenant_id)

    try:
        service = AdminService(db)
        admin = service.unsuspend_admin(admin_id, context)

        # Publish Kafka event
        KafkaClientInstance.publish_user_event(
            event_type=AdminEventTypes.ADMIN_ACTIVATED,
            tenant_id=tenant_id,
            user_id=admin.id,
            metadata={
                "email": admin.email,
                "name": f"{admin.first_name} {admin.last_name}",
                "access_level": admin.access_level,
            },
        )

        return responses.JSONResponse(
            content={"message": "success", "admin": admin.to_dict()}, status_code=200
        )

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during unsuspend_admin: {str(e)}")
        raise HTTPException(status_code=500, detail="Unsuspend admin failed.")


@admin_router.post("/kyc/save")
async def save_kyc_state(
    db: Session = Depends(get_session),
    payload: dict = {},
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
):
    """Save admin KYC state"""

    context = Context(tenant_id=tenant_id)

    try:
        service = AdminService(db)
        admin = service.save_kyc_state(keycloak_id, payload, context)

        # Publish Kafka event
        KafkaClientInstance.publish_kyc_event(
            event_type=AdminEventTypes.KYC_SAVED,
            tenant_id=tenant_id,
            user_id=admin.id,
            kyc_status="saved",
            metadata={
                "email": admin.email,
                "name": f"{admin.first_name} {admin.last_name}",
                "access_level": admin.access_level,
            },
        )

        return responses.JSONResponse(
            content={
                "message": "success",
            },
            status_code=200,
        )

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during save_kyc_state: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to save admin kyc state")


@admin_router.post("/kyc/complete")
async def complete_kyc(
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
):
    """Complete admin KYC"""

    context = Context(tenant_id=tenant_id)

    try:
        service = AdminService(db)
        admin = service.complete_kyc(keycloak_id, context)

        # Publish Kafka event
        KafkaClientInstance.publish_kyc_event(
            event_type=AdminEventTypes.KYC_COMPLETED,
            tenant_id=tenant_id,
            user_id=admin.id,
            kyc_status="completed",
            metadata={
                "email": admin.email,
                "name": f"{admin.first_name} {admin.last_name}",
                "access_level": admin.access_level,
            },
        )

        return responses.JSONResponse(
            content={
                "message": "success",
            },
            status_code=200,
        )

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during complete_kyc: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to complete admin kyc")
