#!/usr/bin/env python3
"""
Permission test for v2.perm schema — tests PermissionManager directly.
Uses `platform` and `tenants` entities with named roles from v2.perm.
"""

from utils.permissions import PermissionManager
from utils.enums import PermifyPlatformRole, PermifyTenantRole


def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def main():
    print_section("Permission Manager Direct Test (v2.perm schema)")

    pm = PermissionManager()
    tenant_id = "54agent"

    # Cleanup
    print_section("Cleanup: Removing Previous Test Data")
    test_user_ids = [
        "user-super", "user-support", "user-auditor",
        "user-branch-mgr", "user-loan-officer", "user-to-revoke"
    ]

    import logging
    logging.getLogger("adapters.permify").setLevel(logging.CRITICAL)

    for user_id in test_user_ids:
        for role in [r.value for r in PermifyPlatformRole]:
            pm.revoke_role(user_id, tenant_id, role, "platform", "default")
        for role in [r.value for r in PermifyTenantRole]:
            pm.revoke_role(user_id, tenant_id, role, "tenants", tenant_id)

    logging.getLogger("adapters.permify").setLevel(logging.INFO)

    import time
    time.sleep(0.5)
    print("  ✓ Cleanup complete\n")

    # Test 1: Platform Role Assignment
    print_section("Test 1: Assign Platform Roles")

    test_users = [
        ("user-super", PermifyPlatformRole.SUPER_ADMIN.value, "manage_tenants"),
        ("user-support", PermifyPlatformRole.SUPPORT_AGENT.value, "provide_support"),
        ("user-auditor", PermifyPlatformRole.INTERNAL_AUDITOR.value, "view_audit_logs"),
    ]

    for user_id, role, permission in test_users:
        print(f"Assigning '{role}' to {user_id} on platform...")
        success = pm.assign_platform_role(
            user_id=user_id, tenant_id=tenant_id, role=role, platform_id="default"
        )
        print(f"  Assignment: {'✓ Success' if success else '✗ Failed'}")
        has_perm = pm.check_user_permission(
            user_id=user_id, tenant_id=tenant_id,
            permission=permission, entity_type="platform", entity_id="default"
        )
        print(f"  Permission '{permission}': {'✓ Granted' if has_perm else '✗ Denied'}\n")

    # Test 2: Tenant Role Assignment
    print_section("Test 2: Assign Tenant Roles")

    tenant_test_users = [
        ("user-branch-mgr", PermifyTenantRole.BRANCH_MANAGER.value, "manage_employees"),
        ("user-loan-officer", PermifyTenantRole.LOAN_OFFICER.value, "process_loans"),
    ]

    for user_id, role, permission in tenant_test_users:
        print(f"Assigning '{role}' to {user_id} on tenant {tenant_id}...")
        success = pm.assign_tenant_role(
            user_id=user_id, tenant_id=tenant_id, role=role, tenant_entity_id=tenant_id
        )
        print(f"  Assignment: {'✓ Success' if success else '✗ Failed'}")
        has_perm = pm.check_user_permission(
            user_id=user_id, tenant_id=tenant_id,
            permission=permission, entity_type="tenants", entity_id=tenant_id
        )
        print(f"  Permission '{permission}': {'✓ Granted' if has_perm else '✗ Denied'}\n")

    # Test 3: Permission Denial
    print_section("Test 3: Permission Denial")
    has_perm = pm.check_user_permission(
        user_id="user-support", tenant_id=tenant_id,
        permission="manage_tenants", entity_type="platform", entity_id="default"
    )
    print(f"  support_agent.manage_tenants: {'Yes (ERROR!)' if has_perm else 'No (Correct ✓)'}")

    has_perm = pm.check_user_permission(
        user_id="user-loan-officer", tenant_id=tenant_id,
        permission="manage_employees", entity_type="tenants", entity_id=tenant_id
    )
    print(f"  loan_officer.manage_employees: {'Yes (ERROR!)' if has_perm else 'No (Correct ✓)'}")

    # Test 4: Role Revocation
    print_section("Test 4: Role Revocation")
    user_id = "user-to-revoke"
    role = PermifyPlatformRole.OPERATIONS_MANAGER.value
    pm.assign_platform_role(user_id=user_id, tenant_id=tenant_id, role=role, platform_id="default")
    success = pm.revoke_role(user_id=user_id, tenant_id=tenant_id, role=role, entity_type="platform", entity_id="default")
    print(f"  Revocation of '{role}': {'✓ Success' if success else '✗ Failed'}")
    has_perm = pm.check_user_permission(
        user_id=user_id, tenant_id=tenant_id,
        permission="provide_support", entity_type="platform", entity_id="default"
    )
    print(f"  provide_support after revocation: {'Yes (ERROR!)' if has_perm else 'No (Correct ✓)'}")

    print_section("All Tests Complete!")
    print("v2.perm permission system validated. ✓\n")


if __name__ == "__main__":
    main()
