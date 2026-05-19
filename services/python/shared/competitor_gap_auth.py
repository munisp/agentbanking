"""
Shared Keycloak JWT authentication + Permify authorization middleware
for all 8 competitor-gap services.
"""
import logging
import os
from functools import lru_cache
from typing import Any, Dict, List, Optional

import httpx
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

# ─── Keycloak Config ─────────────────────────────────────────────────────────
KEYCLOAK_URL       = os.getenv("KEYCLOAK_URL", "http://keycloak:8080")
KEYCLOAK_REALM     = os.getenv("KEYCLOAK_REALM", "54link")
KEYCLOAK_CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "54link-platform")
JWKS_URI           = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/certs"
ISSUER             = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}"

# ─── Permify Config ───────────────────────────────────────────────────────────
PERMIFY_URL        = os.getenv("PERMIFY_URL", "http://permify:3476")
PERMIFY_TENANT_ID  = os.getenv("PERMIFY_TENANT_ID", "t1")

_security = HTTPBearer()

# ─── JWKS Cache ──────────────────────────────────────────────────────────────
_jwks_cache: Optional[Dict] = None


async def _get_jwks() -> Dict:
    global _jwks_cache
    if _jwks_cache:
        return _jwks_cache
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(JWKS_URI)
        resp.raise_for_status()
        _jwks_cache = resp.json()
    return _jwks_cache


async def verify_jwt(token: str) -> Dict[str, Any]:
    """Verify a Keycloak JWT token and return the decoded claims."""
    try:
        from jose import JWTError, jwt as jose_jwt
        jwks = await _get_jwks()
        # Find the matching key
        header = jose_jwt.get_unverified_header(token)
        kid = header.get("kid")
        key = None
        for k in jwks.get("keys", []):
            if k.get("kid") == kid:
                key = k
                break
        if not key:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="Invalid token: key not found")
        payload = jose_jwt.decode(
            token, key,
            algorithms=["RS256"],
            audience=KEYCLOAK_CLIENT_ID,
            issuer=ISSUER,
            options={"verify_exp": True},
        )
        return payload
    except Exception as exc:
        logger.warning("[keycloak] JWT verification failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail=f"Invalid or expired token: {exc}")


class TokenData:
    def __init__(self, payload: Dict[str, Any]):
        self.sub: str = payload.get("sub", "")
        self.preferred_username: str = payload.get("preferred_username", "")
        self.email: str = payload.get("email", "")
        self.tenant_id: str = payload.get("tenant_id",
                                          payload.get("organization", "default"))
        self.agent_id: Optional[str] = payload.get("agent_id")
        realm_access = payload.get("realm_access", {})
        self.roles: List[str] = realm_access.get("roles", [])
        resource_access = payload.get("resource_access", {})
        client_roles = resource_access.get(KEYCLOAK_CLIENT_ID, {})
        self.client_roles: List[str] = client_roles.get("roles", [])
        self.all_roles: List[str] = list(set(self.roles + self.client_roles))

    def has_role(self, role: str) -> bool:
        return role in self.all_roles

    def has_any_role(self, *roles: str) -> bool:
        return any(r in self.all_roles for r in roles)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(_security),
) -> TokenData:
    """FastAPI dependency: verify JWT and return TokenData."""
    payload = await verify_jwt(credentials.credentials)
    return TokenData(payload)


def require_roles(*required_roles: str):
    """FastAPI dependency factory: require specific roles."""
    async def _check(token_data: TokenData = Depends(get_current_user)) -> TokenData:
        if not token_data.has_any_role(*required_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required roles: {list(required_roles)}",
            )
        return token_data
    return _check


# ─── Permify Authorization ───────────────────────────────────────────────────

async def permify_check(subject_type: str, subject_id: str,
                         permission: str, entity_type: str,
                         entity_id: str, tenant_id: str = PERMIFY_TENANT_ID) -> bool:
    """Check a permission using Permify."""
    url = f"{PERMIFY_URL}/v1/tenants/{tenant_id}/permissions/check"
    body = {
        "metadata": {"schema_version": "", "snap_token": "", "depth": 20},
        "entity": {"type": entity_type, "id": entity_id},
        "permission": permission,
        "subject": {"type": subject_type, "id": subject_id},
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(url, json=body)
            if resp.status_code == 200:
                return resp.json().get("can") == "CHECK_RESULT_ALLOWED"
            logger.warning("[permify] check failed status=%d", resp.status_code)
            return False
    except Exception as exc:
        logger.error("[permify] check error: %s", exc)
        return False


def require_permission(permission: str, entity_type: str,
                        entity_id_param: str = "agent_id"):
    """FastAPI dependency factory: require a Permify permission."""
    async def _check(
        token_data: TokenData = Depends(get_current_user),
        **kwargs,
    ) -> TokenData:
        entity_id = kwargs.get(entity_id_param, token_data.agent_id or token_data.sub)
        allowed = await permify_check(
            subject_type="user",
            subject_id=token_data.sub,
            permission=permission,
            entity_type=entity_type,
            entity_id=str(entity_id),
            tenant_id=token_data.tenant_id,
        )
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission} on {entity_type}/{entity_id}",
            )
        return token_data
    return _check


# ─── Service-specific permission constants ───────────────────────────────────

class MultiSimPermissions:
    VIEW_CONNECTIVITY   = "view_connectivity"
    TRIGGER_FAILOVER    = "trigger_failover"
    CONFIGURE_SIMS      = "configure_sims"
    VIEW_ANALYTICS      = "view_analytics"


class ReversalPermissions:
    INITIATE_REVERSAL   = "initiate_reversal"
    VIEW_REVERSALS      = "view_reversals"
    APPROVE_REVERSAL    = "approve_reversal"
    VIEW_METRICS        = "view_metrics"


class WalletPermissions:
    VIEW_BALANCE        = "view_balance"
    VIEW_STATEMENT      = "view_statement"
    VIEW_LEDGER         = "view_ledger"
    EXPORT_STATEMENT    = "export_statement"
    VIEW_ALL_AGENTS     = "view_all_agents"


class CBNPermissions:
    GENERATE_REPORT     = "generate_report"
    VIEW_REPORT         = "view_report"
    SUBMIT_REPORT       = "submit_report"
    FILE_SAR            = "file_sar"
    VIEW_COMPLIANCE     = "view_compliance"


class NFCQRPermissions:
    GENERATE_QR         = "generate_qr"
    PROCESS_PAYMENT     = "process_payment"
    VIEW_TRANSACTIONS   = "view_transactions"
    CONFIGURE_NFC       = "configure_nfc"


class ReceiptPermissions:
    GENERATE_RECEIPT    = "generate_receipt"
    RESEND_RECEIPT      = "resend_receipt"
    VIEW_RECEIPTS       = "view_receipts"
    CONFIGURE_TEMPLATES = "configure_templates"


class TrainingPermissions:
    ENROLL_COURSE       = "enroll_course"
    VIEW_COURSES        = "view_courses"
    TAKE_QUIZ           = "take_quiz"
    VIEW_CERTIFICATES   = "view_certificates"
    MANAGE_COURSES      = "manage_courses"
    VIEW_COMPLIANCE     = "view_compliance"


class LiquidityPermissions:
    REQUEST_LIQUIDITY   = "request_liquidity"
    PROVIDE_LIQUIDITY   = "provide_liquidity"
    VIEW_MATCHES        = "view_matches"
    ACCEPT_MATCH        = "accept_match"
    MAKE_REPAYMENT      = "make_repayment"
    VIEW_REPUTATION     = "view_reputation"
    ADMIN_OVERRIDE      = "admin_override"
