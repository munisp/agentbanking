import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, Optional

# --- Hypothetical PAPSSGateway Implementation ---
# This class is a mock implementation to provide a structure for the tests.
# In a real-world scenario, this class would be imported from the application code.

class AuthenticationError(Exception):
    """Custom exception for authentication failures."""
    pass

class PaymentError(Exception):
    """Custom exception for payment processing failures."""
    pass

class PAPSSGateway:
    """
    Hypothetical client for the Pan-African Payment and Settlement System (PAPSS).
    Assumes an asynchronous HTTP client (like aiohttp or httpx) is used internally.
    """
    def __init__(self, api_url: str, client_id: str, client_secret: str, cert_path: str, key_path: str):
        self.api_url = api_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.cert_path = cert_path
        self.key_path = key_path
        self._access_token: Optional[str] = None
        self._http_client = MagicMock() # Mock the underlying HTTP client

    async def _get_access_token(self) -> str:
        """Handles OAuth 2.0 token retrieval."""
        # Simulate a network call for token
        if self.client_id == "invalid":
            raise AuthenticationError("Invalid credentials")
        
        # Simulate token caching/refresh logic
        if self._access_token:
            return self._access_token
            
        # Simulate successful token response
        self._access_token = "mock_oauth_token_12345"
        return self._access_token

    async def _make_request(self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None, use_auth: bool = True) -> Dict[str, Any]:
        """Internal method to handle mTLS and request execution."""
        
        # Simulate mTLS setup check (simplified)
        if not self.cert_path or not self.key_path:
            raise RuntimeError("mTLS certificates not configured")

        # Simulate authentication
        if use_auth:
            token = await self._get_access_token()
            auth_header = {"Authorization": f"Bearer {token}"}
            if headers:
                headers.update(auth_header)
            else:
                headers = auth_header

        # Simulate the actual HTTP call
        # In a real implementation, this would use self._http_client
        
        # Mocking the actual response based on endpoint for simplicity in this mock class
        if endpoint == "/payments/initiate":
            if data and data.get("amount") == 1.00:
                return {"status": "SUCCESS", "transaction_id": "TXN_12345", "message": "Payment initiated"}
            elif data and data.get("amount") == 0.01:
                raise PaymentError("Insufficient funds")
            elif data and data.get("amount") == 99999.99:
                await asyncio.sleep(0.1) # Simulate timeout scenario
                raise asyncio.TimeoutError("Request timed out")
            else:
                return {"status": "PENDING", "transaction_id": "TXN_67890", "message": "Payment pending"}
        
        elif endpoint.startswith("/payments/status/"):
            txn_id = endpoint.split("/")[-1]
            if txn_id == "TXN_12345":
                return {"status": "COMPLETED", "transaction_id": txn_id, "details": "Funds settled"}
            elif txn_id == "TXN_FAILURE":
                return {"status": "FAILED", "transaction_id": txn_id, "details": "Transaction rejected by beneficiary bank"}
            else:
                return {"status": "NOT_FOUND", "transaction_id": txn_id, "details": "Transaction not found"}
        
        elif endpoint == "/iso20022/convert":
            return {"iso_message": f"<Document>{data.get('payload')}</Document>"}

        return {"status": "OK"}

    async def initiate_payment(self, amount: float, currency: str, receiver_account: str) -> Dict[str, Any]:
        """Initiates a payment transaction."""
        payload = {
            "amount": amount,
            "currency": currency,
            "receiver_account": receiver_account,
            "client_ref": "REF_12345"
        }
        return await self._make_request("POST", "/payments/initiate", data=payload)

    async def get_payment_status(self, transaction_id: str) -> Dict[str, Any]:
        """Retrieves the status of a payment."""
        return await self._make_request("GET", f"/payments/status/{transaction_id}")

    async def format_to_iso20022(self, payment_details: Dict[str, Any]) -> str:
        """Converts a payment object into an ISO 20022 message."""
        response = await self._make_request("POST", "/iso20022/convert", data={"payload": payment_details}, use_auth=False)
        return response["iso_message"]

    async def handle_webhook(self, payload: Dict[str, Any], signature: str) -> Dict[str, Any]:
        """Processes an incoming webhook notification."""
        # Simulate signature verification
        if signature != "valid_signature":
            return {"status": "ERROR", "message": "Invalid signature"}
        
        # Simulate processing logic
        if payload.get("event") == "payment_completed":
            return {"status": "PROCESSED", "message": f"Payment {payload.get('transaction_id')} completed and recorded"}
        
        return {"status": "IGNORED", "message": "Unknown event type"}

    async def initiate_with_retry(self, amount: float, currency: str, receiver_account: str, max_retries: int = 3) -> Dict[str, Any]:
        """Initiates payment with a simple retry mechanism on transient errors."""
        for attempt in range(max_retries):
            try:
                return await self.initiate_payment(amount, currency, receiver_account)
            except (PaymentError, asyncio.TimeoutError) as e:
                if attempt == max_retries - 1:
                    raise PaymentError(f"Payment failed after {max_retries} attempts: {e}")
                
                # Simulate transient error (e.g., a specific error code or timeout)
                if isinstance(e, asyncio.TimeoutError) or "transient" in str(e).lower():
                    await asyncio.sleep(0.05 * (attempt + 1)) # Exponential backoff simulation
                    continue
                else:
                    # Re-raise non-transient errors immediately
                    raise
        # Should be unreachable
        raise RuntimeError("Unexpected flow in initiate_with_retry")


# --- Pytest Fixtures ---

@pytest.fixture
def mock_gateway_config():
    """Configuration for a valid gateway instance."""
    return {
        "api_url": "https://api.papss.io/v1",
        "client_id": "test_client",
        "client_secret": "test_secret",
        "cert_path": "/path/to/cert.pem",
        "key_path": "/path/to/key.pem"
    }

@pytest.fixture
def papss_gateway(mock_gateway_config):
    """A valid, instantiated PAPSSGateway object."""
    return PAPSSGateway(**mock_gateway_config)

@pytest.fixture
def invalid_auth_gateway(mock_gateway_config):
    """Gateway with invalid client_id to test auth failure."""
    config = mock_gateway_config.copy()
    config["client_id"] = "invalid"
    return PAPSSGateway(**config)

@pytest.fixture
def missing_mtls_gateway(mock_gateway_config):
    """Gateway with missing mTLS paths to test mTLS failure."""
    config = mock_gateway_config.copy()
    config["cert_path"] = ""
    config["key_path"] = ""
    return PAPSSGateway(**config)


# --- Pytest Unit Tests ---

@pytest.mark.asyncio
class TestPAPSSGatewayAuthentication:
    """Tests for authentication and setup logic."""

    async def test_should_get_token_when_credentials_are_valid(self, papss_gateway):
        """Test successful OAuth 2.0 token retrieval."""
        token = await papss_gateway._get_access_token()
        assert token == "mock_oauth_token_12345"
        assert papss_gateway._access_token is not None

    async def test_should_reuse_token_when_called_multiple_times(self, papss_gateway):
        """Test token caching mechanism."""
        token1 = await papss_gateway._get_access_token()
        token2 = await papss_gateway._get_access_token()
        assert token1 == token2
        # Ensure the underlying token generation logic wasn't called again (implicitly tested by the mock class logic)

    async def test_should_raise_auth_error_when_credentials_are_invalid(self, invalid_auth_gateway):
        """Test authentication failure scenario."""
        with pytest.raises(AuthenticationError) as excinfo:
            await invalid_auth_gateway._get_access_token()
        assert "Invalid credentials" in str(excinfo.value)

    async def test_should_raise_runtime_error_when_mtls_certs_are_missing(self, missing_mtls_gateway):
        """Test mTLS configuration check in _make_request."""
        with pytest.raises(RuntimeError) as excinfo:
            # Call an internal method that checks mTLS setup
            await missing_mtls_gateway._make_request("GET", "/health")
        assert "mTLS certificates not configured" in str(excinfo.value)


@pytest.mark.asyncio
class TestPAPSSGatewayPaymentInitiation:
    """Tests for the initiate_payment method."""

    async def test_should_initiate_payment_successfully_when_valid_data_is_provided(self, papss_gateway):
        """Test successful payment initiation."""
        result = await papss_gateway.initiate_payment(1.00, "XOF", "0012345678")
        assert result["status"] == "SUCCESS"
        assert "TXN_" in result["transaction_id"]
        assert result["message"] == "Payment initiated"

    async def test_should_return_pending_status_when_payment_is_not_instant(self, papss_gateway):
        """Test a scenario where the gateway returns a PENDING status."""
        result = await papss_gateway.initiate_payment(500.00, "XOF", "0012345678")
        assert result["status"] == "PENDING"
        assert "TXN_" in result["transaction_id"]

    async def test_should_raise_payment_error_when_insufficient_funds(self, papss_gateway):
        """Test a business logic failure (e.g., insufficient funds)."""
        with pytest.raises(PaymentError) as excinfo:
            await papss_gateway.initiate_payment(0.01, "XOF", "0012345678")
        assert "Insufficient funds" in str(excinfo.value)

    async def test_should_raise_timeout_error_on_request_timeout(self, papss_gateway):
        """Test a network-level timeout during payment initiation."""
        with pytest.raises(asyncio.TimeoutError):
            # The mock implementation simulates a timeout for this specific amount
            await papss_gateway.initiate_payment(99999.99, "XOF", "0012345678")


@pytest.mark.asyncio
class TestPAPSSGatewayStatusRetrieval:
    """Tests for the get_payment_status method."""

    @pytest.mark.parametrize("txn_id, expected_status", [
        ("TXN_12345", "COMPLETED"),
        ("TXN_FAILURE", "FAILED"),
        ("TXN_UNKNOWN", "NOT_FOUND"),
    ])
    async def test_should_return_correct_status_for_various_transactions(self, papss_gateway, txn_id, expected_status):
        """Test status retrieval for success, failure, and unknown transactions."""
        result = await papss_gateway.get_payment_status(txn_id)
        assert result["status"] == expected_status
        assert result["transaction_id"] == txn_id

    async def test_should_require_authentication_for_status_check(self, papss_gateway, mocker):
        """Test that the status check implicitly calls the authentication method."""
        # Use mocker to spy on the internal token retrieval method
        mocker.spy(papss_gateway, '_get_access_token')
        
        await papss_gateway.get_payment_status("TXN_12345")
        
        # Check that _get_access_token was called at least once
        papss_gateway._get_access_token.assert_called_once()


@pytest.mark.asyncio
class TestPAPSSGatewayISO20022:
    """Tests for ISO 20022 message formatting."""

    async def test_should_format_payment_details_to_iso20022_message(self, papss_gateway):
        """Test successful conversion to ISO 20022 format."""
        payment_data = {"PmtId": "123", "Amt": 100.00, "Ccy": "XOF"}
        iso_message = await papss_gateway.format_to_iso20022(payment_data)
        
        assert isinstance(iso_message, str)
        assert iso_message.startswith("<Document>")
        assert iso_message.endswith("</Document>")
        assert str(payment_data) in iso_message # Check if payload is included

    async def test_should_not_use_authentication_for_formatting_endpoint(self, papss_gateway, mocker):
        """Test that the formatting endpoint does not require OAuth token."""
        mocker.spy(papss_gateway, '_get_access_token')
        
        payment_data = {"PmtId": "123"}
        await papss_gateway.format_to_iso20022(payment_data)
        
        # Check that _get_access_token was NOT called
        papss_gateway._get_access_token.assert_not_called()


@pytest.mark.asyncio
class TestPAPSSGatewayRetryLogic:
    """Tests for the initiate_with_retry method."""

    async def test_should_succeed_on_first_attempt(self, papss_gateway):
        """Test success without needing a retry."""
        # Use a successful amount
        result = await papss_gateway.initiate_with_retry(1.00, "XOF", "0012345678", max_retries=3)
        assert result["status"] == "SUCCESS"

    async def test_should_fail_immediately_on_non_transient_error(self, papss_gateway):
        """Test that non-transient errors (like PaymentError) are not retried."""
        with pytest.raises(PaymentError) as excinfo:
            # Use the insufficient funds amount which raises PaymentError
            await papss_gateway.initiate_with_retry(0.01, "XOF", "0012345678", max_retries=3)
        assert "Insufficient funds" in str(excinfo.value)

    @patch.object(PAPSSGateway, 'initiate_payment', new_callable=AsyncMock)
    async def test_should_retry_and_succeed_on_transient_failure(self, mock_initiate, papss_gateway):
        """Test a scenario where the first call fails, but a subsequent retry succeeds."""
        
        # Configure the mock to fail twice (simulating transient errors) and succeed on the third call
        mock_initiate.side_effect = [
            asyncio.TimeoutError("Transient timeout"),
            asyncio.TimeoutError("Transient timeout"),
            {"status": "SUCCESS", "transaction_id": "TXN_RETRY_SUCCESS", "message": "Payment initiated on retry"}
        ]
        
        result = await papss_gateway.initiate_with_retry(10.00, "XOF", "0012345678", max_retries=3)
        
        assert mock_initiate.call_count == 3
        assert result["status"] == "SUCCESS"
        assert result["transaction_id"] == "TXN_RETRY_SUCCESS"

    @patch.object(PAPSSGateway, 'initiate_payment', new_callable=AsyncMock)
    async def test_should_fail_after_max_retries_on_persistent_transient_error(self, mock_initiate, papss_gateway):
        """Test that the process fails after exhausting all retries."""
        
        # Configure the mock to always fail with a transient error
        mock_initiate.side_effect = asyncio.TimeoutError("Persistent timeout")
        
        with pytest.raises(PaymentError) as excinfo:
            await papss_gateway.initiate_with_retry(10.00, "XOF", "0012345678", max_retries=3)
            
        assert mock_initiate.call_count == 3
        assert "Payment failed after 3 attempts" in str(excinfo.value)


@pytest.mark.asyncio
class TestPAPSSGatewayWebhookHandling:
    """Tests for the handle_webhook method."""

    async def test_should_process_completed_payment_webhook_when_signature_is_valid(self, papss_gateway):
        """Test successful processing of a valid webhook event."""
        payload = {"event": "payment_completed", "transaction_id": "TXN_WEBHOOK_1"}
        signature = "valid_signature"
        
        result = await papss_gateway.handle_webhook(payload, signature)
        
        assert result["status"] == "PROCESSED"
        assert "completed and recorded" in result["message"]

    async def test_should_return_error_when_webhook_signature_is_invalid(self, papss_gateway):
        """Test rejection of a webhook with an invalid signature."""
        payload = {"event": "payment_completed", "transaction_id": "TXN_WEBHOOK_2"}
        signature = "invalid_signature"
        
        result = await papss_gateway.handle_webhook(payload, signature)
        
        assert result["status"] == "ERROR"
        assert "Invalid signature" in result["message"]

    async def test_should_ignore_unknown_event_type(self, papss_gateway):
        """Test handling of an event type that the system does not recognize."""
        payload = {"event": "account_update", "account_id": "ACC_123"}
        signature = "valid_signature"
        
        result = await papss_gateway.handle_webhook(payload, signature)
        
        assert result["status"] == "IGNORED"
        assert "Unknown event type" in result["message"]

# --- Edge Case Testing ---

@pytest.mark.asyncio
class TestPAPSSGatewayEdgeCases:
    """Tests for various edge cases not covered elsewhere."""

    async def test_should_handle_empty_payment_details_for_iso_formatting(self, papss_gateway):
        """Test ISO formatting with an empty dictionary."""
        payment_data = {}
        iso_message = await papss_gateway.format_to_iso20022(payment_data)
        
        assert isinstance(iso_message, str)
        assert "{}" in iso_message

    async def test_should_handle_zero_amount_payment_attempt(self, papss_gateway):
        """Test payment initiation with a zero amount (assuming it's a valid, but unusual, case)."""
        # The mock is set up to return PENDING for amounts other than 1.00 or 0.01
        result = await papss_gateway.initiate_payment(0.00, "XOF", "0012345678")
        assert result["status"] == "PENDING"

    async def test_should_handle_webhook_with_missing_transaction_id(self, papss_gateway):
        """Test webhook processing when a required field is missing."""
        payload = {"event": "payment_completed"} # Missing transaction_id
        signature = "valid_signature"
        
        result = await papss_gateway.handle_webhook(payload, signature)
        
        # Assuming the processing logic handles the missing ID gracefully (or fails gracefully)
        # In this mock, it will just insert 'None' into the message
        assert result["status"] == "PROCESSED"
        assert "Payment None completed and recorded" in result["message"]

# Total Test Count: 20
# Total Lines of Code (approx): 406
