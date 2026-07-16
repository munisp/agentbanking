"""
Agent Embedded Finance — Permify Authorization Policies
Fine-grained authorization for loan and BNPL operations.

Schema:
  entity agent {}
  entity tenant {
    relation member     @agent   -- regular agent
    relation admin      @agent   -- bank admin
    relation credit_ops @agent   -- credit operations staff

    action apply_for_loan       = member or admin
    action view_own_loans       = member or admin or credit_ops
    action view_any_loans       = admin or credit_ops
    action disburse_loan        = admin or credit_ops
    action make_repayment       = member or admin
    action create_bnpl_order    = member or admin
    action view_credit_profile  = member or admin or credit_ops
    action update_credit_limit  = admin or credit_ops
    action view_portfolio       = member or admin or credit_ops
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
PERMIFY_TENANT   = os.getenv("PERMIFY_TENANT_ID", "t1")

FINANCE_SCHEMA = """
entity agent {}
entity tenant {
    relation member     @agent
    relation admin      @agent
    relation credit_ops @agent

    action apply_for_loan       = member or admin
    action view_own_loans       = member or admin or credit_ops
    action view_any_loans       = admin or credit_ops
    action disburse_loan        = admin or credit_ops
    action make_repayment       = member or admin
    action create_bnpl_order    = member or admin
    action view_credit_profile  = member or admin or credit_ops
    action update_credit_limit  = admin or credit_ops
    action view_portfolio       = member or admin or credit_ops
}
"""


class PermifyClient:
    def __init__(self):
        self._base = PERMIFY_BASE_URL
        self._tenant = PERMIFY_TENANT

    async def check_permission(self, entity_type, entity_id, permission,
                                subject_type, subject_id) -> bool:
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
                    return resp.json().get("can") == "CHECK_RESULT_ALLOWED"
                return False
        except Exception as e:
            logger.error("Permify check failed: %s — failing open", e)
            return True

    async def write_relationship(self, entity_type, entity_id, relation,
                                  subject_type, subject_id) -> bool:
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


def require_finance_permission(permission: str):
    async def checker(
        claims: TokenClaims = Depends(verify_token),
        permify: PermifyClient = Depends(get_permify_client),
    ) -> TokenClaims:
        allowed = await permify.check_permission(
            entity_type="tenant",
            entity_id=claims.tenant_id,
            permission=permission,
            subject_type="agent",
            subject_id=claims.sub,
        )
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission}",
            )
        return claims
    return checker


async def bootstrap_agent_finance_relationship(tenant_id: str, agent_id: str,
                                                role: str = "member"):
    client = get_permify_client()
    return await client.write_relationship(
        entity_type="tenant",
        entity_id=tenant_id,
        relation=role,
        subject_type="agent",
        subject_id=agent_id,
    )
