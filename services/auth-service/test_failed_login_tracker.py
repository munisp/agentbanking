"""
Failed Login Tracking - Test Examples
Demonstrates the failed login attempt tracking and account suspension functionality
"""

from utils.failed_login_tracker import FailedLoginTracker


def test_failed_login_tracking():
    """Test failed login attempt tracking"""
    
    print("=" * 70)
    print("FAILED LOGIN ATTEMPT TRACKING TEST")
    print("=" * 70)
    
    # Mock database session (for testing)
    class MockDB:
        pass
    
    tracker = FailedLoginTracker(MockDB())
    
    test_email = "test.user@example.com"
    test_tenant = "bpmgd"
    test_keycloak_id = "abc-123-def-456"
    
    print(f"\nTest User: {test_email}")
    print(f"Tenant: {test_tenant}")
    print(f"Max Attempts: {tracker.MAX_ATTEMPTS}")
    print(f"Lockout Duration: {tracker.LOCKOUT_DURATION_MINUTES} minutes")
    print("-" * 70)
    
    # Simulate failed login attempts
    for i in range(1, tracker.MAX_ATTEMPTS + 2):
        print(f"\n--- Attempt {i} (Failed) ---")
        
        result = tracker.record_failed_attempt(
            email=test_email,
            tenant_id=test_tenant,
            keycloak_id=test_keycloak_id
        )
        
        print(f"Failed Attempts: {result['attempts']}")
        print(f"Remaining: {result['remaining']}")
        print(f"Suspended: {result['suspended']}")
        
        if result['suspended']:
            print(f"⛔ ACCOUNT SUSPENDED!")
            print(f"Lockout Until: {result['lockout_until']}")
            break
        elif result['remaining'] > 0:
            print(f"⚠️  WARNING: {result['remaining']} attempt(s) remaining")
        else:
            print(f"🚨 CRITICAL: Next attempt will trigger suspension!")
    
    print("\n" + "=" * 70)


def test_reset_attempts():
    """Test resetting failed attempts after successful login"""
    
    print("\n" + "=" * 70)
    print("RESET FAILED ATTEMPTS TEST")
    print("=" * 70)
    
    class MockDB:
        pass
    
    tracker = FailedLoginTracker(MockDB())
    
    test_email = "another.user@example.com"
    test_tenant = "bpmgd"
    test_keycloak_id = "xyz-789-uvw-012"
    
    # Record 3 failed attempts
    print(f"\nRecording 3 failed attempts for: {test_email}")
    for i in range(1, 4):
        result = tracker.record_failed_attempt(
            email=test_email,
            tenant_id=test_tenant,
            keycloak_id=test_keycloak_id
        )
        print(f"  Attempt {i}: {result['attempts']} failed, {result['remaining']} remaining")
    
    # Check remaining attempts
    remaining = tracker.get_remaining_attempts(test_email, test_tenant)
    print(f"\n✓ Before Reset - Remaining: {remaining}")
    
    # Simulate successful login - reset attempts
    print(f"\n✅ Successful Login - Resetting attempts...")
    tracker.reset_attempts(test_email, test_tenant)
    
    # Check remaining attempts after reset
    remaining = tracker.get_remaining_attempts(test_email, test_tenant)
    print(f"✓ After Reset - Remaining: {remaining}")
    
    print("\n" + "=" * 70)


def test_api_responses():
    """Show example API responses for different scenarios"""
    
    print("\n" + "=" * 70)
    print("EXAMPLE API RESPONSES")
    print("=" * 70)
    
    print("\n--- Scenario 1: Failed Login (3 attempts remaining) ---")
    print("HTTP Status: 401 Unauthorized")
    print("Response:")
    print("""
{
  "detail": {
    "code": "AUTH-AUTH-INVALID-4002",
    "message": "Invalid credentials. 3 attempt(s) remaining before account suspension."
  }
}
    """)
    
    print("\n--- Scenario 2: Failed Login (1 attempt remaining) ---")
    print("HTTP Status: 401 Unauthorized")
    print("Response:")
    print("""
{
  "detail": {
    "code": "AUTH-AUTH-INVALID-4002",
    "message": "Invalid credentials. 1 attempt(s) remaining before account suspension."
  }
}
    """)
    
    print("\n--- Scenario 3: Account Suspended (6th failed attempt) ---")
    print("HTTP Status: 403 Forbidden")
    print("Response:")
    print("""
{
  "detail": {
    "code": "AUTH-AUTH-SUSPENDED-4033",
    "message": "Account suspended due to multiple failed login attempts (6). Please contact support."
  }
}
    """)
    
    print("\n--- Scenario 4: Successful Login ---")
    print("HTTP Status: 200 OK")
    print("Response:")
    print("""
{
  "message": "success",
  "access_token": "eyJhbGciOiJSUzI1NiIsInR5cC...",
  "refresh_token": "eyJhbGciOiJSUzI1NiIsInR5cC...",
  "auth_stepup": false
}
    """)
    
    print("\n" + "=" * 70)


def test_user_admin_suspension():
    """Show suspension flow for users and admins"""
    
    print("\n" + "=" * 70)
    print("USER/ADMIN SUSPENSION FLOW")
    print("=" * 70)
    
    print("\n--- User Suspension Flow ---")
    print("1. Failed login detected")
    print("2. GET /user/user?keycloak_id={keycloak_id}")
    print("   Response: { 'user': { 'id': 'user-uuid', ... } }")
    print("3. PUT /user/user/{user-uuid}/suspend")
    print("4. User account suspended ✓")
    
    print("\n--- Admin Suspension Flow ---")
    print("1. Failed login detected")
    print("2. GET /admin/admin/keycloak/{keycloak_id}")
    print("   Response: { 'admin': { 'id': 29, ... } }")
    print("3. PATCH /admin/admin/{admin-id}/suspend")
    print("4. Admin account suspended ✓")
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    print("\n🔒 FAILED LOGIN TRACKING & ACCOUNT SUSPENSION TEST SUITE\n")
    
    test_failed_login_tracking()
    test_reset_attempts()
    test_api_responses()
    test_user_admin_suspension()
    
    print("\n✅ All tests completed!\n")
    
    print("=" * 70)
    print("CONFIGURATION")
    print("=" * 70)
    print("\nFailed Login Settings:")
    print("  MAX_ATTEMPTS: 6")
    print("  LOCKOUT_DURATION: 30 minutes")
    print("\nBehavior:")
    print("  - After 6 failed login attempts, account is automatically suspended")
    print("  - Suspension is done via external API (user or admin service)")
    print("  - Failed attempts reset after successful login")
    print("  - Failed attempts expire after 30 minutes of inactivity")
    print("\nAPI Endpoints Used:")
    print("  - GET /user/user?keycloak_id={id} (get user details)")
    print("  - GET /admin/admin/keycloak/{id} (get admin details)")
    print("  - PUT /user/user/{id}/suspend (suspend user)")
    print("  - PATCH /admin/admin/{id}/suspend (suspend admin)")
    print("=" * 70)
