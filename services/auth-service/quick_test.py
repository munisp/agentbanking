#!/usr/bin/env python3
"""Quick test of Permify integration"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✓ Environment variables loaded from .env")
except ImportError:
    print("⚠ python-dotenv not installed, skipping .env file")
except Exception as e:
    print(f"⚠ Could not load .env file: {e}")

# Set PERMIFY_URL if not already set
if not os.getenv('PERMIFY_URL'):
    os.environ['PERMIFY_URL'] = 'http://localhost:3476'
    print("⚠ PERMIFY_URL not set, using default: http://localhost:3476")

def test_imports():
    """Test if all imports work"""
    print("Testing imports...")
    try:
        from adapters.permify import load_schema, check_permission, assign_role
        from utils.permissions import PermissionManager
        print("✓ All imports successful")
        return True
    except Exception as e:
        print(f"✗ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_schema_load():
    """Test schema loading"""
    print("\nTesting schema load...")
    try:
        from adapters.permify import load_schema
        load_schema()
        print("✓ Schema loaded successfully")
        return True
    except Exception as e:
        print(f"✗ Schema load failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_permission_check():
    """Test permission check"""
    print("\nTesting permission check...")
    try:
        from adapters.permify import check_permission
        result = check_permission(
            user_id="test-user-123",
            tenant_id="54agent",
            permission="view_all_data",
            entity_type="platform",
            entity_id="default"
        )
        print(f"✓ Permission check works (result: {result})")
        return True
    except Exception as e:
        print(f"✗ Permission check failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_role_assignment():
    """Test role assignment"""
    print("\nTesting role assignment...")
    try:
        from adapters.permify import assign_role
        result = assign_role(
            user_id="test-user-123",
            tenant_id="54agent",
            role="super",
            entity_type="platform",
            entity_id="default"
        )
        if result:
            print("✓ Role assignment successful")
            return True
        else:
            print("✗ Role assignment returned False")
            return False
    except Exception as e:
        print(f"✗ Role assignment failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_permission_after_assignment():
    """Test permission check after role assignment"""
    print("\nTesting permission after assignment...")
    try:
        from adapters.permify import check_permission
        result = check_permission(
            user_id="test-user-123",
            tenant_id="54agent",
            permission="view_all_data",
            entity_type="platform",
            entity_id="default"
        )
        if result:
            print("✓ User now has permission")
            return True
        else:
            print("✗ User still doesn't have permission")
            return False
    except Exception as e:
        print(f"✗ Permission verification failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_permission_manager():
    """Test PermissionManager class"""
    print("\nTesting PermissionManager...")
    try:
        from utils.permissions import PermissionManager
        pm = PermissionManager()
        
        # Test platform role
        success = pm.assign_platform_role(
            user_id="test-user-456",
            tenant_id="54agent",
            role="analyst",
            platform_id="default"
        )
        
        if not success:
            print("✗ Platform role assignment failed")
            return False
        
        # Test permission check
        has_perm = pm.check_user_permission(
            user_id="test-user-456",
            tenant_id="54agent",
            permission="view_analytics",
            entity_type="platform",
            entity_id="default"
        )
        
        if has_perm:
            print("✓ PermissionManager works correctly")
            return True
        else:
            print("✗ Permission check failed")
            return False
            
    except Exception as e:
        print(f"✗ PermissionManager test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("Permify Integration Quick Test")
    print("=" * 50)
    
    tests = [
        ("Imports", test_imports),
        ("Schema Load", test_schema_load),
        ("Permission Check", test_permission_check),
        ("Role Assignment", test_role_assignment),
        ("Permission After Assignment", test_permission_after_assignment),
        ("Permission Manager", test_permission_manager),
    ]
    
    passed = 0
    total = len(tests)
    
    for name, test_func in tests:
        if test_func():
            passed += 1
        else:
            print(f"\n⚠️  Test '{name}' failed, stopping here.")
            break
    
    print("\n" + "=" * 50)
    if passed == total:
        print(f"✅ All {total} tests passed!")
        print("=" * 50)
        print("\nYou can now:")
        print("  1. Start the service: source venv/bin/activate && uvicorn main:app --reload --port 8001")
        print("  2. Test API: curl http://localhost:8001/health")
        print("  3. View docs: http://localhost:8001/docs")
        sys.exit(0)
    else:
        print(f"❌ {passed}/{total} tests passed")
        print("=" * 50)
        sys.exit(1)
