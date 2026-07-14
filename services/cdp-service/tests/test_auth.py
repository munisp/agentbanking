import pytest
import httpx
import os
from typing import AsyncGenerator, Dict, Any

# --- Configuration ---
# Assuming the API base URL is set via an environment variable for production readiness
BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000/api/v1")

# --- Fixtures ---

@pytest.fixture(scope="session")
def anyio_backend():
    """
    Required for httpx AsyncClient to work with pytest-asyncio.
    """
    return "asyncio"

@pytest.fixture(scope="session")
async def client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """
    Fixture for an asynchronous HTTP client (httpx.AsyncClient).
    Uses a session scope for efficiency across all tests.
    """
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        yield client

@pytest.fixture(scope="session")
def test_user_data() -> Dict[str, str]:
    """
    Fixture for standard test user data.
    In a real scenario, this would be a user guaranteed to exist in the test database.
    """
    return {
        "phone_number": "+2348012345678",
        "country_code": "NG",
        "password": "SecureTestPassword123"
    }

@pytest.fixture
async def auth_tokens(client: httpx.AsyncClient, test_user_data: Dict[str, str]) -> Dict[str, str]:
    """
    Fixture to perform the full authentication flow (send OTP, verify OTP)
    and return the access and refresh tokens. This is function-scoped to ensure
    a fresh set of tokens for each test that requires authentication.
    """
    # 1. Send OTP
    await client.post("/auth/send-otp", json={"phone_number": test_user_data["phone_number"], "country_code": test_user_data["country_code"]})

    # 2. Verify OTP
    verify_payload = {
        "phone_number": test_user_data["phone_number"],
        "country_code": test_user_data["country_code"],
        "otp": "000000" # Placeholder for a valid OTP
    }
    response = await client.post("/auth/verify-otp", json=verify_payload)
    response.raise_for_status() # Ensure verification was successful

    data = response.json()
    return {
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"]
    }

@pytest.fixture
async def authenticated_client(client: httpx.AsyncClient, auth_tokens: Dict[str, str]) -> httpx.AsyncClient:
    """
    Fixture to return an httpx.AsyncClient with the Authorization header set.
    """
    # Create a new client instance with default headers for the access token
    auth_client = httpx.AsyncClient(
        base_url=client.base_url,
        timeout=client.timeout,
        headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
    )
    # The client is not yielded with 'async with' because it's a function-scoped fixture
    # and we want to return the client itself. The cleanup is handled by the test runner
    # or can be explicitly handled with a finalizer if necessary, but for simple
    # header setting, this is often sufficient.
    return auth_client

# --- Helper Functions (if needed, but we'll stick to direct test calls for simplicity) ---

# --- Test Class Structure ---

class TestAuthenticationEndpoints:
    """
    Integration tests for the Authentication API endpoints.
    Covers: send_otp, verify_otp, refresh_token, logout.
    """

    async def test_send_otp_success(self, client: httpx.AsyncClient, test_user_data: Dict[str, str]):
        """
        Test successful OTP sending for a valid phone number.
        """
        url = "/auth/send-otp"
        payload = {"phone_number": test_user_data["phone_number"], "country_code": test_user_data["country_code"]}
        response = await client.post(url, json=payload)

        assert response.status_code == 200
        assert response.json()["detail"] == "OTP sent successfully"

    async def test_send_otp_validation_error(self, client: httpx.AsyncClient):
        """
        Test validation error for an invalid phone number format.
        """
        url = "/auth/send-otp"
        payload = {"phone_number": "invalid_phone", "country_code": "NG"}
        response = await client.post(url, json=payload)

        assert response.status_code == 422  # Unprocessable Entity for validation errors
        assert "detail" in response.json()
        assert any("phone_number" in error["loc"] for error in response.json()["detail"])

    async def test_verify_otp_success(self, client: httpx.AsyncClient, test_user_data: Dict[str, str], auth_tokens: Dict[str, str]):
        """
        Test successful OTP verification and token generation.
        NOTE: This test assumes a successful OTP has been sent and a valid OTP is used.
        In a real scenario, the OTP generation logic would need to be mocked or known.
        For integration test purposes, we assume a known/mocked OTP (e.g., "000000").
        """
        # 1. Ensure OTP is sent first
        await client.post("/auth/send-otp", json={"phone_number": test_user_data["phone_number"], "country_code": test_user_data["country_code"]})

        # 2. Verify OTP
        url = "/auth/verify-otp"
        # Assuming a known/mocked OTP for integration testing
        payload = {
            "phone_number": test_user_data["phone_number"],
            "country_code": test_user_data["country_code"],
            "otp": "000000" # Placeholder for a valid OTP
        }
        response = await client.post(url, json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

        # The tokens are now managed by the 'auth_tokens' fixture for other tests.
        # This test only verifies the token generation process.
        pass

    async def test_refresh_token_success(self, client: httpx.AsyncClient, auth_tokens: Dict[str, str]):
        """
        Test successful token refresh using a valid refresh token.
        """
        url = "/auth/refresh-token"
        headers = {"Authorization": f"Bearer {auth_tokens['refresh_token']}"}
        response = await client.post(url, headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["access_token"] != auth_tokens["access_token"] # New access token should be different

    async def test_refresh_token_invalid_token_error(self, client: httpx.AsyncClient):
        """
        Test error case for token refresh with an invalid or expired refresh token.
        """
        url = "/auth/refresh-token"
        headers = {"Authorization": "Bearer invalid.refresh.token"}
        response = await client.post(url, headers=headers)

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid or expired refresh token"

    async def test_logout_success(self, client: httpx.AsyncClient, auth_tokens: Dict[str, str]):
        """
        Test successful user logout (token invalidation).
        """
        url = "/auth/logout"
        headers = {"Authorization": f"Bearer {auth_tokens['access_token']}"}
        response = await client.post(url, headers=headers)

        assert response.status_code == 200
        assert response.json()["detail"] == "Successfully logged out"

        # Edge case: Verify the token is now invalid by trying to use it
        # We'll assume a simple protected endpoint exists for this check.
        protected_url = "/users/me" # A common protected endpoint
        protected_response = await client.get(protected_url, headers=headers)
        assert protected_response.status_code == 401

    async def test_logout_unauthorized(self, client: httpx.AsyncClient):
        """
        Test error case for logout without an access token.
        """
        url = "/auth/logout"
        response = await client.post(url) # No Authorization header

        assert response.status_code == 401
        assert response.json()["detail"] == "Not authenticated"

    async def test_logout_invalid_token(self, client: httpx.AsyncClient):
        """
        Test error case for logout with an invalid access token.
        """
        url = "/auth/logout"
        headers = {"Authorization": "Bearer invalid.access.token"}
        response = await client.post(url, headers=headers)

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid token"

    async def test_verify_otp_invalid_otp_error(self, client: httpx.AsyncClient, test_user_data: Dict[str, str]):
        """
        Test error case for an invalid or expired OTP.
        """
        # 1. Ensure OTP is sent first
        await client.post("/auth/send-otp", json={"phone_number": test_user_data["phone_number"], "country_code": test_user_data["country_code"]})

        # 2. Verify OTP with an invalid code
        url = "/auth/verify-otp"
        payload = {
            "phone_number": test_user_data["phone_number"],
            "country_code": test_user_data["country_code"],
            "otp": "999999" # Placeholder for an invalid OTP
        }
        response = await client.post(url, json=payload)

        assert response.status_code == 401 # Unauthorized/Invalid Credentials
        assert response.json()["detail"] == "Invalid or expired OTP"

    async def test_verify_otp_validation_error(self, client: httpx.AsyncClient, test_user_data: Dict[str, str]):
        """
        Test validation error for missing fields in verify OTP request.
        """
        url = "/auth/verify-otp"
        payload = {
            "phone_number": test_user_data["phone_number"],
            "country_code": test_user_data["country_code"],
            # "otp" is missing
        }
        response = await client.post(url, json=payload)

        assert response.status_code == 422
        assert "detail" in response.json()
        assert any("otp" in error["loc"] for error in response.json()["detail"])