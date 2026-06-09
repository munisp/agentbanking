import pytest
import httpx
from typing import AsyncGenerator, Dict, Any, List

# --- Configuration and Mock Data ---

# Base URL for the API. In a real scenario, this would be an environment variable.
BASE_URL = "http://api.remittance-cdp.ng/v1"

# Mock data for a successful user
MOCK_USER_DATA = {
    "id": "user-12345",
    "email": "test.user@example.com",
    "first_name": "Aisha",
    "last_name": "Bello",
    "phone_number": "+2348012345678",
    "is_active": True,
    "profile_status": "VERIFIED",
    "devices": [
        {"id": "dev-001", "type": "mobile", "last_login": "2025-11-05T10:00:00Z"},
        {"id": "dev-002", "type": "web", "last_login": "2025-11-04T15:30:00Z"},
    ]
}

# Mock data for a successful profile update
MOCK_UPDATE_DATA = {
    "first_name": "Aisha Updated",
    "last_name": "Bello Updated",
    "address": "123 Lagos Street, Lagos"
}

# Mock data for a successful device revocation
MOCK_REVOKE_RESPONSE = {
    "message": "Device revoked successfully",
    "device_id": "dev-002"
}

# Mock token for authentication
MOCK_AUTH_TOKEN = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoidXNlci0xMjM0NSIsImV4cCI6MTc2MjU3OTIwMH0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"

# --- Pytest Fixtures ---

@pytest.fixture(scope="session")
def auth_token() -> str:
    """
    Fixture to provide a mock authentication token for tests.
    In a real application, this would be obtained via a login endpoint.
    """
    return MOCK_AUTH_TOKEN

@pytest.fixture(scope="session")
def headers(auth_token: str) -> Dict[str, str]:
    """
    Fixture to provide standard request headers with authentication.
    """
    return {
        "Authorization": auth_token,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

@pytest.fixture(scope="session")
def base_url() -> str:
    """
    Fixture to provide the base URL for the API.
    """
    return BASE_URL

@pytest.fixture(scope="session")
async def client(base_url: str) -> AsyncGenerator[httpx.AsyncClient, None]:
    """
    Asynchronous fixture to create and yield an httpx.AsyncClient.
    This client is configured to use a transport that mocks the API responses.
    """
    
    # Define a custom transport for mocking API responses
    class MockTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            url_path = request.url.path
            method = request.method
            
            # Simulate network delay for realism
            await pytest.mark.asyncio.sleep(0.01)

            # --- /users/me (GET) ---
            if url_path == f"{base_url}/users/me" and method == "GET":
                if request.headers.get("Authorization") == MOCK_AUTH_TOKEN:
                    return httpx.Response(200, json=MOCK_USER_DATA)
                else:
                    return httpx.Response(401, json={"detail": "Authentication credentials were not provided"})

            # --- /users/me (PUT) ---
            elif url_path == f"{base_url}/users/me" and method == "PUT":
                if request.headers.get("Authorization") != MOCK_AUTH_TOKEN:
                    return httpx.Response(401, json={"detail": "Authentication credentials were not provided"})
                
                try:
                    request_data = request.json()
                except:
                    return httpx.Response(400, json={"detail": "Invalid JSON format"})

                # Validation checks
                if "first_name" in request_data and not isinstance(request_data["first_name"], str):
                    return httpx.Response(422, json={"detail": "First name must be a string"})
                if "first_name" in request_data and len(request_data["first_name"]) < 2:
                    return httpx.Response(422, json={"detail": "First name too short"})
                
                # Simulate successful update
                updated_user = MOCK_USER_DATA.copy()
                updated_user.update(request_data)
                return httpx.Response(200, json=updated_user)

            # --- /users/devices (GET) ---
            elif url_path == f"{base_url}/users/devices" and method == "GET":
                if request.headers.get("Authorization") == MOCK_AUTH_TOKEN:
                    return httpx.Response(200, json={"devices": MOCK_USER_DATA["devices"]})
                else:
                    return httpx.Response(401, json={"detail": "Authentication credentials were not provided"})

            # --- /users/devices/{device_id} (DELETE) ---
            elif url_path.startswith(f"{base_url}/users/devices/") and method == "DELETE":
                device_id = url_path.split("/")[-1]
                if request.headers.get("Authorization") != MOCK_AUTH_TOKEN:
                    return httpx.Response(401, json={"detail": "Authentication credentials were not provided"})
                
                if device_id == "dev-002":
                    # Successful revocation
                    return httpx.Response(200, json=MOCK_REVOKE_RESPONSE)
                elif device_id == "non-existent-dev":
                    # Edge case: Device not found
                    return httpx.Response(404, json={"detail": "Device not found"})
                else:
                    # Default for other IDs
                    return httpx.Response(403, json={"detail": "Forbidden: Cannot revoke primary device"})

            # --- Default 404 for unhandled paths ---
            return httpx.Response(404, json={"detail": "Not Found"})

    # Setup: Create the client with the mock transport
    async with httpx.AsyncClient(base_url=base_url, transport=MockTransport()) as client:
        yield client
    
    # Teardown: (Implicitly handled by 'async with' block)

# --- Test Class for User Management Endpoints ---

@pytest.mark.asyncio
class TestUserManagement:
    """
    Comprehensive integration tests for the User Management API endpoints.
    These tests cover success, error, validation, and authentication cases.
    """

    # --- /users/me (GET) ---

    async def test_get_current_user_success(self, client: httpx.AsyncClient, headers: Dict[str, str]):
        """
        Test case for successfully retrieving the current user's profile.
        Verifies status code, response structure, and key data fields.
        """
        response = await client.get("/users/me", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # Assert response structure
        assert isinstance(data, dict)
        assert "id" in data
        assert "email" in data
        assert "first_name" in data
        assert "profile_status" in data
        
        # Assert data integrity
        assert data["id"] == MOCK_USER_DATA["id"]
        assert data["email"] == MOCK_USER_DATA["email"]
        assert data["profile_status"] == "VERIFIED"

    async def test_get_current_user_unauthorized(self, client: httpx.AsyncClient, headers: Dict[str, str]):
        """
        Test case for unauthorized access to the current user endpoint (missing token).
        """
        unauth_headers = headers.copy()
        unauth_headers["Authorization"] = "" # Simulate missing or empty token
        
        response = await client.get("/users/me", headers=unauth_headers)
        
        assert response.status_code == 401
        assert "Authentication credentials were not provided" in response.json().get("detail", "")

    # --- /users/me (PUT) - Update Profile ---

    async def test_update_profile_success(self, client: httpx.AsyncClient, headers: Dict[str, str]):
        """
        Test case for successfully updating the user's profile with valid data.
        Verifies status code and that the response reflects the updated data.
        """
        update_payload = MOCK_UPDATE_DATA
        response = await client.put("/users/me", headers=headers, json=update_payload)
        
        assert response.status_code == 200
        data = response.json()
        
        # Assert updated fields
        assert data["first_name"] == update_payload["first_name"]
        assert data["last_name"] == update_payload["last_name"]
        # Assert that other fields remain
        assert data["email"] == MOCK_USER_DATA["email"]

    async def test_update_profile_validation_error(self, client: httpx.AsyncClient, headers: Dict[str, str]):
        """
        Test case for validation failure (e.g., first name too short).
        """
        invalid_payload = {"first_name": "A"} # Too short
        response = await client.put("/users/me", headers=headers, json=invalid_payload)
        
        assert response.status_code == 422
        assert "First name too short" in response.json().get("detail", "")

    async def test_update_profile_unauthorized(self, client: httpx.AsyncClient, headers: Dict[str, str]):
        """
        Test case for unauthorized profile update attempt.
        """
        unauth_headers = headers.copy()
        unauth_headers["Authorization"] = "Bearer invalid_token"
        
        response = await client.put("/users/me", headers=unauth_headers, json=MOCK_UPDATE_DATA)
        
        assert response.status_code == 401
        assert "Authentication credentials were not provided" in response.json().get("detail", "")

    async def test_update_profile_edge_case_partial_update(self, client: httpx.AsyncClient, headers: Dict[str, str]):
        """
        Edge case: Test updating only a single field (e.g., only last_name).
        """
        partial_payload = {"last_name": "New Surname"}
        response = await client.put("/users/me", headers=headers, json=partial_payload)
        
        assert response.status_code == 200
        data = response.json()
        
        # Assert the updated field
        assert data["last_name"] == partial_payload["last_name"]
        # Assert the first name remains the original mock value (since we didn't update it)
        assert data["first_name"] == MOCK_USER_DATA["first_name"]

    # --- /users/devices (GET) ---

    async def test_list_devices_success(self, client: httpx.AsyncClient, headers: Dict[str, str]):
        """
        Test case for successfully listing the user's registered devices.
        Verifies status code, response structure, and the number of devices.
        """
        response = await client.get("/users/devices", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # Assert response structure
        assert isinstance(data, dict)
        assert "devices" in data
        assert isinstance(data["devices"], list)
        
        # Assert data integrity (number of devices)
        assert len(data["devices"]) == len(MOCK_USER_DATA["devices"])
        assert data["devices"][0]["id"] == MOCK_USER_DATA["devices"][0]["id"]

    async def test_list_devices_unauthorized(self, client: httpx.AsyncClient, headers: Dict[str, str]):
        """
        Test case for unauthorized access to the list devices endpoint.
        """
        unauth_headers = headers.copy()
        unauth_headers["Authorization"] = "Bearer expired_token"
        
        response = await client.get("/users/devices", headers=unauth_headers)
        
        assert response.status_code == 401
        assert "Authentication credentials were not provided" in response.json().get("detail", "")

    # --- /users/devices/{device_id} (DELETE) ---

    async def test_revoke_device_success(self, client: httpx.AsyncClient, headers: Dict[str, str]):
        """
        Test case for successfully revoking a non-primary device.
        Verifies status code and the success message.
        """
        device_to_revoke = "dev-002"
        response = await client.delete(f"/users/devices/{device_to_revoke}", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["message"] == MOCK_REVOKE_RESPONSE["message"]
        assert data["device_id"] == device_to_revoke

    async def test_revoke_device_edge_case_not_found(self, client: httpx.AsyncClient, headers: Dict[str, str]):
        """
        Edge case: Test revoking a device that does not exist.
        Should result in a 404 Not Found error.
        """
        device_to_revoke = "non-existent-dev"
        response = await client.delete(f"/users/devices/{device_to_revoke}", headers=headers)
        
        assert response.status_code == 404
        assert "Device not found" in response.json().get("detail", "")

    async def test_revoke_device_error_case_forbidden(self, client: httpx.AsyncClient, headers: Dict[str, str]):
        """
        Error case: Test revoking a device that is forbidden (e.g., the current primary device).
        Should result in a 403 Forbidden error.
        """
        device_to_revoke = "dev-001" # Mocked as primary/forbidden
        response = await client.delete(f"/users/devices/{device_to_revoke}", headers=headers)
        
        assert response.status_code == 403
        assert "Cannot revoke primary device" in response.json().get("detail", "")

    async def test_revoke_device_unauthorized(self, client: httpx.AsyncClient, headers: Dict[str, str]):
        """
        Test case for unauthorized attempt to revoke a device.
        """
        unauth_headers = headers.copy()
        unauth_headers["Authorization"] = "Bearer wrong_user_token"
        device_to_revoke = "dev-002"
        
        response = await client.delete(f"/users/devices/{device_to_revoke}", headers=unauth_headers)
        
        assert response.status_code == 401
        assert "Authentication credentials were not provided" in response.json().get("detail", "")
