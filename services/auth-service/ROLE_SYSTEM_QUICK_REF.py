"""
QUICK REFERENCE: Role System

For full details, see ROLE_MIGRATION_GUIDE.md
"""

# =================================================================
# CREATING ADMINS - NOW WITH PROPER PERMIFY MAPPING
# =================================================================

# Via Orchestrator (TypeScript)
createAdminWorkflow({
    email: "admin@example.com",
    firstName: "Jane",
    lastName: "Doe",
    phone: "+1234567890",
    uin: "UIN123",
    accessLevel: "7",  # "7" = SUPER_ADMIN -> maps to Permify roles
    tenantId: "54agent",
    keycloakRealm: "54agent",
    keycloakPublicKey: "...",
})

# Result:
# 1. Auth created with user_role=ADMIN, access_level="7"
# 2. Permify roles assigned automatically:
#    - platform:super (from accessLevel "7")
#    - bank:admin (from accessLevel "7" + UserRole.ADMIN)


# =================================================================
# ACCESS LEVEL → PERMIFY ROLE MAPPING
# =================================================================

ACCESS_LEVELS = {
    "0": "Analyst - platform:analyst",
    "1": "Customer Support - platform:operations",
    "2": "Operations Officer - platform:operations",
    "3": "Finance Admin - platform:finance",
    "4": "Compliance Officer - platform:compliance, bank:compliance_officer",
    "5": "Technical Admin - platform:technical",
    "6": "Bank Admin - bank:admin",
    "7": "Super Admin - platform:super, bank:admin",
    "8": "Auditor - platform:auditor, bank:auditor",
}


# =================================================================
# TRANSLATION API USAGE
# =================================================================

# Get Permify roles for an access level
POST /permissions/translate-role
{
    "access_level": "4"
}
# Response:
# {
#   "platform_roles": ["compliance"],
#   "bank_roles": ["compliance_officer"],
#   "description": "Compliance / Risk Officer"
# }

# Get all mappings
GET /permissions/role-mappings


# =================================================================
# CHECKING PERMISSIONS (Services)
# =================================================================

from utils import PermissionManager

permission_manager = PermissionManager()

# Check permission
has_perm = permission_manager.check_user_permission(
    user_id=keycloak_id,
    tenant_id=tenant_id,
    permission="manage_branches",
    entity_type="bank",
    entity_id=bank_id
)


# =================================================================
# BACKWARD COMPATIBILITY
# =================================================================

# ✅ All existing APIs still work
# ✅ Frontend doesn't need changes
# ✅ Database schemas unchanged
# ✅ Legacy role fields (user_role, access_level) still used
# 🆕 Automatic mapping to Permify happens behind the scenes
# 🆕 All authorization checks should use Permify


# =================================================================
# KEY FILES
# =================================================================

# services/auth-service/utils/role_mapper.py
#   - RoleMapper class with all mappings
#   - get_combined_roles() - translates legacy to Permify
#   - validate_access_level() - validates "0"-"8"

# services/auth-service/api/v1/permissions.py
#   - POST /translate-role - translate legacy to Permify
#   - GET /role-mappings - get all mappings
#   - POST /assign-*-role - assign additional roles

# services/auth-service/services/auth.py
#   - _assign_initial_permissions() - auto-assigns Permify roles

# services/orchestrator-service/src/workflows/createAdminWorkflow.ts
#   - Passes accessLevel to auth service

# ROLE_MIGRATION_GUIDE.md
#   - Complete documentation
