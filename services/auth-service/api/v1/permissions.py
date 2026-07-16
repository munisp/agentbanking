"""Permify v2.perm permission management API

Entities (from v2.perm):
  - platform  → 54agent platform-level admins
  - tenants   → bank/tenant-level staff

Endpoints:
  POST  /assign-platform-role     — assign a `platform` entity role
  POST  /assign-tenant-role       — assign a `tenants` entity role
  POST  /check-permission         — check a permission on any entity
  POST  /check-permissions-batch  — check multiple permissions in one request
  DELETE /revoke-role             — revoke any role
  GET   /role-catalog             — list all valid v2.perm roles with descriptions
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi import APIRouter, Depends, Header, HTTPException, responses
from sqlalchemy.orm import Session
from typing import List, Optional
from database import get_session
from utils import create_logger, PermissionManager, RoleMapper
from utils.auth_middleware import get_current_user
from pydantic import BaseModel

logger = create_logger(__name__)

permissions_router = APIRouter()


class AssignRoleRequest(BaseModel):
    """Request model for assigning roles"""

    user_id: str
    role: str
    entity_type: str
    entity_id: str


class CheckPermissionRequest(BaseModel):
    """Request model for checking permissions"""

    user_id: str
    permission: str
    entity_type: str
    entity_id: str


class BatchPermissionItem(BaseModel):
    permission: str
    entity_type: str
    entity_id: str


class CheckPermissionsBatchRequest(BaseModel):
    checks: List[BatchPermissionItem]
    user_id: Optional[str] = None


@permissions_router.post("/assign-platform-role")
def assign_platform_role_endpoint(
    user_id: str,
    role: str,
    db: Session = Depends(get_session),
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Header(..., alias="x-tenant-id"),
):
    """
    Assign a v2.perm `platform` entity role to a user.

    Valid roles: super_admin, tenant_manager, operations_manager, risk_manager,
                 internal_auditor, it_admin, relationship_manager,
                 compliance_officer, support_agent
    """
    try:
        permission_manager = PermissionManager()

        # Only platform super_admin / it_admin may assign platform roles
        can_assign = permission_manager.check_user_permission(
            user_id=current_user.get("sub") or current_user.get("keycloak_id"),
            tenant_id=tenant_id,
            permission="manage_tenants",
            entity_type="platform",
            entity_id=tenant_id,
        )

        if not can_assign:
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to assign platform roles",
            )

        if not RoleMapper.validate_platform_role(role):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid platform role: '{role}'. Valid: {PermissionManager.VALID_PLATFORM_ROLES}",
            )

        success = permission_manager.assign_platform_role(
            user_id=user_id,
            tenant_id=tenant_id,
            role=role,
            platform_id=tenant_id,
        )

        if success:
            label = RoleMapper.get_platform_role_label(role)
            return {
                "message": f"Assigned platform role '{role}' ({label}) to user {user_id}"
            }
        raise HTTPException(status_code=500, detail="Failed to assign platform role")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error assigning platform role: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@permissions_router.post("/assign-tenant-role")
def assign_tenant_role_endpoint(
    user_id: str,
    role: str,
    tenant_entity_id: str = None,
    db: Session = Depends(get_session),
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Header(..., alias="x-tenant-id"),
):
    """
    Assign a v2.perm `tenants` entity role to a user.

    Valid roles: super_admin, branch_manager, operations_manager, risk_manager,
                 internal_auditor, it_admin, relationship_manager,
                 trade_finance_admin, vault_manager, treasury_manager,
                 loan_officer, compliance_officer, support_agent
    """
    try:
        permission_manager = PermissionManager()

        # super_admin or it_admin on the tenants entity may assign roles
        can_assign = permission_manager.check_user_permission(
            user_id=current_user.get("sub") or current_user.get("keycloak_id"),
            tenant_id=tenant_id,
            permission="manage_employees",
            entity_type="tenants",
            entity_id=tenant_entity_id or tenant_id,
        )

        if not can_assign:
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to assign tenant roles",
            )

        if not RoleMapper.validate_tenant_role(role):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid tenant role: '{role}'. Valid: {PermissionManager.VALID_TENANT_ROLES}",
            )

        success = permission_manager.assign_tenant_role(
            user_id=user_id,
            tenant_id=tenant_id,
            role=role,
            tenant_entity_id=tenant_entity_id or tenant_id,
        )

        if success:
            label = RoleMapper.get_tenant_role_label(role)
            return {
                "message": f"Assigned tenant role '{role}' ({label}) to user {user_id}"
            }
        raise HTTPException(status_code=500, detail="Failed to assign tenant role")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error assigning tenant role: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@permissions_router.post("/check-permission")
def check_permission_endpoint(
    permission: str,
    entity_type: str,
    entity_id: str,
    user_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Header(..., alias="x-tenant-id"),
):
    """
    Check if a user has a specific permission on an entity.

    entity_type must be `platform` or `tenants` (v2.perm entities).
    If user_id is omitted, the current user is checked.
    """
    try:
        permission_manager = PermissionManager()
        target_user_id = (
            user_id or current_user.get("sub") or current_user.get("keycloak_id")
        )

        has_permission = permission_manager.check_user_permission(
            user_id=target_user_id,
            tenant_id=tenant_id,
            permission=permission,
            entity_type=entity_type,
            entity_id=entity_id,
        )

        return {
            "user_id": target_user_id,
            "permission": permission,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "has_permission": has_permission,
        }
    except Exception as e:
        logger.error(f"Error checking permission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@permissions_router.post("/check-permissions-batch")
def check_permissions_batch_endpoint(
    body: CheckPermissionsBatchRequest,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Header(..., alias="x-tenant-id"),
):
    """
    Check multiple permissions in a single request.

    Accepts a list of {permission, entity_type, entity_id} checks and returns
    results for all of them, saving N-1 round-trips compared to individual calls.
    If user_id is omitted, the current user is checked.
    """
    try:
        permission_manager = PermissionManager()
        target_user_id = (
            body.user_id or current_user.get("sub") or current_user.get("keycloak_id")
        )

        def check_one(item: BatchPermissionItem) -> dict:
            try:
                has_permission = permission_manager.check_user_permission(
                    user_id=target_user_id,
                    tenant_id=tenant_id,
                    permission=item.permission,
                    entity_type=item.entity_type,
                    entity_id=item.entity_id,
                )
            except Exception as item_err:
                logger.error(f"Error checking {item.entity_type}:{item.permission} — {item_err}")
                has_permission = False
            return {
                "permission": item.permission,
                "entity_type": item.entity_type,
                "entity_id": item.entity_id,
                "has_permission": has_permission,
            }

        max_workers = min(len(body.checks), 10)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(check_one, item): item for item in body.checks}
            results = [f.result() for f in as_completed(futures)]

        return {"user_id": target_user_id, "results": results}
    except Exception as e:
        logger.error(f"Error checking permissions batch: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@permissions_router.delete("/revoke-role")
def revoke_role_endpoint(
    user_id: str,
    role: str,
    entity_type: str,
    entity_id: str,
    db: Session = Depends(get_session),
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Header(..., alias="x-tenant-id"),
):
    """Revoke a role from a user on any v2.perm entity (platform or tenants)."""
    try:
        permission_manager = PermissionManager()

        permission_needed = (
            "manage_tenants" if entity_type == "platform" else "manage_employees"
        )
        can_revoke = permission_manager.check_user_permission(
            user_id=current_user.get("sub") or current_user.get("keycloak_id"),
            tenant_id=tenant_id,
            permission=permission_needed,
            entity_type=entity_type,
            entity_id=entity_id,
        )

        if not can_revoke:
            raise HTTPException(
                status_code=403, detail="You don't have permission to revoke roles"
            )

        success = permission_manager.revoke_role(
            user_id=user_id,
            tenant_id=tenant_id,
            role=role,
            entity_type=entity_type,
            entity_id=entity_id,
        )

        if success:
            return {"message": f"Revoked role '{role}' from user {user_id}"}
        raise HTTPException(status_code=500, detail="Failed to revoke role")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error revoking role: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@permissions_router.get("/role-catalog")
def get_role_catalog(current_user: dict = Depends(get_current_user)):
    """
    List all valid v2.perm roles for both entities with human-readable descriptions.

    Use this to populate role-selection dropdowns in admin UIs.
    """
    try:
        return responses.JSONResponse(
            content={
                "message": "v2.perm role catalog",
                "platform_roles": RoleMapper.get_all_platform_roles(),
                "tenant_roles": RoleMapper.get_all_tenant_roles(),
                "notes": {
                    "platform": "Assigned on the `platform` entity — 54agent platform-level admins",
                    "tenants": "Assigned on the `tenants` entity — bank/tenant-level staff",
                    "authentication": "UserRole (superadmin/admin/user/guest) is Keycloak-only; not stored in Permify",
                },
            },
            status_code=200,
        )
    except Exception as e:
        logger.error(f"Error getting role catalog: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
