from fastapi import APIRouter, Depends, HTTPException, responses, Header
from sqlalchemy.orm import Session
from schemas.v1 import (
    CreateAuth,
    Login,
    SetupPassword,
    ForgotPassword,
    ResetPassword,
    ChangePassword,
    Context,
    AuditEventSchema,
    DeviceResponse,
    DeleteDeviceResponse,
    VerifyOTP,
)
from database import get_session
from utils import (
    get_config,
    create_logger,
    UserRole,
    detect_vpn,
    get_failed_login_tracker,
    get_otp_service,
)
from services import AuthService
from utils.errors import raise_http_exception_handler
from adapters import AuditServiceAdapter
from datetime import datetime
from utils.kafka_instance import KafkaClientInstance
from utils.kafka_client import AuthEventTypes
from utils.auth_middleware import get_current_user
from repositories import DeviceRepository
from typing import List

config = get_config()

logger = create_logger(__name__)

auth_router = APIRouter()

DEFAULT_TENANT_ID = "54agent"
DEFAULT_KEYCLOAK_REALM = config.DEFAULT_KEYCLOAK_REALM
DEFAULT_KEYCLOAK_PUBLIC_KEY = config.DEFAULT_KEYCLOAK_PUBLIC_KEY


@auth_router.post("")
def create_auth(
    payload: CreateAuth,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_realm: str = Header(..., alias="x-keycloak-realm"),
    keycloak_pub_key: str = Header(..., alias="x-keycloak-pub-key"),
):
    """Create auth route handler."""

    try:
        auth_service = AuthService(db)

        context = Context(
            tenant_id=tenant_id,
            keycloak_realm=keycloak_realm,
            keycloak_pub_key=keycloak_pub_key,
        )

        auth = auth_service.create_auth(payload, context)

        # Publish Kafka event for auth creation
        KafkaClientInstance.publish_auth_event(
            event_type=AuthEventTypes.AUTH_CREATED,
            user_id=auth.id,
            tenant_id=tenant_id,
            status=None,
            metadata={
                "email": getattr(auth, "email", None),
                "username": getattr(auth, "username", None),
                "keycloak_id": getattr(auth, "keycloak_id", None),
            },
        )

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


@auth_router.post("/login")
def login(
    payload: Login,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_realm: str = Header(..., alias="x-keycloak-realm"),
    keycloak_pub_key: str = Header(..., alias="x-keycloak-pub-key"),
    user_agent: str = Header("Unknown", alias="user-agent"),
    x_forwarded_for: str = Header(None, alias="x-forwarded-for"),
    x_device_id: str = Header(None, alias="x-device-id"),
):
    """Login route handler"""

    try:
        auth_service = AuthService(db)
        device_repository = DeviceRepository(db)
        failed_login_tracker = get_failed_login_tracker(db)

        # Get client IP (handles proxy scenarios)
        client_ip = (
            x_forwarded_for.split(",")[0].strip() if x_forwarded_for else "unknown"
        )

        logger.info(
            f"Login attempt from IP: {client_ip}, User-Agent: {user_agent}, Device-ID: {x_device_id}"
        )

        # VPN/Proxy/Tor Detection
        vpn_detection = detect_vpn(client_ip)
        logger.info(f"VPN Detection for IP {client_ip}: {vpn_detection}")

        # Block VPN/Tor/Datacenter IPs based on config
        if config.BLOCK_TOR and vpn_detection.get("is_tor"):
            logger.warning(
                f"Login attempt blocked - Tor network detected from IP: {client_ip}"
            )
            raise_http_exception_handler(
                status_code=403,
                message="Login from Tor network is not allowed for security reasons.",
                code="AUTH-AUTH-TOR-4030",
            )

        if config.BLOCK_VPN and vpn_detection.get("is_vpn"):
            logger.warning(f"Login attempt blocked - VPN detected from IP: {client_ip}")
            raise_http_exception_handler(
                status_code=403,
                message="Login from VPN is not allowed. Please disable your VPN and try again.",
                code="AUTH-AUTH-VPN-4031",
            )

        if config.BLOCK_DATACENTER and vpn_detection.get("is_datacenter"):
            logger.warning(
                f"Login attempt blocked - Datacenter IP detected: {client_ip}"
            )
            raise_http_exception_handler(
                status_code=403,
                message="Login from datacenter IPs is not allowed for security reasons.",
                code="AUTH-AUTH-DC-4032",
            )

        logger.info(f"Login payload: email={payload.email}, type={payload.type}")

        if payload.type and payload.type is UserRole.SUPERADMIN:
            context = Context(
                tenant_id=DEFAULT_TENANT_ID,
                keycloak_realm=DEFAULT_KEYCLOAK_REALM,
                keycloak_pub_key=DEFAULT_KEYCLOAK_PUBLIC_KEY,
            )
        else:
            context = Context(
                tenant_id=tenant_id,
                keycloak_realm=keycloak_realm,
                keycloak_pub_key=keycloak_pub_key,
            )

        # Get device information
        device_info = {
            "user_agent": user_agent,
            "ip_address": client_ip,
            "device_id": x_device_id,
        }

        # Generate device fingerprint
        device_fingerprint = device_repository.generate_device_id(user_agent, client_ip)

        # Check if device is already trusted BEFORE login (so we can determine auth_stepup)
        # Get user by email first (doesn't require authentication)
        auth_user = auth_service._auth_repository.get_auth_by_email(
            payload.email, context.tenant_id
        )
        is_device_trusted = False

        if auth_user:
            existing_device = device_repository.get_trusted_device_by_keycloak(
                device_id=device_fingerprint,
                keycloak_id=auth_user.keycloak_id,
                tenant_id=context.tenant_id,
            )
            is_device_trusted = existing_device is not None

        logger.info(
            f"Device trusted status (before login): {is_device_trusted} for device {device_fingerprint}"
        )

        # Perform login (this will raise exception if credentials are invalid)
        try:
            token_response = auth_service.login(payload, context, device_info)
        except HTTPException as login_error:
            error_detail = (
                login_error.detail if isinstance(login_error.detail, dict) else {}
            )
            error_code = error_detail.get("code")

            if error_code == "AUTH-AUTH-SETUP-4004":
                logger.warning(
                    f"Login blocked for {payload.email} due to incomplete Keycloak account setup"
                )
                raise login_error

            # Login failed - record failed attempt
            logger.warning(
                f"Login failed for {payload.email} - Recording failed attempt"
            )

            attempt_result = failed_login_tracker.record_failed_attempt(
                email=payload.email,
                tenant_id=context.tenant_id,
                keycloak_id=auth_user.keycloak_id if auth_user else None,
            )

            # If account was suspended, return specific message
            if attempt_result["suspended"]:
                raise_http_exception_handler(
                    status_code=403,
                    message=f"Account suspended due to multiple failed login attempts ({failed_login_tracker.MAX_ATTEMPTS}). Please contact support.",
                    code="AUTH-AUTH-SUSPENDED-4033",
                )

            # Return error with remaining attempts count
            remaining = attempt_result["remaining"]
            attempts = attempt_result["attempts"]

            if remaining > 0:
                raise_http_exception_handler(
                    status_code=401,
                    message=f"Invalid credentials. {remaining} attempt(s) remaining before account suspension.",
                    code="AUTH-AUTH-INVALID-4002",
                )
            else:
                raise_http_exception_handler(
                    status_code=403,
                    message="Maximum login attempts exceeded. Account will be suspended.",
                    code="AUTH-AUTH-MAX-ATTEMPTS-4034",
                )

        # Login successful - reset failed attempts counter
        if auth_user:
            failed_login_tracker.reset_attempts(
                email=payload.email, tenant_id=context.tenant_id
            )
            logger.info(f"Login successful - Reset failed attempts for {payload.email}")

        if token_response is not None:
            AuditServiceAdapter().create_audit(
                payload=AuditEventSchema(
                    actor_id=token_response.get("keycloak_id", payload.email),
                    tenant_id=context.tenant_id,
                    event_type="LOGIN",
                    event_data={
                        "email": payload.email,
                        "type": payload.type.value if payload.type else "N/A",
                    },
                    timestamp=datetime.utcnow().isoformat(),
                ),
                context=context,
            )

        # Always save/update device on successful login
        device_repository.create_or_update_trusted_device(
            device_id=device_fingerprint,
            device_ip=client_ip,
            user_agent=user_agent,
            user_email=payload.email,
            tenant_id=context.tenant_id,
            keycloak_id=auth_user.keycloak_id if auth_user else "",
        )
        db.commit()
        logger.info(
            f"Device {'updated' if is_device_trusted else 'added'}: {device_fingerprint} for user {payload.email}"
        )

        # Check if OTP is required (auth_stepup = true means new/untrusted device)
        if not is_device_trusted:
            # Generate OTP for authentication step-up
            otp_service = get_otp_service()
            otp_data = otp_service.generate_otp(
                keycloak_id=auth_user.keycloak_id,
                tenant_id=context.tenant_id,
                email=payload.email,
            )

            logger.info(
                f"🔐 OTP required for untrusted device. OTP generated for {payload.email}"
            )

            return {
                "message": "OTP required for verification",
                "auth_stepup": True,
                "otp_required": True,
                "keycloak_id": auth_user.keycloak_id,
                "otp_expires_at": otp_data["expires_at"],
                # Token will be provided after OTP verification
            }

        # Trusted device - return token immediately
        return {
            "message": "success",
            **token_response,
            "auth_stepup": False,
            "otp_required": False,
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during login: {e}")
        raise_http_exception_handler(
            status_code=401,
            message="Login failed. Please check your credentials and try again.",
            code="AUTH-AUTH-INT-5001",
        )


@auth_router.post("/verify-otp")
def verify_otp(
    payload: VerifyOTP,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_realm: str = Header(..., alias="x-keycloak-realm"),
    keycloak_pub_key: str = Header(..., alias="x-keycloak-pub-key"),
):
    """
    Verify OTP for authentication step-up.
    Called after login when auth_stepup is true.
    """

    try:
        otp_service = get_otp_service()
        auth_service = AuthService(db)

        context = Context(
            tenant_id=tenant_id,
            keycloak_realm=keycloak_realm,
            keycloak_pub_key=keycloak_pub_key,
        )

        logger.info(f"OTP verification attempt for keycloak_id: {payload.keycloak_id}")

        # Verify the OTP
        verification_result = otp_service.verify_otp(
            keycloak_id=payload.keycloak_id,
            tenant_id=tenant_id,
            otp_code=payload.otp_code,
        )

        if not verification_result["valid"]:
            # OTP verification failed
            logger.warning(
                f"OTP verification failed for keycloak_id: {payload.keycloak_id} - {verification_result['message']}"
            )
            raise_http_exception_handler(
                status_code=401,
                message=verification_result["message"],
                code="AUTH-OTP-INVALID-4010",
            )

        # OTP verified successfully - generate and return tokens
        logger.info(
            f"✅ OTP verified successfully for keycloak_id: {payload.keycloak_id}"
        )

        # Get user details to generate token
        auth_user = auth_service._auth_repository.get_auth_by_keycloak_id(
            payload.keycloak_id, tenant_id
        )

        if not auth_user:
            raise_http_exception_handler(
                status_code=404,
                message="User not found.",
                code="AUTH-USER-NOT-FOUND-4040",
            )

        # Generate token using Keycloak (need to get user credentials)
        # For now, we'll return a success message
        # In production, you might want to generate a session token or use refresh token flow

        # Publish audit event
        AuditServiceAdapter().create_audit(
            payload=AuditEventSchema(
                actor_id=payload.keycloak_id,
                tenant_id=tenant_id,
                event_type="OTP_VERIFIED",
                event_data={
                    "keycloak_id": payload.keycloak_id,
                    "email": auth_user.email,
                },
                timestamp=datetime.utcnow().isoformat(),
            ),
            context=context,
        )

        return {
            "message": "OTP verified successfully. Authentication complete.",
            "verified": True,
            "keycloak_id": payload.keycloak_id,
            "email": auth_user.email,
            # Note: In production, you would return access_token and refresh_token here
            # For now, the frontend should make another request or use stored tokens
        }

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during OTP verification: {e}")
        raise_http_exception_handler(
            status_code=500,
            message="OTP verification failed.",
            code="AUTH-OTP-INT-5010",
        )


@auth_router.post("/setup-password")
def setup_password(
    payload: SetupPassword,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_realm: str = Header(..., alias="x-keycloak-realm"),
    keycloak_pub_key: str = Header(..., alias="x-keycloak-pub-key"),
):
    """Setup user password."""

    try:
        auth_service = AuthService(db)

        context = Context(
            tenant_id=tenant_id,
            keycloak_realm=keycloak_realm,
            keycloak_pub_key=keycloak_pub_key,
        )

        auth_service.setup_password(payload, context)

        return {"message": "success"}
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during password update: {e}")
        raise_http_exception_handler(
            status_code=500,
            message="Failed to update password.",
            code="AUTH-AUTH-INT-5002",
        )


@auth_router.post("/forgot-password")
def forgot_password(
    payload: ForgotPassword,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_realm: str = Header(..., alias="x-keycloak-realm"),
    keycloak_pub_key: str = Header(..., alias="x-keycloak-pub-key"),
):
    """Generate OTP for password reset."""

    try:
        auth_service = AuthService(db)

        context = Context(
            tenant_id=tenant_id,
            keycloak_realm=keycloak_realm,
            keycloak_pub_key=keycloak_pub_key,
        )

        result = auth_service.forgot_password(payload, context)
        return result
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during forgot password: {e}")
        raise_http_exception_handler(
            status_code=500,
            message="Failed to process forgot password request.",
            code="AUTH-AUTH-INT-5003",
        )


@auth_router.post("/reset-password")
def reset_password(
    payload: ResetPassword,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
    keycloak_realm: str = Header(..., alias="x-keycloak-realm"),
    keycloak_pub_key: str = Header(..., alias="x-keycloak-pub-key"),
):
    """Reset password using OTP."""

    try:
        auth_service = AuthService(db)

        context = Context(
            tenant_id=tenant_id,
            keycloak_realm=keycloak_realm,
            keycloak_pub_key=keycloak_pub_key,
        )

        auth_service.reset_password(payload, context)
        return {"message": "Password reset successfully."}
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during reset password: {e}")
        raise_http_exception_handler(
            status_code=500,
            message="Failed to reset password.",
            code="AUTH-AUTH-INT-5004",
        )


@auth_router.post("/change-password")
def change_password(
    payload: ChangePassword,
    db: Session = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """Change password for authenticated user."""

    try:
        auth_service = AuthService(db)
        context = current_user["context"]

        auth_service.change_password(payload, context, current_user["keycloak_id"])
        return {"message": "Password changed successfully."}
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during change password: {e}")
        raise_http_exception_handler(
            status_code=500,
            message="Failed to change password.",
            code="AUTH-AUTH-INT-5005",
        )


@auth_router.get("/devices", response_model=List[DeviceResponse])
def get_user_devices(
    db: Session = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """Get all trusted devices for the current user."""
    try:
        device_repository = DeviceRepository(db)

        logger.info(
            f"Fetching devices for keycloak_id: {current_user['keycloak_id']}, tenant: {current_user['tenant_id']}"
        )

        devices = device_repository.get_user_devices_by_keycloak_id(
            keycloak_id=current_user["keycloak_id"],
            tenant_id=current_user["tenant_id"],
        )

        logger.info(f"Found {len(devices)} devices")

        return devices
    except Exception as e:
        logger.error(f"Error retrieving devices: {e}")
        raise_http_exception_handler(
            status_code=500,
            message="Failed to retrieve devices.",
            code="AUTH-DEVICE-INT-5001",
        )


@auth_router.delete("/devices/{device_id}", response_model=DeleteDeviceResponse)
def delete_trusted_device(
    device_id: str,
    db: Session = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """Delete a trusted device for the current user."""
    try:
        device_repository = DeviceRepository(db)

        # Get the device to verify ownership
        device = device_repository.get_trusted_device_by_keycloak(
            device_id=device_id,
            keycloak_id=current_user["keycloak_id"],
            tenant_id=current_user["tenant_id"],
        )

        if not device:
            raise_http_exception_handler(
                status_code=404,
                message="Device not found or you don't have permission to delete it.",
                code="AUTH-DEVICE-INT-4001",
            )

        db.delete(device)
        db.commit()

        logger.info(f"Device {device_id} deleted for user {current_user['email']}")

        return DeleteDeviceResponse(
            message="Device deleted successfully",
            device_id=device_id,
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error deleting device: {e}")
        db.rollback()
        raise_http_exception_handler(
            status_code=500,
            message="Failed to delete device.",
            code="AUTH-DEVICE-INT-5002",
        )
