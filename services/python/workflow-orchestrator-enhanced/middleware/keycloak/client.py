"""Keycloak client for authentication and authorization"""
import logging
from typing import List, Optional
from keycloak import KeycloakAdmin, KeycloakOpenID

logger = logging.getLogger(__name__)

class KeycloakConfig:
    def __init__(self, url: str, realm: str, client_id: str, client_secret: str, admin_user: str, admin_pass: str):
        self.url = url
        self.realm = realm
        self.client_id = client_id
        self.client_secret = client_secret
        self.admin_user = admin_user
        self.admin_pass = admin_pass

class UserInfo:
    def __init__(self, user_id: str, username: str, email: str, roles: List[str], tenant_id: str):
        self.user_id = user_id
        self.username = username
        self.email = email
        self.roles = roles
        self.tenant_id = tenant_id

class KeycloakClient:
    def __init__(self, config: KeycloakConfig):
        self.config = config
        self.admin = KeycloakAdmin(
            server_url=config.url,
            username=config.admin_user,
            password=config.admin_pass,
            realm_name="master",
            verify=True
        )
        self.admin.realm_name = config.realm
        self.openid = KeycloakOpenID(
            server_url=config.url,
            client_id=config.client_id,
            realm_name=config.realm,
            client_secret_key=config.client_secret
        )

    def validate_token(self, access_token: str) -> UserInfo:
        logger.info("Validating JWT token with Keycloak")
        userinfo = self.openid.userinfo(access_token)
        roles = userinfo.get("realm_access", {}).get("roles", [])
        return UserInfo(
            user_id=userinfo["sub"],
            username=userinfo["preferred_username"],
            email=userinfo.get("email", ""),
            roles=roles,
            tenant_id=userinfo.get("tenant_id", "")
        )

    def create_user(self, username: str, email: str, password: str) -> str:
        logger.info(f"Creating user in Keycloak: {username}")
        user_id = self.admin.create_user({
            "username": username,
            "email": email,
            "enabled": True,
            "emailVerified": True
        })
        self.admin.set_user_password(user_id, password, temporary=False)
        return user_id

    def assign_role(self, user_id: str, role_name: str) -> None:
        logger.info(f"Assigning role to user: {user_id} - {role_name}")
        role = self.admin.get_realm_role(role_name)
        self.admin.assign_realm_roles(user_id, [role])

    def close(self) -> None:
        pass
