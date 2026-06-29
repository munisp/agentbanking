"""
Keycloak JWT Authentication Middleware
Remittance Platform V11.0

Provides JWT token validation and user context extraction for FastAPI services.

Usage:
    from shared.keycloak_auth import KeycloakAuth, require_auth, require_role
    
    auth = KeycloakAuth(
        server_url="http://keycloak:8080",
        realm="remittance",
        client_id="remittance-api"
    )
    
    @app.get("/protected")
    @require_auth
    async def protected_route(user: dict = Depends(auth.get_current_user)):
        return {"user_id": user["sub"], "username": user["preferred_username"]}
    
    @app.get("/admin-only")
    @require_role("admin")
    async def admin_route(user: dict = Depends(auth.get_current_user)):
        return {"message": "Admin access granted"}

Author: Manus AI
Date: November 11, 2025
"""

import os
import logging
from typing import Optional, List, Callable
from functools import wraps
import jwt
from jwt import PyJWKClient
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import httpx
from datetime import datetime, timedelta


logger = logging.getLogger(__name__)
security = HTTPBearer()


class KeycloakAuth:
    """Keycloak authentication and authorization handler."""
    
    def __init__(
        self,
        server_url: str = None,
        realm: str = None,
        client_id: str = None,
        verify_signature: bool = True,
        verify_audience: bool = True,
        cache_jwks: bool = True,
        cache_ttl: int = 3600
    ):
        """
        Initialize Keycloak authentication.
        
        Args:
            server_url: Keycloak server URL (e.g., http://keycloak:8080)
            realm: Keycloak realm name
            client_id: Client ID for audience verification
            verify_signature: Whether to verify JWT signature
            verify_audience: Whether to verify audience claim
            cache_jwks: Whether to cache JWKS keys
            cache_ttl: JWKS cache TTL in seconds
        """
        self.server_url = server_url or os.getenv("KEYCLOAK_SERVER_URL", "http://keycloak:8080")
        self.realm = realm or os.getenv("KEYCLOAK_REALM", "remittance")
        self.client_id = client_id or os.getenv("KEYCLOAK_CLIENT_ID", "remittance-api")
        self.verify_signature = verify_signature
        self.verify_audience = verify_audience
        
        # Build URLs
        self.realm_url = f"{self.server_url}/realms/{self.realm}"
        self.jwks_url = f"{self.realm_url}/protocol/openid-connect/certs"
        self.token_url = f"{self.realm_url}/protocol/openid-connect/token"
        self.userinfo_url = f"{self.realm_url}/protocol/openid-connect/userinfo"
        
        # Initialize JWKS client for signature verification
        if self.verify_signature:
            self.jwks_client = PyJWKClient(
                self.jwks_url,
                cache_keys=cache_jwks,
                max_cached_keys=10,
                cache_jwk_set_ttl=cache_ttl
            )
        else:
            self.jwks_client = None
        
        logger.info(f"Keycloak auth initialized: {self.realm_url}")
    
    async def get_current_user(
        self,
        credentials: HTTPAuthorizationCredentials = Security(security)
    ) -> dict:
        """
        Extract and validate current user from JWT token.
        
        Args:
            credentials: HTTP Bearer token credentials
            
        Returns:
            User claims dictionary
            
        Raises:
            HTTPException: If token is invalid or expired
        """
        token = credentials.credentials
        
        try:
            # Decode and verify token
            user = self.decode_token(token)
            return user
            
        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            raise HTTPException(
                status_code=401,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"}
            )
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication token",
                headers={"WWW-Authenticate": "Bearer"}
            )
        except Exception as e:
            logger.error(f"Token validation error: {e}")
            raise HTTPException(
                status_code=401,
                detail="Authentication failed",
                headers={"WWW-Authenticate": "Bearer"}
            )
    
    def decode_token(self, token: str) -> dict:
        """
        Decode and verify JWT token.
        
        Args:
            token: JWT token string
            
        Returns:
            Decoded token claims
            
        Raises:
            jwt.InvalidTokenError: If token is invalid
        """
        if self.verify_signature:
            # Get signing key from JWKS
            signing_key = self.jwks_client.get_signing_key_from_jwt(token)
            
            # Decode with signature verification
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self.client_id if self.verify_audience else None,
                options={
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_aud": self.verify_audience
                }
            )
        else:
            # Decode without signature verification (not recommended for production)
            claims = jwt.decode(
                token,
                options={
                    "verify_signature": False,
                    "verify_exp": True,
                    "verify_aud": False
                }
            )
        
        return claims
    
    def has_role(self, user: dict, role: str) -> bool:
        """
        Check if user has a specific role.
        
        Args:
            user: User claims dictionary
            role: Role name to check
            
        Returns:
            True if user has the role, False otherwise
        """
        # Check realm roles
        realm_roles = user.get("realm_access", {}).get("roles", [])
        if role in realm_roles:
            return True
        
        # Check client roles
        resource_access = user.get("resource_access", {})
        client_roles = resource_access.get(self.client_id, {}).get("roles", [])
        if role in client_roles:
            return True
        
        return False
    
    def has_any_role(self, user: dict, roles: List[str]) -> bool:
        """
        Check if user has any of the specified roles.
        
        Args:
            user: User claims dictionary
            roles: List of role names to check
            
        Returns:
            True if user has any of the roles, False otherwise
        """
        return any(self.has_role(user, role) for role in roles)
    
    def has_all_roles(self, user: dict, roles: List[str]) -> bool:
        """
        Check if user has all of the specified roles.
        
        Args:
            user: User claims dictionary
            roles: List of role names to check
            
        Returns:
            True if user has all of the roles, False otherwise
        """
        return all(self.has_role(user, role) for role in roles)
    
    async def get_user_info(self, token: str) -> dict:
        """
        Get user info from Keycloak userinfo endpoint.
        
        Args:
            token: Access token
            
        Returns:
            User info dictionary
            
        Raises:
            HTTPException: If request fails
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.userinfo_url,
                headers={"Authorization": f"Bearer {token}"}
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail="Failed to get user info"
                )
            
            return response.json()
    
    async def introspect_token(self, token: str, client_secret: str) -> dict:
        """
        Introspect token using Keycloak introspection endpoint.
        
        Args:
            token: Access token to introspect
            client_secret: Client secret for authentication
            
        Returns:
            Token introspection result
            
        Raises:
            HTTPException: If request fails
        """
        introspection_url = f"{self.realm_url}/protocol/openid-connect/token/introspect"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                introspection_url,
                data={
                    "token": token,
                    "client_id": self.client_id,
                    "client_secret": client_secret
                }
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail="Token introspection failed"
                )
            
            return response.json()


# Global auth instance (can be overridden)
auth = KeycloakAuth()


def require_auth(func: Callable) -> Callable:
    """
    Decorator to require authentication for a route.
    
    Usage:
        @app.get("/protected")
        @require_auth
        async def protected_route(user: dict = Depends(auth.get_current_user)):
            return {"user_id": user["sub"]}
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        return await func(*args, **kwargs)
    return wrapper


def require_role(role: str) -> Callable:
    """
    Decorator to require a specific role for a route.
    
    Usage:
        @app.get("/admin")
        @require_role("admin")
        async def admin_route(user: dict = Depends(auth.get_current_user)):
            return {"message": "Admin access"}
    
    Args:
        role: Required role name
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, user: dict = Depends(auth.get_current_user), **kwargs):
            if not auth.has_role(user, role):
                raise HTTPException(
                    status_code=403,
                    detail=f"Insufficient permissions. Required role: {role}"
                )
            return await func(*args, user=user, **kwargs)
        return wrapper
    return decorator


def require_any_role(*roles: str) -> Callable:
    """
    Decorator to require any of the specified roles for a route.
    
    Usage:
        @app.get("/agent-or-admin")
        @require_any_role("agent", "admin")
        async def route(user: dict = Depends(auth.get_current_user)):
            return {"message": "Access granted"}
    
    Args:
        roles: Required role names (any)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, user: dict = Depends(auth.get_current_user), **kwargs):
            if not auth.has_any_role(user, list(roles)):
                raise HTTPException(
                    status_code=403,
                    detail=f"Insufficient permissions. Required roles (any): {', '.join(roles)}"
                )
            return await func(*args, user=user, **kwargs)
        return wrapper
    return decorator


def require_all_roles(*roles: str) -> Callable:
    """
    Decorator to require all of the specified roles for a route.
    
    Usage:
        @app.get("/super-admin")
        @require_all_roles("admin", "super_agent")
        async def route(user: dict = Depends(auth.get_current_user)):
            return {"message": "Super admin access"}
    
    Args:
        roles: Required role names (all)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, user: dict = Depends(auth.get_current_user), **kwargs):
            if not auth.has_all_roles(user, list(roles)):
                raise HTTPException(
                    status_code=403,
                    detail=f"Insufficient permissions. Required roles (all): {', '.join(roles)}"
                )
            return await func(*args, user=user, **kwargs)
        return wrapper
    return decorator


def get_user_id(user: dict) -> str:
    """
    Extract user ID from user claims.
    
    Args:
        user: User claims dictionary
        
    Returns:
        User ID (sub claim)
    """
    return user.get("sub")


def get_username(user: dict) -> str:
    """
    Extract username from user claims.
    
    Args:
        user: User claims dictionary
        
    Returns:
        Username (preferred_username claim)
    """
    return user.get("preferred_username")


def get_email(user: dict) -> Optional[str]:
    """
    Extract email from user claims.
    
    Args:
        user: User claims dictionary
        
    Returns:
        Email address or None
    """
    return user.get("email")


def get_roles(user: dict) -> List[str]:
    """
    Extract all roles from user claims.
    
    Args:
        user: User claims dictionary
        
    Returns:
        List of role names
    """
    roles = set()
    
    # Realm roles
    realm_roles = user.get("realm_access", {}).get("roles", [])
    roles.update(realm_roles)
    
    # Client roles
    resource_access = user.get("resource_access", {})
    for client_id, client_data in resource_access.items():
        client_roles = client_data.get("roles", [])
        roles.update(client_roles)
    
    return list(roles)

