import pytest
import httpx
import asyncio
from typing import AsyncGenerator, Dict, Any

# Base URL for the mock API server
# Base URL is not strictly needed with ASGITransport, but kept for clarity
BASE_URL = "http://test"

# Mock data for testing
MOCK_USER_ID = "user_123"
MOCK_AUTH_TOKEN = "Bearer valid_token"
MOCK_INVALID_TOKEN = "Bearer invalid_token"
MOCK_ESCROW_ID = "escrow_456"
MOCK_TRANSACTION_ID = "txn_789"

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


from mock_server import app as fastapi_app
from httpx import ASGITransport

@pytest.fixture(scope="session")
async def client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """
    Asynchronous HTTP client fixture for making requests to the API.
    Uses a session scope for efficiency and ASGITransport to bypass network.
    """
    async with httpx.AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test", timeout=10) as client:
        # Setup: Pre-create a mock user or necessary state if required
        # For this mock, we assume the server is ready.
        print("\n--- Setup: Initializing AsyncClient ---")
        yield client
        # Teardown: Clean up resources if necessary
        print("\n--- Teardown: Closing AsyncClient ---")

@pytest.fixture
def auth_headers() -> Dict[str, str]:
    """Fixture for valid authentication headers."""
    return {"Authorization": MOCK_AUTH_TOKEN, "X-User-ID": MOCK_USER_ID}

@pytest.fixture
def invalid_auth_headers() -> Dict[str, str]:
    """Fixture for invalid authentication headers."""
    return {"Authorization": MOCK_INVALID_TOKEN, "X-User-ID": MOCK_USER_ID}

@pytest.fixture
def missing_auth_headers() -> Dict[str, str]:
    """Fixture for missing authentication headers."""
    return {}

class TestTransactionEndpoints:
    """
    Comprehensive integration tests for the Nigerian Remittance Platform CDP Transaction endpoints.
    Covers create escrow, claim escrow, refund escrow, and get escrow details.
    """

    @pytest.mark.asyncio
    async def test_01_create_escrow_success(self, client: httpx.AsyncClient, auth_headers: Dict[str, str]):
        """
        Test case for successful creation of a new escrow transaction.
        Covers: Success case, status code 201, response structure, and data validation.
        """
        payload = {
            "amount": 50000.00,
            "currency": "NGN",
            "sender_account": "1234567890",
            "recipient_account": "0987654321",
            "description": "Payment for goods",
            "metadata": {"source": "web_app"}
        }
        response = await client.post("/transactions/escrow", json=payload, headers=auth_headers)

        assert response.status_code == 201, f"Expected 201, got {response.status_code}. Response: {response.text}"
        data = response.json()
        assert "escrow_id" in data
        assert data["status"] == "CREATED"
        assert data["amount"] == payload["amount"]
        assert data["currency"] == payload["currency"]
        assert data["owner_id"] == MOCK_USER_ID
        assert data["transaction_id"] == MOCK_TRANSACTION_ID # Mock server should return this

    @pytest.mark.asyncio
    async def test_02_create_escrow_validation_error(self, client: httpx.AsyncClient, auth_headers: Dict[str, str]):
        """
        Test case for validation errors during escrow creation (e.g., missing required fields).
        Covers: Validation error case, status code 400, and error message structure.
        """
        # Missing 'amount' and invalid 'currency'
        payload = {
            "currency": "USD",
            "sender_account": "1234567890",
            "recipient_account": "0987654321",
            "description": "Invalid test"
        }
        response = await client.post("/transactions/escrow", json=payload, headers=auth_headers)

        assert response.status_code == 400, f"Expected 400, got {response.status_code}. Response: {response.text}"
        data = response.json()
        assert "detail" in data
        assert "amount" in data["detail"]
        assert "currency" in data["detail"]

    @pytest.mark.asyncio
    async def test_03_create_escrow_unauthorized(self, client: httpx.AsyncClient, invalid_auth_headers: Dict[str, str]):
        """
        Test case for unauthorized access during escrow creation.
        Covers: Authentication error, status code 401.
        """
        payload = {
            "amount": 100.00,
            "currency": "NGN",
            "sender_account": "1234567890",
            "recipient_account": "0987654321",
            "description": "Unauthorized test"
        }
        response = await client.post("/transactions/escrow", json=payload, headers=invalid_auth_headers)
        assert response.status_code == 401, f"Expected 401, got {response.status_code}. Response: {response.text}"

    @pytest.mark.asyncio
    async def test_04_create_escrow_forbidden(self, client: httpx.AsyncClient, auth_headers: Dict[str, str]):
        """
        Test case for forbidden access (e.g., user lacks permission for this transaction type).
        Covers: Authorization error, status code 403.
        """
        # Mock server is configured to return 403 if amount is 99999.99
        payload = {
            "amount": 99999.99, # Edge case for forbidden
            "currency": "NGN",
            "sender_account": "1234567890",
            "recipient_account": "0987654321",
            "description": "Forbidden test"
        }
        response = await client.post("/transactions/escrow", json=payload, headers=auth_headers)
        assert response.status_code == 403, f"Expected 403, got {response.status_code}. Response: {response.text}"

    @pytest.mark.asyncio
    async def test_05_get_escrow_details_success(self, client: httpx.AsyncClient, auth_headers: Dict[str, str]):
        """
        Test case for successfully retrieving details of an existing escrow.
        Covers: Success case, status code 200, response structure, and data integrity.
        """
        response = await client.get(f"/transactions/escrow/{MOCK_ESCROW_ID}", headers=auth_headers)

        assert response.status_code == 200, f"Expected 200, got {response.status_code}. Response: {response.text}"
        data = response.json()
        assert data["escrow_id"] == MOCK_ESCROW_ID
        assert data["status"] == "CREATED"
        assert "amount" in data
        assert "currency" in data

    @pytest.mark.asyncio
    async def test_06_get_escrow_details_not_found(self, client: httpx.AsyncClient, auth_headers: Dict[str, str]):
        """
        Test case for retrieving details of a non-existent escrow.
        Covers: Edge case (not found), status code 404.
        """
        non_existent_id = "non_existent_id"
        response = await client.get(f"/transactions/escrow/{non_existent_id}", headers=auth_headers)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}. Response: {response.text}"

    @pytest.mark.asyncio
    async def test_07_get_escrow_details_unauthorized(self, client: httpx.AsyncClient, missing_auth_headers: Dict[str, str]):
        """
        Test case for unauthorized access when getting escrow details.
        Covers: Authentication error, status code 401.
        """
        response = await client.get(f"/transactions/escrow/{MOCK_ESCROW_ID}", headers=missing_auth_headers)
        assert response.status_code == 401, f"Expected 401, got {response.status_code}. Response: {response.text}"

    @pytest.mark.asyncio
    async def test_08_claim_escrow_success(self, client: httpx.AsyncClient, auth_headers: Dict[str, str]):
        """
        Test case for successful claiming (releasing funds) of an escrow.
        Covers: Success case, status code 200, and final status update.
        """
        claim_id = "claimable_escrow_1" # Mock server expects this ID to be claimable
        payload = {"claim_details": "Recipient confirmed delivery"}
        response = await client.post(f"/transactions/escrow/{claim_id}/claim", json=payload, headers=auth_headers)

        assert response.status_code == 200, f"Expected 200, got {response.status_code}. Response: {response.text}"
        data = response.json()
        assert data["escrow_id"] == claim_id
        assert data["status"] == "CLAIMED"
        assert "transaction_id" in data

    @pytest.mark.asyncio
    async def test_09_claim_escrow_already_claimed_or_refunded(self, client: httpx.AsyncClient, auth_headers: Dict[str, str]):
        """
        Test case for attempting to claim an escrow that is already in a final state.
        Covers: Edge case (invalid state transition), status code 409 (Conflict).
        """
        final_state_id = "final_state_escrow_2" # Mock server expects this ID to be in a final state
        payload = {"claim_details": "Attempting to claim again"}
        response = await client.post(f"/transactions/escrow/{final_state_id}/claim", json=payload, headers=auth_headers)
        assert response.status_code == 409, f"Expected 409, got {response.status_code}. Response: {response.text}"

    @pytest.mark.asyncio
    async def test_10_refund_escrow_success(self, client: httpx.AsyncClient, auth_headers: Dict[str, str]):
        """
        Test case for successful refunding of an escrow.
        Covers: Success case, status code 200, and final status update.
        """
        refund_id = "refundable_escrow_3" # Mock server expects this ID to be refundable
        payload = {"reason": "Seller failed to deliver"}
        response = await client.post(f"/transactions/escrow/{refund_id}/refund", json=payload, headers=auth_headers)

        assert response.status_code == 200, f"Expected 200, got {response.status_code}. Response: {response.text}"
        data = response.json()
        assert data["escrow_id"] == refund_id
        assert data["status"] == "REFUNDED"
        assert "transaction_id" in data

    @pytest.mark.asyncio
    async def test_11_refund_escrow_unauthorized_user(self, client: httpx.AsyncClient, invalid_auth_headers: Dict[str, str]):
        """
        Test case for unauthorized user attempting to initiate a refund.
        Covers: Authorization error, status code 403 (Forbidden, if user is not sender/admin).
        """
        refund_id = "refundable_escrow_3"
        payload = {"reason": "Unauthorized attempt"}
        # The invalid token will be caught by the authentication layer (401) before the authorization layer (403).
        response = await client.post(f"/transactions/escrow/{refund_id}/refund", json=payload, headers=invalid_auth_headers)
        assert response.status_code == 401, f"Expected 401, got {response.status_code}. Response: {response.text}"

    @pytest.mark.asyncio
    async def test_12_claim_escrow_not_found(self, client: httpx.AsyncClient, auth_headers: Dict[str, str]):
        """
        Test case for attempting to claim a non-existent escrow.
        Covers: Edge case (not found), status code 404.
        """
        non_existent_id = "claim_non_existent"
        payload = {"claim_details": "Non-existent claim"}
        response = await client.post(f"/transactions/escrow/{non_existent_id}/claim", json=payload, headers=auth_headers)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}. Response: {response.text}"

    @pytest.mark.asyncio
    async def test_13_refund_escrow_not_found(self, client: httpx.AsyncClient, auth_headers: Dict[str, str]):
        """
        Test case for attempting to refund a non-existent escrow.
        Covers: Edge case (not found), status code 404.
        """
        non_existent_id = "refund_non_existent"
        payload = {"reason": "Non-existent refund"}
        response = await client.post(f"/transactions/escrow/{non_existent_id}/refund", json=payload, headers=auth_headers)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}. Response: {response.text}"

    @pytest.mark.asyncio
    async def test_14_create_escrow_edge_case_zero_amount(self, client: httpx.AsyncClient, auth_headers: Dict[str, str]):
        """
        Test case for creating an escrow with a zero amount (should fail validation).
        Covers: Edge case (zero amount), status code 400.
        """
        payload = {
            "amount": 0.00,
            "currency": "NGN",
            "sender_account": "1234567890",
            "recipient_account": "0987654321",
            "description": "Zero amount test"
        }
        response = await client.post("/transactions/escrow", json=payload, headers=auth_headers)
        assert response.status_code == 400, f"Expected 400, got {response.status_code}. Response: {response.text}"
        data = response.json()
        assert "detail" in data
        assert "amount" in data["detail"]

    @pytest.mark.asyncio
    async def test_15_get_escrow_details_forbidden_other_user(self, client: httpx.AsyncClient, auth_headers: Dict[str, str]):
        """
        Test case for a user attempting to view an escrow they do not own (Forbidden).
        Covers: Authorization error, status code 403.
        """
        other_user_escrow_id = "other_user_escrow_999" # Mock server expects this ID to belong to another user
        # Mock server is configured to return 403 if the X-User-ID in headers does not match the escrow owner
        response = await client.get(f"/transactions/escrow/{other_user_escrow_id}", headers=auth_headers)
        assert response.status_code == 403, f"Expected 403, got {response.status_code}. Response: {response.text}"

# Total test cases: 15