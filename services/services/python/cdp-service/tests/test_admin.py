import pytest
import httpx
import json
from typing import Dict, Any, List

# --- Configuration ---
# Assuming the base URL for the API is known, even if we are mocking it.
BASE_URL = "http://api.remittance.cdp"
ADMIN_ENDPOINT_USER = "/v1/admin/user/wallet"
ADMIN_ENDPOINT_STATS = "/v1/admin/stats"
ADMIN_AUTH_TOKEN = "valid_admin_token"
USER_AUTH_TOKEN = "valid_user_token"
INVALID_TOKEN = "invalid_token"

# --- Mock Data ---

# Mock response for successful 'get user by wallet'
MOCK_USER_DATA = {
    "id": "user-123",
    "wallet_address": "0x1234567890abcdef",
    "email": "test.user@example.com",
    "status": "active",
    "kyc_level": 2,
    "created_at": "2023-01-01T00:00:00Z"
}

# Mock response for successful 'get system stats'
MOCK_STATS_DATA = {
    "total_users": 15000,
    "active_users": 12500,
    "total_transactions": 50000,
    "total_volume_usd": 15000000.00,
    "last_24h_transactions": 500,
    "platform_health": "operational"
}

# --- Mock Transport Implementation ---

class AdminMockTransport(httpx.AsyncBaseTransport):
    """
    A custom mock transport for httpx to simulate Admin API responses.
    This allows testing the client logic without an actual running server.
    """
    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        """Handles the mocked request and returns a simulated response."""
        
        # 1. Authentication/Authorization Check (Admin Token Required)
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return httpx.Response(401, request=request, json={"detail": "Authentication required"})
        
        token = auth_header.split("Bearer ")[1]
        
        if token == INVALID_TOKEN:
            return httpx.Response(401, request=request, json={"detail": "Invalid authentication credentials"})
        
        # Only ADMIN_AUTH_TOKEN is authorized for these endpoints
        if token != ADMIN_AUTH_TOKEN:
            # Simulate Forbidden for non-admin but authenticated users
            if token == USER_AUTH_TOKEN:
                return httpx.Response(403, request=request, json={"detail": "Permission denied: Admin access required"})
            # Fallback for other invalid tokens
            return httpx.Response(401, request=request, json={"detail": "Invalid authentication credentials"})

        # 2. Endpoint and Method Routing
           # GET /admin/user/wallet?wallet_address={address}
        if request.method == "GET" and request.url.path == ADMIN_ENDPOINT_USER:
            wallet_address = request.url.params.get("wallet_address")
            
            # Validation/Edge Case: Missing wallet_address
            if not wallet_address:
                return httpx.Response(422, request=request, json={"detail": "Validation Error: wallet_address query parameter is required"})
            
            # Edge Case: Invalid format (simple check)
            if not wallet_address.startswith("0x") or len(wallet_address) < 10:
                return httpx.Response(422, request=request, json={"detail": "Validation Error: Invalid wallet address format"})

            # Success Case
            if wallet_address == MOCK_USER_DATA["wallet_address"]:
                return httpx.Response(200, request=request, json=MOCK_USER_DATA)
            
            # Error Case: User not found
            if wallet_address == "0xnotfound":
                return httpx.Response(404, request=request, json={"detail": "User not found"})
            
            # Edge Case: User is suspended/inactive
            if wallet_address == "0xsuspended":
                suspended_user = MOCK_USER_DATA.copy()
                suspended_user["status"] = "suspended"
                suspended_user["wallet_address"] = wallet_address # Correct the wallet address in the mock response
                return httpx.Response(200, request=request, json=suspended_user)

            # Default Not Found
            return httpx.Response(404, request=request, json={"detail": "User not found"})

        # GET /admin/stats
        # The path check is already done in the outer block, but we need to ensure it's not the user endpoint
        # The path check is done by the client's base_url + endpoint, so we only need to check the path
        if request.method == "GET" and request.url.path == ADMIN_ENDPOINT_STATS:
            # Success Case
            return httpx.Response(200, request=request, json=MOCK_STATS_DATA)
        
        # Error Case: General Not Found for unhandled paths
        return httpx.Response(404, request=request, json={"detail": "Not Found"})

# --- Fixtures ---

@pytest.fixture(scope="module")
def admin_client():
    """
    Provides an httpx.AsyncClient configured with the mock transport
    for testing admin endpoints.
    """
    transport = AdminMockTransport()
    # The base_url is important for relative path resolution in the client
    client = httpx.AsyncClient(base_url=BASE_URL, transport=transport)
    yield client
    # Teardown is implicitly handled by the fixture scope

@pytest.fixture
def admin_headers() -> Dict[str, str]:
    """Provides valid admin authorization headers."""
    return {"Authorization": f"Bearer {ADMIN_AUTH_TOKEN}"}

@pytest.fixture
def user_headers() -> Dict[str, str]:
    """Provides valid non-admin user authorization headers."""
    return {"Authorization": f"Bearer {USER_AUTH_TOKEN}"}

@pytest.fixture
def invalid_headers() -> Dict[str, str]:
    """Provides invalid authorization headers."""
    return {"Authorization": f"Bearer {INVALID_TOKEN}"}

@pytest.fixture
def missing_headers() -> Dict[str, str]:
    """Provides missing authorization headers."""
    return {}

# --- Test Functions ---

# ==============================================================================
# Test Suite: GET /admin/user/wallet
# ==============================================================================

@pytest.mark.asyncio
async def test_get_user_by_wallet_success(admin_client: httpx.AsyncClient, admin_headers: Dict[str, str]):
    """
    Test case for successful retrieval of a user by their wallet address.
    Verifies status code, response structure, and data integrity.
    """
    wallet_address = MOCK_USER_DATA["wallet_address"]
    response = await admin_client.get(
        ADMIN_ENDPOINT_USER, 
        params={"wallet_address": wallet_address}, 
        headers=admin_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Assert response structure
    assert isinstance(data, dict)
    assert "wallet_address" in data
    assert "email" in data
    assert "status" in data
    
    # Assert data integrity
    assert data["wallet_address"] == wallet_address
    assert data["status"] == "active"
    assert data == MOCK_USER_DATA

@pytest.mark.asyncio
async def test_get_user_by_wallet_not_found(admin_client: httpx.AsyncClient, admin_headers: Dict[str, str]):
    """
    Test case for the error scenario where the user is not found (404).
    """
    wallet_address = "0xnotfound"
    response = await admin_client.get(
        ADMIN_ENDPOINT_USER, 
        params={"wallet_address": wallet_address}, 
        headers=admin_headers
    )
    
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert data["detail"] == "User not found"

@pytest.mark.asyncio
async def test_get_user_by_wallet_edge_suspended_user(admin_client: httpx.AsyncClient, admin_headers: Dict[str, str]):
    """
    Test case for the edge scenario where the user is found but is suspended.
    The API should return 200 with the user's status as 'suspended'.
    """
    wallet_address = "0xsuspended"
    response = await admin_client.get(
        ADMIN_ENDPOINT_USER, 
        params={"wallet_address": wallet_address}, 
        headers=admin_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["wallet_address"] == wallet_address
    assert data["status"] == "suspended"

@pytest.mark.asyncio
async def test_get_user_by_wallet_validation_missing_param(admin_client: httpx.AsyncClient, admin_headers: Dict[str, str]):
    """
    Test case for validation error when the required 'wallet_address' query parameter is missing (422).
    """
    response = await admin_client.get(
        ADMIN_ENDPOINT_USER, 
        headers=admin_headers
    )
    
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data
    assert "wallet_address query parameter is required" in data["detail"]

@pytest.mark.asyncio
async def test_get_user_by_wallet_validation_invalid_format(admin_client: httpx.AsyncClient, admin_headers: Dict[str, str]):
    """
    Test case for validation error when the 'wallet_address' format is invalid (422).
    """
    wallet_address = "invalid_format"
    response = await admin_client.get(
        ADMIN_ENDPOINT_USER, 
        params={"wallet_address": wallet_address}, 
        headers=admin_headers
    )
    
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data
    assert "Invalid wallet address format" in data["detail"]

# ==============================================================================
# Test Suite: GET /admin/stats
# ==============================================================================

@pytest.mark.asyncio
async def test_get_system_stats_success(admin_client: httpx.AsyncClient, admin_headers: Dict[str, str]):
    """
    Test case for successful retrieval of system statistics.
    Verifies status code, response structure, and data types.
    """
    response = await admin_client.get(ADMIN_ENDPOINT_STATS, headers=admin_headers)
    
    assert response.status_code == 200
    data = response.json()
    
    # Assert response structure and data types
    assert isinstance(data, dict)
    assert "total_users" in data and isinstance(data["total_users"], int)
    assert "total_transactions" in data and isinstance(data["total_transactions"], int)
    assert "total_volume_usd" in data and isinstance(data["total_volume_usd"], float)
    assert "platform_health" in data and isinstance(data["platform_health"], str)
    
    # Assert data integrity
    assert data == MOCK_STATS_DATA

# ==============================================================================
# Test Suite: Authentication and Authorization (Applies to both endpoints)
# ==============================================================================

@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint, params", [
    (ADMIN_ENDPOINT_USER, {"wallet_address": MOCK_USER_DATA["wallet_address"]}),
    (ADMIN_ENDPOINT_STATS, {})
])
async def test_admin_auth_missing_token(admin_client: httpx.AsyncClient, missing_headers: Dict[str, str], endpoint: str, params: Dict[str, str]):
    """
    Test case for authentication failure when the Authorization header is missing (401).
    Applies to both admin endpoints.
    """
    response = await admin_client.get(endpoint, params=params, headers=missing_headers)
    
    assert response.status_code == 401
    data = response.json()
    assert "detail" in data
    assert data["detail"] == "Authentication required"

@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint, params", [
    (ADMIN_ENDPOINT_USER, {"wallet_address": MOCK_USER_DATA["wallet_address"]}),
    (ADMIN_ENDPOINT_STATS, {})
])
async def test_admin_auth_invalid_token(admin_client: httpx.AsyncClient, invalid_headers: Dict[str, str], endpoint: str, params: Dict[str, str]):
    """
    Test case for authentication failure when the token is invalid (401).
    Applies to both admin endpoints.
    """
    response = await admin_client.get(endpoint, params=params, headers=invalid_headers)
    
    assert response.status_code == 401
    data = response.json()
    assert "detail" in data
    assert "Invalid authentication credentials" in data["detail"]

@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint, params", [
    (ADMIN_ENDPOINT_USER, {"wallet_address": MOCK_USER_DATA["wallet_address"]}),
    (ADMIN_ENDPOINT_STATS, {})
])
async def test_admin_auth_forbidden_non_admin_user(admin_client: httpx.AsyncClient, user_headers: Dict[str, str], endpoint: str, params: Dict[str, str]):
    """
    Test case for authorization failure when a valid non-admin user attempts to access admin endpoints (403).
    Applies to both admin endpoints.
    """
    response = await admin_client.get(endpoint, params=params, headers=user_headers)
    
    assert response.status_code == 403
    data = response.json()
    assert "detail" in data
    assert "Permission denied: Admin access required" in data["detail"]