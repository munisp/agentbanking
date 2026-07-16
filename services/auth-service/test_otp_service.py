"""
OTP Service - Test Examples
Demonstrates OTP generation and verification functionality
"""

from utils.otp_service import OTPService


def test_otp_generation():
    """Test OTP generation"""
    
    print("=" * 70)
    print("OTP GENERATION TEST")
    print("=" * 70)
    
    otp_service = OTPService()
    
    test_keycloak_id = "9052cbd0-25e3-4712-9fba-d8b792efe428"
    test_tenant = "bpmgd"
    test_email = "user@example.com"
    
    print(f"\nGenerating OTP for:")
    print(f"  Email: {test_email}")
    print(f"  Keycloak ID: {test_keycloak_id}")
    print(f"  Tenant: {test_tenant}")
    print(f"  OTP Length: {otp_service.OTP_LENGTH} digits")
    print(f"  Expiry: {otp_service.OTP_EXPIRY_MINUTES} minutes")
    print("-" * 70)
    
    otp_data = otp_service.generate_otp(
        keycloak_id=test_keycloak_id,
        tenant_id=test_tenant,
        email=test_email
    )
    
    print(f"\n✅ OTP Generated!")
    print(f"   Code: {otp_data['code']}")
    print(f"   Expires At: {otp_data['expires_at']}")
    
    print("\n" + "=" * 70)
    
    return otp_data['code'], test_keycloak_id, test_tenant


def test_otp_verification():
    """Test OTP verification"""
    
    print("\n" + "=" * 70)
    print("OTP VERIFICATION TEST")
    print("=" * 70)
    
    otp_service = OTPService()
    
    # Generate OTP first
    test_keycloak_id = "abc-123-def-456"
    test_tenant = "bpmgd"
    test_email = "test@example.com"
    
    otp_data = otp_service.generate_otp(
        keycloak_id=test_keycloak_id,
        tenant_id=test_tenant,
        email=test_email
    )
    
    correct_otp = otp_data['code']
    print(f"\n✅ OTP Generated: {correct_otp}")
    
    # Test 1: Valid OTP
    print("\n--- Test 1: Valid OTP ---")
    result = otp_service.verify_otp(
        keycloak_id=test_keycloak_id,
        tenant_id=test_tenant,
        otp_code=correct_otp
    )
    print(f"Valid: {result['valid']}")
    print(f"Message: {result['message']}")
    
    # Test 2: Invalid OTP (after valid verification)
    print("\n--- Test 2: OTP Already Used ---")
    result = otp_service.verify_otp(
        keycloak_id=test_keycloak_id,
        tenant_id=test_tenant,
        otp_code=correct_otp
    )
    print(f"Valid: {result['valid']}")
    print(f"Message: {result['message']}")
    
    # Test 3: Wrong OTP code
    print("\n--- Test 3: Wrong OTP Code ---")
    otp_data2 = otp_service.generate_otp(
        keycloak_id="xyz-789-uvw-012",
        tenant_id=test_tenant,
        email="another@example.com"
    )
    
    for i in range(1, 4):
        print(f"\nAttempt {i}:")
        result = otp_service.verify_otp(
            keycloak_id="xyz-789-uvw-012",
            tenant_id=test_tenant,
            otp_code="999999"  # Wrong code
        )
        print(f"  Valid: {result['valid']}")
        print(f"  Message: {result['message']}")
        if 'attempts_remaining' in result:
            print(f"  Attempts Remaining: {result['attempts_remaining']}")
    
    # Test 4: Max attempts exceeded
    print("\n--- Test 4: Max Attempts Should Be Exceeded ---")
    result = otp_service.verify_otp(
        keycloak_id="xyz-789-uvw-012",
        tenant_id=test_tenant,
        otp_code="999999"
    )
    print(f"Valid: {result['valid']}")
    print(f"Message: {result['message']}")
    
    print("\n" + "=" * 70)


def test_login_flow_with_otp():
    """Simulate login flow with OTP"""
    
    print("\n" + "=" * 70)
    print("LOGIN FLOW WITH OTP STEP-UP")
    print("=" * 70)
    
    print("\n📱 SCENARIO: User logging in from new device")
    print("-" * 70)
    
    print("\n1️⃣ POST /auth/login")
    print("   Request:")
    print("   {")
    print('     "email": "user@example.com",')
    print('     "password": "correct_password"')
    print("   }")
    
    print("\n   Response (200 OK):")
    print("   {")
    print('     "message": "OTP required for verification",')
    print('     "auth_stepup": true,')
    print('     "otp_required": true,')
    print('     "keycloak_id": "9052cbd0-25e3-4712-9fba-d8b792efe428",')
    print('     "otp_expires_at": "2026-02-07T15:30:00.000000"')
    print("   }")
    
    print("\n   🔐 OTP Generated and Logged:")
    print("   ==========================================")
    print("   🔐 OTP GENERATED for user@example.com")
    print("      Tenant: bpmgd")
    print("      Keycloak ID: 9052cbd0-25e3-4712-9fba-d8b792efe428")
    print("      OTP Code: 123456")
    print("      Expires At: 2026-02-07T15:30:00.000000")
    print("   ==========================================")
    
    print("\n2️⃣ POST /auth/verify-otp")
    print("   Request:")
    print("   {")
    print('     "keycloak_id": "9052cbd0-25e3-4712-9fba-d8b792efe428",')
    print('     "otp_code": "123456"')
    print("   }")
    
    print("\n   Response (200 OK):")
    print("   {")
    print('     "message": "OTP verified successfully. Authentication complete.",')
    print('     "verified": true,')
    print('     "keycloak_id": "9052cbd0-25e3-4712-9fba-d8b792efe428",')
    print('     "email": "user@example.com"')
    print("   }")
    
    print("\n✅ User authenticated successfully!")
    print("\n" + "=" * 70)


def test_trusted_device_flow():
    """Simulate login from trusted device"""
    
    print("\n" + "=" * 70)
    print("LOGIN FLOW - TRUSTED DEVICE (No OTP)")
    print("=" * 70)
    
    print("\n📱 SCENARIO: User logging in from trusted device")
    print("-" * 70)
    
    print("\n1️⃣ POST /auth/login")
    print("   Request:")
    print("   {")
    print('     "email": "user@example.com",')
    print('     "password": "correct_password"')
    print("   }")
    
    print("\n   Response (200 OK):")
    print("   {")
    print('     "message": "success",')
    print('     "access_token": "eyJhbGciOiJSUzI1NiIsInR5cC...",')
    print('     "refresh_token": "eyJhbGciOiJSUzI1NiIsInR5cC...",')
    print('     "expires_in": 300,')
    print('     "refresh_expires_in": 1800,')
    print('     "token_type": "Bearer",')
    print('     "keycloak_id": "9052cbd0-25e3-4712-9fba-d8b792efe428",')
    print('     "auth_stepup": false,')
    print('     "otp_required": false')
    print("   }")
    
    print("\n✅ User authenticated immediately (no OTP required)")
    print("\n" + "=" * 70)


def test_otp_error_scenarios():
    """Test various OTP error scenarios"""
    
    print("\n" + "=" * 70)
    print("OTP ERROR SCENARIOS")
    print("=" * 70)
    
    print("\n--- Scenario 1: OTP Not Found ---")
    print("POST /auth/verify-otp")
    print("Response (401):")
    print('{')
    print('  "detail": {')
    print('    "code": "AUTH-OTP-INVALID-4010",')
    print('    "message": "No OTP found. Please request a new one."')
    print('  }')
    print('}')
    
    print("\n--- Scenario 2: OTP Expired ---")
    print("POST /auth/verify-otp")
    print("Response (401):")
    print('{')
    print('  "detail": {')
    print('    "code": "AUTH-OTP-INVALID-4010",')
    print('    "message": "OTP has expired. Please request a new one."')
    print('  }')
    print('}')
    
    print("\n--- Scenario 3: Invalid OTP Code ---")
    print("POST /auth/verify-otp")
    print("Response (401):")
    print('{')
    print('  "detail": {')
    print('    "code": "AUTH-OTP-INVALID-4010",')
    print('    "message": "Invalid OTP code. 2 attempt(s) remaining."')
    print('  }')
    print('}')
    
    print("\n--- Scenario 4: Max Attempts Exceeded ---")
    print("POST /auth/verify-otp")
    print("Response (401):")
    print('{')
    print('  "detail": {')
    print('    "code": "AUTH-OTP-INVALID-4010",')
    print('    "message": "Maximum verification attempts exceeded. Please request a new OTP."')
    print('  }')
    print('}')
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    print("\n🔐 OTP SERVICE TEST SUITE\n")
    
    test_otp_generation()
    test_otp_verification()
    test_login_flow_with_otp()
    test_trusted_device_flow()
    test_otp_error_scenarios()
    
    print("\n✅ All tests completed!\n")
    
    print("=" * 70)
    print("CONFIGURATION")
    print("=" * 70)
    print("\nOTP Settings:")
    print("  OTP_LENGTH: 6 digits")
    print("  OTP_EXPIRY: 10 minutes")
    print("  MAX_VERIFICATION_ATTEMPTS: 3")
    print("\nAPI Endpoints:")
    print("  POST /auth/login - Returns OTP requirement if auth_stepup=true")
    print("  POST /auth/verify-otp - Verifies OTP code")
    print("\nOTP Delivery:")
    print("  - Currently: Logged to console (for development)")
    print("  - Production: Send via SMS/Email service")
    print("=" * 70)
