"""
Agent Scorecard — Keycloak JWT Authentication Middleware
Validates Bearer tokens issued by Keycloak, extracts claims,
and enforces role-based access control for all scorecard endpoints.
"""
import logging
import os
from functools import lru_cache
from typing import Optional, List, Dict, Any

import httpx
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError, JWTClaimsError
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────────
KEYCLOAK_BASE_URL  = os.getenv("KEYCLOAK_BASE_URL", "http://keycloak:8080")
KEYCLOAK_REALM     = os.getenv("KEYCLOAK_REALM", "54link")
KEYCLOAK_CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "agent-embedded-finance")
KEYCLOAK_AUDIENCE  = os.getenv("KEYCLOAK_AUDIENCE", "agent-embedded-finance")

JWKS_URL = f"{KEYCLOAK_BASE_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/certs"
ISSUER   = f"{KEYCLOAK_BASE_URL}/realms/{KEYCLOAK_REALM}"

ALGORITHM = "RS256"

security = HTTPBearer()


# ── Token Claims Model ─────────────────────────────────────────────────────────

class TokenClaims(BaseModel):
    sub: str                          # Keycloak user ID
    preferred_username: str           # Agent / admin username
    email: Optional[str] = None
    tenant_id: str                    # Custom claim: tenant/bank ID
    agent_id: Optional[str] = None   # Custom claim: agent ID (if agent role)
    roles: List[str] = []            # Realm roles
    resource_roles: List[str] = []   # Client-specific roles
    exp: int
    iat: int


# ── JWKS Key Fetching ──────────────────────────────────────────────────────────

class KeycloakJWKSClient:
    """Fetches and caches Keycloak public keys (JWKS) for JWT verification."""

    def __init__(self):
        self._jwks: Optional[Dict[str, Any]] = None

    async def get_jwks(self) -> Dict[str, Any]:
        """Fetch JWKS from Keycloak, with in-memory caching."""
        if self._jwks is not None:
            return self._jwks
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(JWKS_URL)
                resp.raise_for_status()
                self._jwks = resp.json()
                logger.info("Fetched Keycloak JWKS from %s", JWKS_URL)
                return self._jwks
            except Exception as e:
                logger.error("Failed to fetch Keycloak JWKS: %s", e)
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Authentication service unavailable",
                )

    def invalidate_cache(self):
        """Invalidate JWKS cache (called on key rotation)."""
        self._jwks = None


_jwks_client = KeycloakJWKSClient()


# ── JWT Verification ───────────────────────────────────────────────────────────

async def verify_token(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> TokenClaims:
    """
    FastAPI dependency that validates the Keycloak Bearer token.
    Extracts and returns structured token claims.
    """
    token = credentials.credentials

    try:
        jwks = await _jwks_client.get_jwks()

        # Decode header to get key ID
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")

        # Find the matching public key
        rsa_key = {}
        for key in jwks.get("keys", []):
            if key.get("kid") == kid:
                rsa_key = {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n":   key["n"],
                    "e":   key["e"],
                }
                break

        if not rsa_key:
            # Key not found — may need to refresh JWKS (key rotation)
            _jwks_client.invalidate_cache()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: signing key not found",
            )

        # Verify and decode the JWT
        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=[ALGORITHM],
            audience=KEYCLOAK_AUDIENCE,
            issuer=ISSUER,
            options={"verify_exp": True, "verify_iat": True},
        )

        # Extract realm roles
        realm_access = payload.get("realm_access", {})
        realm_roles = realm_access.get("roles", [])

        # Extract client-specific roles
        resource_access = payload.get("resource_access", {})
        client_access = resource_access.get(KEYCLOAK_CLIENT_ID, {})
        client_roles = client_access.get("roles", [])

        # Extract custom claims
        tenant_id = payload.get("tenant_id") or payload.get("organization") or "default"
        agent_id = payload.get("agent_id")

        return TokenClaims(
            sub=payload["sub"],
            preferred_username=payload.get("preferred_username", ""),
            email=payload.get("email"),
            tenant_id=tenant_id,
            agent_id=agent_id,
            roles=realm_roles,
            resource_roles=client_roles,
            exp=payload["exp"],
            iat=payload["iat"],
        )

    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTClaimsError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token claims: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token validation failed: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ── Role-Based Access Control ──────────────────────────────────────────────────

def require_roles(*required_roles: str):
    """
    FastAPI dependency factory that enforces role requirements.
    Usage: Depends(require_roles("agent", "super-agent"))
    """
    async def role_checker(claims: TokenClaims = Depends(verify_token)) -> TokenClaims:
        all_roles = set(claims.roles + claims.resource_roles)
        if not any(role in all_roles for role in required_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required roles: {list(required_roles)}",
            )
        return claims
    return role_checker


def require_agent_self_or_admin():
    """
    Ensures an agent can only access their own scorecard,
    while admins/super-agents can access any agent's scorecard.
    """
    async def checker(
        agent_id: str,
        claims: TokenClaims = Depends(verify_token),
    ) -> TokenClaims:
        all_roles = set(claims.roles + claims.resource_roles)
        is_admin = any(r in all_roles for r in ["admin", "super-agent", "bank-admin", "platform-admin"])

        if not is_admin:
            # Regular agent: can only access their own scorecard
            if claims.agent_id != agent_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Agents can only access their own scorecard",
                )
        return claims
    return checker


# ── Convenience Dependencies ───────────────────────────────────────────────────

# Any authenticated user
CurrentUser = Depends(verify_token)

# Admin or bank staff only
AdminUser = Depends(require_roles("admin", "bank-admin", "platform-admin"))

# Agent, super-agent, or admin
AgentOrAdmin = Depends(require_roles("agent", "super-agent", "admin", "bank-admin"))
