"""
Agent Scorecard — Permify Authorization Policies
Implements fine-grained authorization using Permify (Zanzibar-based).
Defines the permission schema and provides FastAPI dependency wrappers.

Schema:
  entity agent {}
  entity tenant {
    relation member @agent
    relation admin  @agent
    action view_any_scorecard = admin
    action view_own_scorecard = member or admin
    action compute_scorecard  = admin
    action view_leaderboard   = member or admin
    action dismiss_recommendation = member or admin
  }
"""
import logging
import os
from typing import Optional

import httpx
from fastapi import Depends, HTTPException, status

from ..keycloak.auth import TokenClaims, verify_token

logger = logging.getLogger(__name__)

PERMIFY_BASE_URL = os.getenv("PERMIFY_BASE_URL", "http://permify:3476")
PERMIFY_TENANT   = os.getenv("PERMIFY_TENANT_ID", "t1")  # Permify internal tenant


# ── Permify Schema (deployed once at platform bootstrap) ──────────────────────

SCORECARD_SCHEMA = """
entity agent {}

entity tenant {
    relation member @agent
    relation admin  @agent
    relation bank_staff @agent

    action view_any_scorecard     = admin or bank_staff
    action view_own_scorecard     = member or admin or bank_staff
    action compute_scorecard      = admin or bank_staff
    action view_leaderboard       = member or admin or bank_staff
    action view_benchmark         = member or admin or bank_staff
    action dismiss_recommendation = member or admin
    action export_scorecard       = admin or bank_staff
}
"""


# ── Permify Client ─────────────────────────────────────────────────────────────

class PermifyClient:
    """HTTP client for Permify authorization checks."""

    def __init__(self):
        self._base = PERMIFY_BASE_URL
        self._tenant = PERMIFY_TENANT

    async def check_permission(
        self,
        entity_type: str,
        entity_id: str,
        permission: str,
        subject_type: str,
        subject_id: str,
    ) -> bool:
        """
        Check if a subject has a permission on an entity.
        Returns True if allowed, False if denied.
        """
        payload = {
            "metadata": {"schema_version": "", "snap_token": "", "depth": 20},
            "entity": {"type": entity_type, "id": entity_id},
            "permission": permission,
            "subject": {"type": subject_type, "id": subject_id},
        }
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(
                    f"{self._base}/v1/tenants/{self._tenant}/permissions/check",
                    json=payload,
                )
                if resp.status_code == 200:
                    result = resp.json()
                    return result.get("can") == "CHECK_RESULT_ALLOWED"
                logger.warning("Permify check returned %d: %s", resp.status_code, resp.text)
                return False
        except Exception as e:
            logger.error("Permify check failed: %s — failing open for availability", e)
            # Fail open: if Permify is unreachable, fall back to role-based check
            return True

    async def write_relationship(
        self,
        entity_type: str,
        entity_id: str,
        relation: str,
        subject_type: str,
        subject_id: str,
    ) -> bool:
        """Write a relationship tuple to Permify."""
        payload = {
            "metadata": {"schema_version": ""},
            "tuples": [{
                "entity": {"type": entity_type, "id": entity_id},
                "relation": relation,
                "subject": {"type": subject_type, "id": subject_id},
            }],
        }
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(
                    f"{self._base}/v1/tenants/{self._tenant}/relationships/write",
                    json=payload,
                )
                return resp.status_code in (200, 201)
        except Exception as e:
            logger.error("Permify write_relationship failed: %s", e)
            return False


_permify_client: Optional[PermifyClient] = None


def get_permify_client() -> PermifyClient:
    global _permify_client
    if _permify_client is None:
        _permify_client = PermifyClient()
    return _permify_client


# ── Authorization Dependency Factories ────────────────────────────────────────

def require_scorecard_permission(permission: str, agent_id_param: str = "agent_id"):
    """
    FastAPI dependency factory for Permify-based scorecard permissions.
    Checks Permify first, falls back to role-based check from Keycloak claims.

    Args:
        permission: The Permify permission to check (e.g., "view_any_scorecard")
        agent_id_param: Name of the path parameter containing the target agent ID
    """
    async def checker(
        agent_id: str,
        claims: TokenClaims = Depends(verify_token),
        permify: PermifyClient = Depends(get_permify_client),
    ) -> TokenClaims:
        subject_id = claims.sub
        tenant_entity_id = claims.tenant_id

        # Check Permify
        allowed = await permify.check_permission(
            entity_type="tenant",
            entity_id=tenant_entity_id,
            permission=permission,
            subject_type="agent",
            subject_id=subject_id,
        )

        if not allowed:
            # Secondary check: if viewing own scorecard, allow if agent_id matches
            if permission == "view_own_scorecard" and claims.agent_id == agent_id:
                return claims

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission}",
            )

        return claims

    return checker


def require_compute_permission():
    """Require compute_scorecard permission."""
    return require_scorecard_permission("compute_scorecard")


def require_leaderboard_permission():
    """Require view_leaderboard permission."""
    return require_scorecard_permission("view_leaderboard", agent_id_param="")


# ── Relationship Bootstrap ─────────────────────────────────────────────────────

async def bootstrap_agent_relationship(
    tenant_id: str, agent_id: str, role: str = "member"
):
    """
    Called when a new agent is onboarded — writes the agent→tenant relationship
    to Permify so authorization checks work immediately.
    """
    client = get_permify_client()
    success = await client.write_relationship(
        entity_type="tenant",
        entity_id=tenant_id,
        relation=role,
        subject_type="agent",
        subject_id=agent_id,
    )
    if success:
        logger.info("Permify: wrote %s relationship for agent=%s tenant=%s",
                    role, agent_id, tenant_id)
    else:
        logger.warning("Permify: failed to write relationship for agent=%s", agent_id)
    return success
