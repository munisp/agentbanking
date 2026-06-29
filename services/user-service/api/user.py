from fastapi import APIRouter, Depends, HTTPException, responses, Header
from sqlalchemy.orm import Session
from typing import Optional
import os

from utils import get_config, create_logger, KycVerificationStatus, UserRole, UserStatus
from database import get_session
from models import User
from schemas import UserSchema, CreateUserSchema, Context
from utils import UserEventTypes
from utils.kafka_instance import KafkaClientInstance
from utils.external_api_client import ExternalAPIClient

config = get_config()

logger = create_logger(__name__)

user_router = APIRouter()

@user_router.post("")
def create_user(
    payload: CreateUserSchema, 
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
):
    """Create new user."""

    context = Context(
        tenant_id=tenant_id,
        keycloak_id=keycloak_id,
    )

    existing_user = db.query(User).filter(User.email == payload.email, User.tenant_id == context.tenant_id).first()

    if existing_user:
        raise HTTPException(status_code=409, detail="User already exists.")

    user = User(
        first_name=payload.first_name,
        last_name=payload.last_name,
        name=payload.first_name + " " + payload.last_name,
        email=payload.email,
        phone_number=payload.phone,
        uin=payload.uin,
        keycloak_id=context.keycloak_id,
        user_role=UserRole.USER,
        kyc_verification_status=KycVerificationStatus.PENDING,
        tenant_id=context.tenant_id,
        # address=payload.address,
        # city=payload.city,
        # state=payload.state,
        # postal_code=payload.postal_code
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    logger.info(f"user: {user}")

    # Publish user created event
    KafkaClientInstance.publish_user_event(
        event_type=UserEventTypes.USER_CREATED,
        user_id=user.id,
        tenant_id=context.tenant_id,
        status=user.status.value if user.status else None,
        metadata={
            "email": user.email,
            "name": user.name,
            "keycloak_id": user.keycloak_id,
            "user_role": user.user_role.value if user.user_role else None
        }
    )

    return responses.JSONResponse(content={
        "message": "success",
        "user": user.to_dict(),
    }, status_code=200)

@user_router.get("/tenant")
def get_tenant_users(
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
):
    """Get user."""

    context = Context(
        tenant_id=tenant_id,
        keycloak_id=keycloak_id,
    )

    users = db.query(User).filter(User.tenant_id == context.tenant_id).order_by(User.created_at).all()

    return {
        "message": "success",
        "users": [u.to_dict() for u in users]
    }

@user_router.get("/all")
def get_all_users(
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
):
    """Get all users scoped to the requesting tenant. Requires ADMIN or SUPERADMIN role."""

    requesting_user = db.query(User).filter(
        User.keycloak_id == keycloak_id,
        User.tenant_id == tenant_id,
    ).first()

    if not requesting_user:
        raise HTTPException(status_code=403, detail="User not found in tenant.")

    if requesting_user.user_role not in (UserRole.ADMIN, UserRole.SUPERADMIN):
        raise HTTPException(status_code=403, detail="Insufficient permissions. Admin role required.")

    users = db.query(User).filter(User.tenant_id == tenant_id).order_by(User.created_at).all()

    return {
        "message": "success",
        "users": [u.to_dict() for u in users],
    }

@user_router.get("/metrics")
def get_metrics(
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
):
    """Get user."""

    total_count = db.query(User).filter(User.tenant_id == tenant_id).count()

    return {
        "message": "success",
        "metrics": { "total_count": total_count }
    }

@user_router.post("/kyc/save")
async def save_kyc_state(
    db: Session = Depends(get_session),
    payload: dict = {},
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
):
    """Complete user KYC"""

    context = Context(
        tenant_id=tenant_id,
        keycloak_id=keycloak_id,
    )
    
    user = db.query(User).filter(User.keycloak_id == keycloak_id, User.tenant_id == context.tenant_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.kyc_verification_url = payload.get("url", "")
    
    try:
        db.commit()
        db.refresh(user)
    except Exception as e:
        db.rollback()
        logger.error(f"Database error during save_kyc_state: {e}")
        raise HTTPException(status_code=500, detail="Failed to save user kyc state")
    
    # Publish KYC saved event
    KafkaClientInstance.publish_kyc_event(
        event_type=UserEventTypes.KYC_SAVED,
        user_id=user.id,
        tenant_id=context.tenant_id,
        kyc_status=user.kyc_verification_status.value if user.kyc_verification_status else None,
        metadata={
            "kyc_url": user.kyc_verification_url
        }
    )
    
    return {
        "message": "success",
    }

@user_router.post("/kyc/complete")
async def complete_kyc(
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
):
    """Complete user KYC"""

    context = Context(
        tenant_id=tenant_id,
        keycloak_id=keycloak_id,
    )
    
    user = db.query(User).filter(User.keycloak_id == keycloak_id, User.tenant_id == context.tenant_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.kyc_verification_status = KycVerificationStatus.VERIFIED
    
    try:
        db.commit()
        db.refresh(user)
    except Exception as e:
        db.rollback()
        logger.error(f"Database error during complete_kyc: {e}")
        raise HTTPException(status_code=500, detail="Failed to complete user kyc")
    
    # Publish KYC completed event
    KafkaClientInstance.publish_kyc_event(
        event_type=UserEventTypes.KYC_COMPLETED,
        user_id=user.id,
        tenant_id=context.tenant_id,
        kyc_status=user.kyc_verification_status.value,
        metadata={
            "email": user.email,
            "name": user.name
        }
    )
    
    return {
        "message": "success",
    }

@user_router.get("")
def get_user(
    keycloak_id_query: Optional[str] = None, 
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
):
    """Get user."""

    context = Context(
        tenant_id=tenant_id,
        keycloak_id=keycloak_id,
    )

    user_keycloak_id = keycloak_id_query or context.keycloak_id

    if not user_keycloak_id:
        raise HTTPException(status_code=400, detail="keycloak_id is required")

    logger.info(f"keycloak_id: {user_keycloak_id}")

    user = db.query(User).filter(User.keycloak_id == user_keycloak_id, User.tenant_id == context.tenant_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "message": "success",
        "user": user.to_dict()
    }   

@user_router.put("/{id}")
async def update_user(
    id: str,
    payload: UserSchema,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
):
    """Update user. A user may only update their own record; ADMIN/SUPERADMIN may update any record in their tenant."""

    context = Context(tenant_id=tenant_id, keycloak_id=keycloak_id)

    requesting_user = db.query(User).filter(
        User.keycloak_id == keycloak_id,
        User.tenant_id == tenant_id,
    ).first()

    if not requesting_user:
        raise HTTPException(status_code=403, detail="Requesting user not found in tenant.")

    user = db.query(User).filter(User.id == id, User.tenant_id == context.tenant_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    is_self = str(requesting_user.id) == str(id)
    is_privileged = requesting_user.user_role in (UserRole.ADMIN, UserRole.SUPERADMIN)

    if not is_self and not is_privileged:
        raise HTTPException(status_code=403, detail="Cannot update another user's record.")
    
    update_data = payload.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(user, key, value)
    
    try:
        db.commit()
        db.refresh(user)
    except Exception as e:
        db.rollback()
        logger.error(f"Database error during update_user: {e}")
        raise HTTPException(status_code=500, detail="Failed to update user")
    
    # Publish user updated event
    KafkaClientInstance.publish_user_event(
        event_type=UserEventTypes.USER_UPDATED,
        user_id=user.id,
        tenant_id=context.tenant_id,
        status=user.status.value if user.status else None,
        metadata={
            "updated_fields": list(update_data.keys()),
            "updated_by": context.keycloak_id
        }
    )
    
    return {
        "message": "User updated successfully",
        "user": user
    }

@user_router.put("/{id}/activate")
async def activate_user(
    id: str,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
):
    """Activate user. Requires ADMIN or SUPERADMIN role."""

    context = Context(tenant_id=tenant_id, keycloak_id=keycloak_id)

    requesting_user = db.query(User).filter(
        User.keycloak_id == keycloak_id,
        User.tenant_id == tenant_id,
    ).first()

    if not requesting_user:
        raise HTTPException(status_code=403, detail="Requesting user not found in tenant.")

    if requesting_user.user_role not in (UserRole.ADMIN, UserRole.SUPERADMIN):
        raise HTTPException(status_code=403, detail="Insufficient permissions. Admin role required.")

    user = db.query(User).filter(User.id == id, User.tenant_id == context.tenant_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.status = UserStatus.ACTIVE
    
    try:
        db.commit()
        db.refresh(user)
    except Exception as e:
        db.rollback()
        logger.error(f"Database error during update_user: {e}")
        raise HTTPException(status_code=500, detail="Failed to update user")
    
    # Publish user activated event
    KafkaClientInstance.publish_user_event(
        event_type=UserEventTypes.USER_ACTIVATED,
        user_id=user.id,
        tenant_id=context.tenant_id,
        status=UserStatus.ACTIVE.value,
        metadata={
            "activated_by": context.keycloak_id,
            "email": user.email
        }
    )
    
    return {
        "message": "User activated successfully",
        "user": user
    }

@user_router.put("/{id}/suspend")
async def suspend_user(
    id: str,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
):
    """Suspend user. Requires ADMIN or SUPERADMIN role. A SUPERADMIN cannot be suspended."""

    context = Context(tenant_id=tenant_id, keycloak_id=keycloak_id)

    requesting_user = db.query(User).filter(
        User.keycloak_id == keycloak_id,
        User.tenant_id == tenant_id,
    ).first()

    if not requesting_user:
        raise HTTPException(status_code=403, detail="Requesting user not found in tenant.")

    if requesting_user.user_role not in (UserRole.ADMIN, UserRole.SUPERADMIN):
        raise HTTPException(status_code=403, detail="Insufficient permissions. Admin role required.")

    user = db.query(User).filter(User.id == id, User.tenant_id == context.tenant_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.user_role == UserRole.SUPERADMIN:
        raise HTTPException(status_code=403, detail="SUPERADMIN accounts cannot be suspended.")

    if str(requesting_user.id) == str(id):
        raise HTTPException(status_code=403, detail="Cannot suspend your own account.")

    user.status = UserStatus.SUSPENDED
    
    try:
        db.commit()
        db.refresh(user)
    except Exception as e:
        db.rollback()
        logger.error(f"Database error during update_user: {e}")
        raise HTTPException(status_code=500, detail="Failed to update user")
    
    # Publish user suspended event
    KafkaClientInstance.publish_user_event(
        event_type=UserEventTypes.USER_SUSPENDED,
        user_id=user.id,
        tenant_id=context.tenant_id,
        status=UserStatus.SUSPENDED.value,
        metadata={
            "suspended_by": context.keycloak_id,
            "email": user.email
        }
    )
    
    return {
        "message": "User suspended successfully",
        "user": user
    }
@user_router.post("/kyc/liveness-check")
async def liveness_check(
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_id: str = Header(..., alias="x-keycloak-id"),
):
    """
    Perform liveness check for user KYC verification.
    Sets user verification status to NOT_VERIFIED and initializes verification with verification service.
    """

    context = Context(
        tenant_id=tenant_id,
        keycloak_id=keycloak_id,
    )
    
    # Get user
    user = db.query(User).filter(User.keycloak_id == keycloak_id, User.tenant_id == context.tenant_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Set user verification status to NOT_VERIFIED
    user.kyc_verification_status = KycVerificationStatus.NOT_VERIFIED
    
    try:
        db.commit()
        db.refresh(user)
    except Exception as e:
        db.rollback()
        logger.error(f"Database error during liveness_check: {e}")
        raise HTTPException(status_code=500, detail="Failed to update user verification status")
    
    # Initialize verification with verification service
    verification_service_url = os.getenv("VERIFICATION_SERVICE_URL", "https://54agent.upi.dev/verification")
    client_id = os.getenv("VERIFICATION_CLIENT_ID", "")
    client_secret = os.getenv("VERIFICATION_CLIENT_SECRET", "")
    
    if not client_id or not client_secret:
        logger.error("Verification service credentials not configured")
        raise HTTPException(status_code=500, detail="Verification service not configured")
    
    try:
        verification_client = ExternalAPIClient(
            base_url=verification_service_url,
            headers={
                "Content-Type": "application/json",
                "x-client-id": client_id,
                "x-client-secret": client_secret,
            }
        )
        
        # Call initialize-verification endpoint
        verification_response = verification_client._post(
            endpoint="/kyc/initialize-verification",
            data={
                "user": {
                    "firstName": user.first_name,
                    "lastName": user.last_name,
                    "phone": user.phone_number,
                    "UIN": user.uin or user.keycloak_id,
                    "dateOfBirth": ""
                },
                "identityProvider": "liveness",
                "redirectUrl": os.getenv("KYC_REDIRECT_URL", "https://kyc.54agent.upi.dev/success"),
                "metadata": {
                    "tenant_id": tenant_id,
                    "keycloak_id": keycloak_id,
                    "liveness_check": True
                }
            }
        )
        
        # Update user with verification URL
        if verification_response and verification_response.get("url"):
            user.kyc_verification_url = verification_response.get("url")
            db.commit()
            db.refresh(user)
        
        # Publish liveness check event
        KafkaClientInstance.publish_kyc_event(
            event_type=UserEventTypes.KYC_SAVED,
            user_id=user.id,
            tenant_id=context.tenant_id,
            kyc_status=user.kyc_verification_status.value,
            metadata={
                "liveness_check": True,
                "verification_id": verification_response.get("id"),
                "kyc_url": user.kyc_verification_url
            }
        )
        
        return {
            "message": "Liveness check initialized successfully",
            "user": user.to_dict(),
            "verification": verification_response
        }
        
    except Exception as e:
        logger.error(f"Failed to initialize verification: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to initialize verification: {str(e)}")