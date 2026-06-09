import pytest
import httpx
import asyncio
from unittest.mock import patch, AsyncMock
from typing import Dict, Any, List

# --- Configuration and Mock Data ---

BASE_URL = "https://api.remittance.cdp/v1/wallet"
AUTH_TOKEN = "Bearer mock_valid_token"
INVALID_TOKEN = "Bearer invalid_token"
MOCK_USER_ID = "user_12345"
MOCK_BALANCE_DATA = {
    "user_id": MOCK_USER_ID,
    "currency": "NGN",
    "balance": 150000.75,
    "last_updated": "2025-11-05T10:00:00Z"
}
MOCK_TRANSACTIONS_DATA = {
    "user_id": MOCK_USER_ID,
    "total_count": 2,
    "transactions": [
        {
            "id": "txn_001",
            "type": "CREDIT",
            "amount": 100000.00,
            "currency": "NGN",
            "status": "COMPLETED",
            "timestamp": "2025-11-04T10:00:00Z",
            "description": "Initial deposit"
        },
        {
            "id": "txn_002",
            "type": "DEBIT",
            "amount": 50000.00,
            "currency": "NGN",
            "status": "COMPLETED",
            "timestamp": "2025-11-05T09:00:00Z",
            "description": "Remittance to beneficiary"
        }
    ]
}
MOCK_GAS_ESTIMATE_DATA = {
    "gas_fee": 5.50,
    "currency": "NGN",
    "estimated_time_ms": 500
}

# --- Fixtures ---

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="module")
async def client():
    """
    Fixture to provide an httpx.AsyncClient instance.
    This client will be used for all API calls in the tests.
    """
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=5.0) as client:
        yield client

@pytest.fixture
def mock_response_factory():
    """
    A factory fixture to create a mock httpx.Response object.
    This simplifies mocking the API responses.
    """
    def _factory(status_code: int, json_data: Dict[str, Any] = None, content: bytes = b""):
        mock_response = AsyncMock(spec=httpx.Response)
        mock_response.status_code = status_code
        mock_response.json.return_value = json_data if json_data is not None else {}
        mock_response.content = content
        mock_response.raise_for_status.side_effect = (
            httpx.HTTPStatusError(
                f"Mock HTTP Error: {status_code}", request=httpx.Request("GET", BASE_URL), response=mock_response
            )
            if status_code >= 400
            else None
        )
        return mock_response
    return _factory

@pytest.fixture(autouse=True)
def setup_teardown_mock_transport(mock_response_factory):
    """
    Setup: Patch the httpx.AsyncClient's transport layer to intercept all requests.
    Teardown: The patch is automatically removed after the test.
    """
    with patch("httpx.AsyncClient.request", new_callable=AsyncMock) as mock_request:
        # Default mock behavior for unhandled requests
        mock_request.return_value = mock_response_factory(500, {"code": "MOCK_ERROR", "message": "Unhandled mock request"})
        yield mock_request

# --- Test Class for Wallet Endpoints ---

@pytest.mark.asyncio
class TestWalletEndpoints:
    """
    Integration tests for the Nigerian Remittance Platform CDP Wallet endpoints.

    These tests use a mocked HTTP transport layer to simulate API responses,
    ensuring that the client-side logic (request construction, response parsing,
    error handling, and authentication) is correct and production-ready.
    """

    # --- Helper Methods for Mocking ---

    def _mock_auth_check(self, mock_request: AsyncMock, expected_token: str, status_code: int, json_data: Dict[str, Any]):
        """Helper to set up mock response based on Authorization header."""
        def side_effect(method, url, headers=None, **kwargs):
            if headers and headers.get("Authorization") == expected_token:
                return mock_request.return_value
            else:
                # Unauthorized response for any other token or missing token
                unauth_data = {"code": "UNAUTHORIZED", "message": "Missing or invalid token"}
                return self.mock_response_factory(401, unauth_data)

        mock_request.side_effect = side_effect
        mock_request.return_value = self.mock_response_factory(status_code, json_data)

    # --- Fixture Injection for Test Methods ---

    @pytest.fixture(autouse=True)
    def inject_fixtures(self, client, setup_teardown_mock_transport, mock_response_factory):
        """Inject necessary fixtures into the test class instance."""
        self.client = client
        self.mock_request = setup_teardown_mock_transport
        self.mock_response_factory = mock_response_factory

    # =========================================================================
    # Test Cases for GET /v1/wallet/balance/{user_id}
    # =========================================================================

    async def test_get_balance_success(self):
        """
        Test case for successful retrieval of a user's wallet balance (200 OK).
        Verifies correct request URL, method, headers, status code, and response structure.
        """
        # Arrange
        self._mock_auth_check(self.mock_request, AUTH_TOKEN, 200, MOCK_BALANCE_DATA)
        expected_url = f"{BASE_URL}/balance/{MOCK_USER_ID}"

        # Act
        response = await self.client.get(f"/balance/{MOCK_USER_ID}", headers={"Authorization": AUTH_TOKEN})
        data = response.json()

        # Assert
        self.mock_request.assert_called_once_with(
            "GET", expected_url, headers={"Authorization": AUTH_TOKEN}, timeout=5.0
        )
        assert response.status_code == 200
        assert data == MOCK_BALANCE_DATA
        assert isinstance(data["balance"], (int, float))
        assert data["currency"] == "NGN"

    async def test_get_balance_unauthorized(self):
        """
        Test case for unauthorized access (401 Unauthorized).
        Verifies that an invalid or missing token results in a 401 error.
        """
        # Arrange
        # The default mock setup in setup_teardown_mock_transport handles unauthorized for invalid tokens
        self._mock_auth_check(self.mock_request, AUTH_TOKEN, 200, MOCK_BALANCE_DATA)

        # Act & Assert
        with pytest.raises(httpx.HTTPStatusError) as excinfo:
            await self.client.get(f"/balance/{MOCK_USER_ID}", headers={"Authorization": INVALID_TOKEN})

        assert excinfo.value.response.status_code == 401
        assert excinfo.value.response.json()["code"] == "UNAUTHORIZED"

    async def test_get_balance_not_found(self):
        """
        Test case for wallet not found (404 Not Found).
        Simulates the scenario where the user_id does not have an associated wallet.
        """
        # Arrange
        error_data = {"code": "WALLET_NOT_FOUND", "message": "Wallet for user_id not found"}
        self._mock_auth_check(self.mock_request, AUTH_TOKEN, 404, error_data)

        # Act & Assert
        with pytest.raises(httpx.HTTPStatusError) as excinfo:
            await self.client.get(f"/balance/non_existent_user", headers={"Authorization": AUTH_TOKEN})

        assert excinfo.value.response.status_code == 404
        assert excinfo.value.response.json()["code"] == "WALLET_NOT_FOUND"

    # =========================================================================
    # Test Cases for GET /v1/wallet/transactions/{user_id}
    # =========================================================================

    async def test_get_transactions_success_default_params(self):
        """
        Test case for successful retrieval of transactions with default query parameters (200 OK).
        """
        # Arrange
        self._mock_auth_check(self.mock_request, AUTH_TOKEN, 200, MOCK_TRANSACTIONS_DATA)
        expected_url = f"{BASE_URL}/transactions/{MOCK_USER_ID}"

        # Act
        response = await self.client.get(f"/transactions/{MOCK_USER_ID}", headers={"Authorization": AUTH_TOKEN})
        data = response.json()

        # Assert
        self.mock_request.assert_called_once_with(
            "GET", expected_url, headers={"Authorization": AUTH_TOKEN}, timeout=5.0
        )
        assert response.status_code == 200
        assert data["user_id"] == MOCK_USER_ID
        assert data["total_count"] == len(data["transactions"])
        assert isinstance(data["transactions"], list)
        assert all(t["type"] in ["CREDIT", "DEBIT"] for t in data["transactions"])

    async def test_get_transactions_success_with_query_params(self):
        """
        Test case for successful retrieval of transactions with specific query parameters (edge case).
        Verifies that query parameters are correctly passed in the request.
        """
        # Arrange
        self._mock_auth_check(self.mock_request, AUTH_TOKEN, 200, MOCK_TRANSACTIONS_DATA)
        params = {"limit": 10, "offset": 5, "start_date": "2025-01-01", "end_date": "2025-12-31"}
        expected_url = f"{BASE_URL}/transactions/{MOCK_USER_ID}?limit=10&offset=5&start_date=2025-01-01&end_date=2025-12-31"

        # Act
        response = await self.client.get(
            f"/transactions/{MOCK_USER_ID}",
            headers={"Authorization": AUTH_TOKEN},
            params=params
        )

        # Assert
        # httpx automatically handles query parameter encoding
        call_args, call_kwargs = self.mock_request.call_args
        assert call_kwargs["params"] == params
        assert response.status_code == 200

    async def test_get_transactions_empty_list(self):
        """
        Test case for a user with no transactions (edge case).
        The API should return 200 OK with an empty list.
        """
        # Arrange
        empty_data = {"user_id": MOCK_USER_ID, "total_count": 0, "transactions": []}
        self._mock_auth_check(self.mock_request, AUTH_TOKEN, 200, empty_data)

        # Act
        response = await self.client.get(f"/transactions/{MOCK_USER_ID}", headers={"Authorization": AUTH_TOKEN})
        data = response.json()

        # Assert
        assert response.status_code == 200
        assert data["total_count"] == 0
        assert data["transactions"] == []

    async def test_get_transactions_invalid_params(self):
        """
        Test case for invalid query parameters (400 Bad Request - validation).
        Simulates passing a non-integer limit parameter.
        """
        # Arrange
        error_data = {"code": "INVALID_PARAMS", "message": "Invalid query parameters: limit must be an integer"}
        # Set up a specific mock response for this bad request
        def side_effect(method, url, headers=None, params=None, **kwargs):
            if params and params.get("limit") == "abc":
                return self.mock_response_factory(400, error_data)
            # Fallback to unauthorized if token is bad, or default 500 if token is good but not the bad request
            if headers and headers.get("Authorization") == AUTH_TOKEN:
                return self.mock_response_factory(500, {"code": "MOCK_ERROR", "message": "Unhandled mock request"})
            else:
                return self.mock_response_factory(401, {"code": "UNAUTHORIZED", "message": "Missing or invalid token"})

        self.mock_request.side_effect = side_effect

        # Act & Assert
        with pytest.raises(httpx.HTTPStatusError) as excinfo:
            await self.client.get(
                f"/transactions/{MOCK_USER_ID}",
                headers={"Authorization": AUTH_TOKEN},
                params={"limit": "abc"}
            )

        assert excinfo.value.response.status_code == 400
        assert excinfo.value.response.json()["code"] == "INVALID_PARAMS"

    # =========================================================================
    # Test Cases for POST /v1/wallet/gas/estimate
    # =========================================================================

    async def test_estimate_gas_success(self):
        """
        Test case for successful gas estimation (200 OK).
        This endpoint does not require authentication (as per spec).
        """
        # Arrange
        request_body = {
            "from_address": "0x123...",
            "to_address": "0x456...",
            "amount": 1000.00,
            "currency": "NGN"
        }
        self.mock_request.return_value = self.mock_response_factory(200, MOCK_GAS_ESTIMATE_DATA)
        expected_url = f"{BASE_URL}/gas/estimate"

        # Act
        response = await self.client.post("/gas/estimate", json=request_body)
        data = response.json()

        # Assert
        self.mock_request.assert_called_once_with(
            "POST", expected_url, json=request_body, timeout=5.0
        )
        assert response.status_code == 200
        assert data == MOCK_GAS_ESTIMATE_DATA
        assert isinstance(data["gas_fee"], (int, float))

    async def test_estimate_gas_validation_error(self):
        """
        Test case for validation error on request body (422 Unprocessable Entity).
        Simulates missing a required field (amount).
        """
        # Arrange
        invalid_body = {
            "from_address": "0x123...",
            "to_address": "0x456...",
            "currency": "NGN" # 'amount' is missing
        }
        error_data = {"code": "VALIDATION_ERROR", "message": "Missing required field: amount"}
        self.mock_request.return_value = self.mock_response_factory(422, error_data)

        # Act & Assert
        with pytest.raises(httpx.HTTPStatusError) as excinfo:
            await self.client.post("/gas/estimate", json=invalid_body)

        assert excinfo.value.response.status_code == 422
        assert excinfo.value.response.json()["code"] == "VALIDATION_ERROR"

    async def test_estimate_gas_service_unavailable(self):
        """
        Test case for external service failure (503 Service Unavailable - error case).
        Simulates the underlying gas estimation service being down.
        """
        # Arrange
        request_body = {
            "from_address": "0x123...",
            "to_address": "0x456...",
            "amount": 1000.00,
            "currency": "NGN"
        }
        error_data = {"code": "SERVICE_UNAVAILABLE", "message": "Gas estimation service is down"}
        self.mock_request.return_value = self.mock_response_factory(503, error_data)

        # Act & Assert
        with pytest.raises(httpx.HTTPStatusError) as excinfo:
            await self.client.post("/gas/estimate", json=request_body)

        assert excinfo.value.response.status_code == 503
        assert excinfo.value.response.json()["code"] == "SERVICE_UNAVAILABLE"

    async def test_estimate_gas_edge_case_zero_amount(self):
        """
        Test case for an edge case: estimating gas for a zero amount transfer.
        Should still succeed if the API allows it.
        """
        # Arrange
        request_body = {
            "from_address": "0x123...",
            "to_address": "0x456...",
            "amount": 0.00,
            "currency": "NGN"
        }
        # Mock a successful response for zero amount
        zero_amount_gas_data = {"gas_fee": 0.00, "currency": "NGN", "estimated_time_ms": 100}
        self.mock_request.return_value = self.mock_response_factory(200, zero_amount_gas_data)

        # Act
        response = await self.client.post("/gas/estimate", json=request_body)
        data = response.json()

        # Assert
        assert response.status_code == 200
        assert data["gas_fee"] == 0.00
        assert data["currency"] == "NGN"