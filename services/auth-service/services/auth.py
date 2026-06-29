from schemas.v1 import (
    CreateAuth,
    Login,
    SetupPassword,
    ForgotPassword,
    ResetPassword,
    ChangePassword,
    Context,
)
from repositories import AuthRepository, DeviceRepository
from utils import (
    ApiError,
    generate_api_key,
    create_logger,
    PermissionManager,
    UserRole,
    get_otp_service,
)
from adapters import KeycloakAdapter
from definitions import CreateKeycloakUser
from sqlalchemy.orm import Session
from utils.errors import raise_http_exception_handler

logger = create_logger(__name__)


class AuthService:
    """Auth Service"""

    def __init__(self, db: Session):
        self._db = db
        self._auth_repository = AuthRepository(db)
        self._device_repository = DeviceRepository(db)

    def create_auth(self, payload: CreateAuth, context: Context):
        auth = self._auth_repository.get_auth_by_email(payload.email, context.tenant_id)

        if auth:
            raise_http_exception_handler(
                status_code=409,
                message="User already exists.",
                code="AUTH-AUTH-INT-4001",
            )

        api_key = generate_api_key(24)
        api_secret = generate_api_key(32) + "123#"  # Password requirements

        create_keycloak_user_payload = CreateKeycloakUser(
            email=payload.email, user_name=payload.email
        )

        logger.info(f"create_keycloak_user_payload: {create_keycloak_user_payload}")

        keycloak_adapter = KeycloakAdapter(realm=context.keycloak_realm)

        logger.info(
            f"Creating Keycloak user for {payload.email} in realm {context.keycloak_realm}"
        )
        try:
            keycloak_adapter.create_user(payload=create_keycloak_user_payload)
            logger.info(f"✓ Keycloak user creation completed for {payload.email}")
        except Exception as e:
            logger.error(
                f"✗ Failed to create Keycloak user for {payload.email}: {str(e)}"
            )
            raise

        logger.info(f"Retrieving Keycloak user details for {payload.email}")
        keycloak_user = keycloak_adapter.get_user(payload.email)

        if keycloak_user is None:
            logger.error(
                f"✗ Failed to retrieve Keycloak user {payload.email} after creation"
            )
            raise ApiError(
                message="Failed to create user.",
                status_code=500,
                code="AUTH-AUTH-INT-5001",
            )

        logger.info(
            f"✓ successfully retrieved keycloak user: {keycloak_user.id} for {payload.email}"
        )

        # Create service account
        create_keycloak_service_account_payload = CreateKeycloakUser(
            email=api_key + "_" + payload.email, user_name=api_key, password=api_secret
        )

        logger.info(
            f"create_keycloak_service_account_payload: {create_keycloak_service_account_payload}"
        )

        logger.info(f"Creating service account for {payload.email}")
        try:
            keycloak_adapter.create_user(
                payload=create_keycloak_service_account_payload
            )
            logger.info(
                f"✓ successfully created keycloak service account for {payload.email}"
            )
        except Exception as e:
            logger.error(
                f"✗ Failed to create service account for {payload.email}: {str(e)}"
            )
            raise

        logger.info(f"Creating auth database record for {payload.email}")
        auth = self._auth_repository.create_auth(
            email=payload.email,
            user_role=payload.user_role,
            tenant_id=context.tenant_id,
            keycloak_id=keycloak_user.id,
            api_key=api_key,
            api_secret=api_secret,
        )

        self._db.commit()
        logger.info(f"✓ Auth database record created for {payload.email}")

        # Assign Permify v2.perm roles based on the explicit role fields
        # platform_role → assigned on `platform` entity (54agent platform-level admins)
        # tenant_role   → assigned on `tenants`  entity (bank/tenant-level staff)
        logger.info(f"Assigning Permify permissions for {payload.email}")
        self._assign_initial_permissions(
            keycloak_user_id=keycloak_user.id,
            user_role=payload.user_role,
            tenant_id=context.tenant_id,
            platform_role=payload.platform_role,
            tenant_role=payload.tenant_role,
        )
        logger.info(f"✓ Permify permissions assigned for {payload.email}")

        return auth

    def login(self, payload: Login, context: Context, device_info: dict = None) -> dict:
        """Auth Service - Login."""

        auth = self._auth_repository.get_auth_by_email(payload.email, context.tenant_id)

        if not auth:
            raise_http_exception_handler(
                status_code=401,
                message="Invalid credentials.",
                code="AUTH-AUTH-INT-4002",
            )

        logger.info(f"auth profile: {auth}")

        keycloak = KeycloakAdapter(realm=context.keycloak_realm)

        try:
            token_response = keycloak.request_user_token(auth.email, payload.password)
        except ApiError as e:
            # Handle Keycloak authentication errors (invalid password, etc.)
            logger.error(f"Keycloak authentication failed: {e.message}")

            error_description = ""
            if isinstance(e.payload, dict):
                error_description = str(e.payload.get("error_description", "")).lower()

            if "account is not fully set up" in error_description:
                raise_http_exception_handler(
                    status_code=403,
                    message="Account setup is incomplete. Please complete required account actions (for example password update or email verification) and try again.",
                    code="AUTH-AUTH-SETUP-4004",
                )

            raise_http_exception_handler(
                status_code=401,
                message="Invalid credentials.",
                code="AUTH-AUTH-INT-4003",
            )

        logger.info(f"get user token success: {token_response}")

        return {**token_response, "keycloak_id": auth.keycloak_id}

    def setup_password(self, payload: SetupPassword, context: Context) -> None:
        """Auth Service - Setup password."""

        if payload.password != payload.confirm_password:
            raise ApiError(
                message="Passwords dont match.",
                status_code=400,
                code="AUTH-AUTH-INT-5001",
            )

        auth = self._auth_repository.get_auth_by_keycloak_id(
            payload.keycloak_id, context.tenant_id
        )

        if not auth:
            raise_http_exception_handler(
                status_code=400,
                message="Invalid user.",
                code="AUTH-AUTH-INT-4003",
            )

        keycloak = KeycloakAdapter(realm=context.keycloak_realm)

        keycloak.set_user_password(payload.keycloak_id, payload.password)

    def forgot_password(self, payload: ForgotPassword, context: Context) -> dict:
        """Auth Service - Forgot password."""

        auth = self._auth_repository.get_auth_by_email(payload.email, context.tenant_id)

        if not auth:
            raise_http_exception_handler(
                status_code=404,
                message="User not found.",
                code="AUTH-AUTH-USER-4041",
            )

        otp_service = get_otp_service()
        otp_data = otp_service.generate_otp(
            keycloak_id=auth.keycloak_id,
            tenant_id=context.tenant_id,
            email=auth.email,
        )

        return {
            "message": "Password reset OTP generated.",
            "keycloak_id": auth.keycloak_id,
            "otp_expires_at": otp_data["expires_at"],
        }

    def reset_password(self, payload: ResetPassword, context: Context) -> None:
        """Auth Service - Reset password with OTP verification."""

        if payload.new_password != payload.confirm_password:
            raise_http_exception_handler(
                status_code=400,
                message="Passwords do not match.",
                code="AUTH-AUTH-RESET-4005",
            )

        if len(payload.new_password) < 8:
            raise_http_exception_handler(
                status_code=400,
                message="New password must be at least 8 characters.",
                code="AUTH-AUTH-RESET-4006",
            )

        auth = self._auth_repository.get_auth_by_keycloak_id(
            payload.keycloak_id, context.tenant_id
        )

        if not auth:
            raise_http_exception_handler(
                status_code=400,
                message="Invalid user.",
                code="AUTH-AUTH-RESET-4007",
            )

        otp_service = get_otp_service()
        otp_result = otp_service.verify_otp(
            keycloak_id=payload.keycloak_id,
            tenant_id=context.tenant_id,
            otp_code=payload.otp_code,
        )

        if not otp_result.get("valid"):
            raise_http_exception_handler(
                status_code=401,
                message=otp_result.get("message", "Invalid OTP code."),
                code="AUTH-AUTH-RESET-4011",
            )

        keycloak = KeycloakAdapter(realm=context.keycloak_realm)
        keycloak.set_user_password(payload.keycloak_id, payload.new_password)

    def change_password(
        self, payload: ChangePassword, context: Context, keycloak_id: str
    ) -> None:
        """Auth Service - Change password for authenticated user."""

        if payload.new_password != payload.confirm_password:
            raise_http_exception_handler(
                status_code=400,
                message="Passwords do not match.",
                code="AUTH-AUTH-CHANGE-4008",
            )

        if len(payload.new_password) < 8:
            raise_http_exception_handler(
                status_code=400,
                message="New password must be at least 8 characters.",
                code="AUTH-AUTH-CHANGE-4009",
            )

        if payload.current_password == payload.new_password:
            raise_http_exception_handler(
                status_code=400,
                message="New password must be different from current password.",
                code="AUTH-AUTH-CHANGE-4010",
            )

        auth = self._auth_repository.get_auth_by_keycloak_id(keycloak_id, context.tenant_id)

        if not auth:
            raise_http_exception_handler(
                status_code=404,
                message="User not found.",
                code="AUTH-AUTH-USER-4042",
            )

        keycloak = KeycloakAdapter(realm=context.keycloak_realm)

        try:
            keycloak.request_user_token(auth.email, payload.current_password)
        except ApiError:
            raise_http_exception_handler(
                status_code=401,
                message="Current password is incorrect.",
                code="AUTH-AUTH-CHANGE-4012",
            )

        keycloak.set_user_password(auth.keycloak_id, payload.new_password)

    def get_auth_by_api_key(self, key: str, secret: str, context: Context):
        return self._auth_repository.get_auth_by_api_key(key, secret, context.tenant_id)

    def _assign_initial_permissions(
        self,
        keycloak_user_id: str,
        user_role: UserRole,
        tenant_id: str,
        platform_role: str = None,
        tenant_role: str = None,
    ) -> None:
        """
        Assign v2.perm Permify roles on user creation.

        - platform_role → written to the `platform` entity (54agent-level admins)
        - tenant_role   → written to the `tenants`  entity (bank/tenant staff)
        - If neither is given, fall back to a sensible default derived from
          user_role (UserRole.SUPERADMIN → platform:super_admin, etc.)

        UserRole (SUPERADMIN/ADMIN/USER/GUEST) remains solely for Keycloak
        authentication-level routing and is never written to Permify directly.
        """
        try:
            from utils import RoleMapper

            permission_manager = PermissionManager()

            # ─── explicit platform role ──────────────────────────────────
            if platform_role:
                if RoleMapper.validate_platform_role(platform_role):
                    success = permission_manager.assign_platform_role(
                        user_id=keycloak_user_id,
                        tenant_id=tenant_id,
                        role=platform_role,
                        platform_id=tenant_id,
                    )
                    label = RoleMapper.get_platform_role_label(platform_role)
                    if success:
                        logger.info(
                            f"✓ platform:{platform_role} ({label}) → {keycloak_user_id}"
                        )
                    else:
                        logger.warning(
                            f"✗ failed: platform:{platform_role} → {keycloak_user_id}"
                        )
                else:
                    logger.warning(
                        f"Invalid platform_role '{platform_role}' — skipped. "
                        f"Valid: {PermissionManager.VALID_PLATFORM_ROLES}"
                    )

            # ─── explicit tenant role ────────────────────────────────────
            if tenant_role:
                if RoleMapper.validate_tenant_role(tenant_role):
                    success = permission_manager.assign_tenant_role(
                        user_id=keycloak_user_id,
                        tenant_id=tenant_id,
                        role=tenant_role,
                        tenant_entity_id=tenant_id,
                    )
                    label = RoleMapper.get_tenant_role_label(tenant_role)
                    if success:
                        logger.info(
                            f"✓ tenants:{tenant_role} ({label}) → {keycloak_user_id}"
                        )
                    else:
                        logger.warning(
                            f"✗ failed: tenants:{tenant_role} → {keycloak_user_id}"
                        )
                else:
                    logger.warning(
                        f"Invalid tenant_role '{tenant_role}' — skipped. "
                        f"Valid: {PermissionManager.VALID_TENANT_ROLES}"
                    )

            # ─── fallback: derive from UserRole when nothing explicit set ─
            if not platform_role and not tenant_role and user_role:
                default = RoleMapper.get_default_platform_role_for_user_role(user_role)
                if default:
                    success = permission_manager.assign_platform_role(
                        user_id=keycloak_user_id,
                        tenant_id=tenant_id,
                        role=default,
                        platform_id=tenant_id,
                    )
                    if success:
                        logger.info(
                            f"✓ platform:{default} (fallback from UserRole={user_role.value}) → {keycloak_user_id}"
                        )
                else:
                    logger.info(
                        f"No automatic Permify role for user {keycloak_user_id} "
                        f"(UserRole={user_role}). Assign via /permissions API."
                    )

        except Exception as e:
            logger.error(f"Error assigning initial Permify permissions: {str(e)}")
            # Do not fail user creation if permission assignment fails
