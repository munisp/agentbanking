"""Permission utilities for Permify integration"""

import logging
from functools import wraps
from typing import Callable
from fastapi import HTTPException
from adapters.permify import check_permission, assign_role, remove_role

logger = logging.getLogger(__name__)


def require_permission(entity_type: str, permission: str, entity_id_param: str = None):
    """
    Decorator to check if user has permission on an entity.

    Args:
        entity_type: Type of entity (e.g., 'bank', 'branch', 'customer')
        permission: Permission to check (e.g., 'view', 'edit', 'manage')
        entity_id_param: Name of the parameter containing entity_id (if None, uses tenant_id)

    Usage:
        @require_permission('bank', 'manage_branches')
        def create_branch(...):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract user_id from current_user dependency
            current_user = kwargs.get("current_user")
            if not current_user:
                raise HTTPException(status_code=401, detail="Authentication required")

            user_id = current_user.get("sub") or current_user.get("keycloak_id")

            # Extract tenant_id from headers
            tenant_id = kwargs.get("tenant_id")
            if not tenant_id:
                raise HTTPException(status_code=400, detail="Tenant ID required")

            # Get entity_id from parameters or use tenant_id
            entity_id = kwargs.get(entity_id_param) if entity_id_param else tenant_id

            # Check permission
            has_permission = check_permission(
                user_id=user_id,
                tenant_id=tenant_id,
                permission=permission,
                entity_type=entity_type,
                entity_id=entity_id,
            )

            if not has_permission:
                logger.warning(
                    f"Permission denied: user={user_id}, "
                    f"permission={permission}, entity={entity_type}:{entity_id}"
                )
                raise HTTPException(
                    status_code=403,
                    detail=f"Insufficient permissions: {permission} on {entity_type}",
                )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


class PermissionManager:
    """
    Manager class for v2.perm Permify authorization.

    v2.perm defines two top-level entities:
      - `platform`  → 54agent platform-level roles (9 roles)
      - `tenants`   → bank/tenant-level roles (13 roles)

    UserRole (SUPERADMIN, ADMIN, USER, GUEST) remains for Keycloak authentication.
    All fine-grained authorization is done via Permify with the roles below.
    """

    # v2.perm `platform` entity roles
    VALID_PLATFORM_ROLES = [
        "super_admin",
        "tenant_manager",
        "operations_manager",
        "risk_manager",
        "internal_auditor",
        "it_admin",
        "relationship_manager",
        "compliance_officer",
        "support_agent",
    ]

    # v2.perm `tenants` entity roles
    VALID_TENANT_ROLES = [
        "super_admin",
        "branch_manager",
        "operations_manager",
        "risk_manager",
        "internal_auditor",
        "it_admin",
        "relationship_manager",
        "trade_finance_admin",
        "vault_manager",
        "treasury_manager",
        "loan_officer",
        "compliance_officer",
        "support_agent",
    ]

    @staticmethod
    def assign_platform_role(
        user_id: str, tenant_id: str, role: str, platform_id: str = "default"
    ) -> bool:
        """
        Assign a v2.perm `platform` entity role to a user.

        Platform roles (54agent-level admins):
          super_admin, tenant_manager, operations_manager, risk_manager,
          internal_auditor, it_admin, relationship_manager, compliance_officer,
          support_agent
        """
        if role not in PermissionManager.VALID_PLATFORM_ROLES:
            logger.error(
                f"Invalid platform role: '{role}'. Valid: {PermissionManager.VALID_PLATFORM_ROLES}"
            )
            return False

        return assign_role(
            user_id=user_id,
            tenant_id=tenant_id,
            role=role,
            entity_type="platform",
            entity_id=platform_id,
        )

    @staticmethod
    def assign_tenant_role(
        user_id: str, tenant_id: str, role: str, tenant_entity_id: str = None
    ) -> bool:
        """
        Assign a v2.perm `tenants` entity role to a user.

        Tenant roles (bank/tenant-level staff):
          super_admin, branch_manager, operations_manager, risk_manager,
          internal_auditor, it_admin, relationship_manager, trade_finance_admin,
          vault_manager, treasury_manager, loan_officer, compliance_officer,
          support_agent
        """
        if role not in PermissionManager.VALID_TENANT_ROLES:
            logger.error(
                f"Invalid tenant role: '{role}'. Valid: {PermissionManager.VALID_TENANT_ROLES}"
            )
            return False

        entity_id = tenant_entity_id or tenant_id
        return assign_role(
            user_id=user_id,
            tenant_id=tenant_id,
            role=role,
            entity_type="tenants",
            entity_id=entity_id,
        )

    @staticmethod
    def check_user_permission(
        user_id: str, tenant_id: str, permission: str, entity_type: str, entity_id: str
    ) -> bool:
        """Check if user has a specific permission on an entity (platform or tenants)."""
        return check_permission(
            user_id=user_id,
            tenant_id=tenant_id,
            permission=permission,
            entity_type=entity_type,
            entity_id=entity_id,
        )

    @staticmethod
    def revoke_role(
        user_id: str, tenant_id: str, role: str, entity_type: str, entity_id: str
    ) -> bool:
        """Revoke a role from a user on any entity."""
        return remove_role(
            user_id=user_id,
            tenant_id=tenant_id,
            role=role,
            entity_type=entity_type,
            entity_id=entity_id,
        )
