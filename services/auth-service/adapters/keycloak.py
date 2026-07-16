from utils import ExternalAPIClient, get_config, ApiError, create_logger
from definitions import CreateKeycloakUser, GetKeycloakUserResponse
from urllib.parse import urlencode, quote

config = get_config()
logger = create_logger(__name__)


class KeycloakAdapter(ExternalAPIClient):
    """Keycloak adapter."""

    def __init__(self, realm: str):
        self.__realm = realm
        self.headers = {}

        ExternalAPIClient.__init__(self, base_url=config.KEYCLOAK_BASE_URL, headers={})

    def __initialize(self) -> None:
        """Initialize keycloak client"""

        self.headers["Content-Type"] = "application/json"
        self.headers["Authorization"] = f"Bearer {self.request_admin_cli_token()}"

    def request_admin_cli_token(self):
        """Request an admin access token from keycloak."""

        data = {
            "client_id": "admin-cli",
            "username": config.KEYCLOAK_ADMIN_USERNAME,
            "password": config.KEYCLOAK_ADMIN_PASSWORD,
            "grant_type": "password",
        }

        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        response = self._post(
            endpoint="/realms/master/protocol/openid-connect/token",
            data=urlencode(data),
            headers=headers,
        )

        access_token = response.get("access_token", "")

        if not access_token:
            raise ApiError(
                message="Failed to fetch keycloak admin token.",
                status_code=500,
                code="AUTH-KEYCLOAK-INT-5001",
            )

        return access_token

    def create_user(self, payload: CreateKeycloakUser) -> None:
        """Create new keycloak user."""

        self.__initialize()

        create_user_payload = {
            "username": payload.user_name,
            "email": payload.email,
            "enabled": True,
            "emailVerified": True,
        }

        if payload.password:
            create_user_payload["credentials"] = [
                {"type": "password", "value": payload.password, "temporary": False}
            ]

        logger.info(f"create_user_payload: {create_user_payload}")

        response = self._post(
            endpoint=f"/admin/realms/{self.__realm}/users",
            data=create_user_payload,
            headers=self.headers,
            get_response=False,
        )

        status_code = response.get("status_code")

        logger.info(f"create_user_status_code: {status_code}")

        logger.info(response)

        # 201 = success, user created
        if status_code == 201:
            logger.info(f"Successfully created Keycloak user: {payload.email}")
            return

        # 409 = user already exists
        if status_code == 409:
            logger.warning(
                f"User {payload.email} already exists in Keycloak (409 Conflict). "
                "This may be from a previous failed creation attempt. Continuing..."
            )
            return  # Don't fail - user exists, continue with workflow

        # Any other non-201 status is an error
        logger.error(
            f"Failed to create Keycloak user {payload.email}. "
            f"Status: {status_code}, Response: {response}"
        )
        raise ApiError(
            message=f"Failed to create user in Keycloak (status {status_code}).",
            status_code=500,
            code="AUTH-KEYCLOAK-INT-5002",
        )

    def assign_role_to_user(self, user_id: str, role_name: str) -> None:
        """Assign role to user."""

        # 1. Get the role details
        role_response = self._get(
            endpoint=f"/admin/realms/{self.__realm}/roles/{role_name}",
            headers=self.headers,
        )

        logger.info(f"role_response: {role_response}")

        # 2. Assign role to user
        assign_payload = [
            {"id": role_response.get("id", ""), "name": role_response.get("name", "")}
        ]

        assign_response = self._post(
            endpoint=f"/admin/realms/{self.__realm}/users/{user_id}/role-mappings/realm",
            data=assign_payload,
            headers=self.headers,
            get_response=False,
        )

        logger.info(f"assign_response: {assign_response}")

        logger.info(f"Successfully assigned role '{role_name}' to user {user_id}")

    def set_user_password(self, id: str, password: str) -> None:
        """Setup a keycloak user's password."""

        self.__initialize()

        set_user_password_payload = {
            "type": "password",
            "value": password,
            "temporary": False,
        }

        logger.info(f"set_user_password_payload: {set_user_password_payload}")

        response = self._put(
            endpoint=f"/admin/realms/{self.__realm}/users/{id}/reset-password",
            data=set_user_password_payload,
            headers=self.headers,
            get_response=False,
        )

        status_code = response.get("status_code")

        logger.info(f"set_user_password_status_code: {status_code}")

        if status_code != 204:
            raise ApiError(
                message="Failed to set user password.",
                status_code=500,
                code="AUTH-KEYCLOAK-INT-5003",
            )

    def get_user(self, email: str):
        """Get a keycloak user."""

        self.__initialize()

        users = self._get(
            endpoint=f"/admin/realms/{self.__realm}/users?email={quote(email)}"
        )

        if users and len(users) > 0:
            return GetKeycloakUserResponse.model_validate(users[0])

        return None

    def request_user_token(self, username: str, password: str) -> dict:
        """Request a user access token from keycloak."""

        self.__initialize()

        data = {
            "client_id": "admin-cli",
            "username": username,
            "password": password,
            "grant_type": "password",
        }

        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        return self._post(
            endpoint=f"/realms/{self.__realm}/protocol/openid-connect/token",
            data=urlencode(data),
            headers=headers,
        )

    def refresh_user_token(self, refresh_token: str) -> dict:
        """Refresh a user access token."""

        data = {
            "client_id": "admin-cli",
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }

        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        return self._post(
            endpoint=f"/realms/{self.__realm}/protocol/openid-connect/token",
            data=urlencode(data),
            headers=headers,
        )
