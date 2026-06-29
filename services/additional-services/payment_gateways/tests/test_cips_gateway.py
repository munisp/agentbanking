import pytest
import asyncio
from unittest.mock import patch, MagicMock
import os
from typing import Dict, Any

# Assuming cips_gateway.py is in the same directory
from cips_gateway import CIPSGateway, CIPSGatewayError, CIPS_SUCCESS_STATUS, CIPS_FAILURE_STATUS, CIPS_PENDING_STATUS, CIPS_CROSS_BORDER_CODE, CIPS_DOMESTIC_CODE

# --- Fixtures for Mocking Files and Setup ---

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for pytest-asyncio."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="module")
def mock_cert_files(tmp_path_factory):
    """
    Fixture to create mock certificate and key files for mTLS.
    The CIPSGateway constructor requires these paths.
    """
    # Create a temporary directory for the files
    temp_dir = tmp_path_factory.mktemp("certs")
    
    # Create mock files
    cert_file = temp_dir / "client.pem"
    key_file = temp_dir / "client.key"
    ca_file = temp_dir / "ca.pem"
    
    # Write some dummy content
    cert_file.write_text("---BEGIN CERTIFICATE---")
    key_file.write_text("---BEGIN PRIVATE KEY---")
    ca_file.write_text("---BEGIN CA CERTIFICATE---")
    
    # Return the paths
    return {
        "cert_path": str(cert_file),
        "key_path": str(key_file),
        "ca_path": str(ca_file),
        "invalid_path": "/non/existent/file.pem"
    }

@pytest.fixture
def cips_gateway_instance(mock_cert_files):
    """Fixture to create a valid CIPSGateway instance."""
    return CIPSGateway(
        api_url="https://api.cips.example.com/v1",
        cert_path=mock_cert_files["cert_path"],
        key_path=mock_cert_files["key_path"],
        ca_path=mock_cert_files["ca_path"]
    )

@pytest.fixture
def cips_gateway_invalid_auth(mock_cert_files):
    """Fixture to create a CIPSGateway instance with invalid auth paths."""
    return CIPSGateway(
        api_url="https://api.cips.example.com/v1",
        cert_path=mock_cert_files["invalid_path"],
        key_path=mock_cert_files["key_path"],
        ca_path=mock_cert_files["ca_path"]
    )

# --- Fixtures for Test Data ---

@pytest.fixture
def domestic_payment_data() -> Dict[str, Any]:
    """Standard domestic payment data."""
    return {
        "transaction_id": "TXN-DOM-12345",
        "amount": 1000.50,
        "currency": "CNY",
        "beneficiary_details": {
            "name": "Beneficiary A",
            "account": "6222020000000000001",
            "bank_id": "ICBKCNBJ"
        }
    }

@pytest.fixture
def cross_border_payment_data() -> Dict[str, Any]:
    """Standard cross-border payment data."""
    return {
        "transaction_id": "TXN-CB-67890",
        "amount": 5000.00,
        "currency": "USD",
        "beneficiary_details": {
            "name": "Foreign Bank B",
            "account": "US1234567890",
            "swift_bic": "CHASUS33"
        }
    }

# --- Test Class Structure ---

class TestCIPSGateway:
    """
    Comprehensive test suite for the CIPSGateway class.
    Tests cover authentication, payment initiation, status retrieval,
    and message formatting (ISO 20022 and SWIFT MT).
    """
    @pytest.mark.asyncio
    async def test_should_create_valid_ssl_context_when_auth_config_is_complete(self, cips_gateway_instance):
        """Test successful creation of SSL context for mTLS."""
        context = await cips_gateway_instance._get_ssl_context()
        assert isinstance(context, CIPSGateway.ssl.SSLContext)
        # Check if the context has loaded a certificate chain (basic check for mTLS setup)
        # This is hard to check directly, so we rely on the method not raising an exception.
        # We can check the purpose to ensure it's for server auth as intended.
        assert context.purpose == CIPSGateway.ssl.Purpose.SERVER_AUTH

    @pytest.mark.asyncio
    async def test_should_raise_error_when_mtls_config_is_incomplete(self, mock_cert_files):
        """Test that CIPSGatewayError is raised when mTLS config is missing paths."""
        # Create an instance with a missing key path
        gateway = CIPSGateway(
            api_url="https://api.cips.example.com/v1",
            cert_path=mock_cert_files["cert_path"],
            key_path="", # Missing key path
            ca_path=mock_cert_files["ca_path"]
        )
        with pytest.raises(CIPSGatewayError) as excinfo:
            await gateway._get_ssl_context()
        assert "mTLS configuration is incomplete" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_should_return_auth_failure_when_invalid_cert_path_is_used(self, cips_gateway_invalid_auth, domestic_payment_data):
        """Test that a request fails with an AUTH_FAIL code when mTLS setup fails."""
        # Since we cannot easily mock the internal ssl module's behavior, we will
        # mock the _get_ssl_context method itself to raise the expected error
        # when using the invalid auth gateway.
        
        with patch.object(cips_gateway_invalid_auth, '_get_ssl_context', side_effect=CIPSGatewayError("mTLS configuration is incomplete.")):
            response = await cips_gateway_invalid_auth.initiate_payment(
                **domestic_payment_data
            )
            assert response["status"] == "ERROR"
            assert response["code"] == "AUTH_FAIL"
            assert "mTLS configuration is incomplete" in response["message"]

    def test_should_format_domestic_payment_to_iso20022_xml(self, cips_gateway_instance, domestic_payment_data):
        """Test the ISO 20022 message formatting."""
        formatted_message = cips_gateway_instance._format_iso20022(domestic_payment_data)
        assert "<Document>" in formatted_message
        assert f"<PmtId>{domestic_payment_data['transaction_id']}</PmtId>" in formatted_message
        assert f"<Amt>{domestic_payment_data['amount']}</Amt>" in formatted_message
        assert f"<Ccy>{domestic_payment_data['currency']}</Ccy>" in formatted_message

    def test_should_format_cross_border_payment_to_swift_mt(self, cips_gateway_instance, cross_border_payment_data):
        """Test the SWIFT MT message formatting."""
        formatted_message = cips_gateway_instance._format_swift_mt(cross_border_payment_data)
        assert formatted_message.startswith("{1:F01BANKXXXXXX}")
        assert cross_border_payment_data['transaction_id'] in formatted_message
        assert str(cross_border_payment_data['amount']) in formatted_message
        assert cross_border_payment_data['currency'] in formatted_message

    @pytest.mark.asyncio
    async def test_should_initiate_domestic_payment_successfully(self, cips_gateway_instance, domestic_payment_data):
        """Test successful initiation of a domestic payment."""
        response = await cips_gateway_instance.initiate_payment(
            is_cross_border=False,
            **domestic_payment_data
        )
        assert response["status"] == CIPS_SUCCESS_STATUS
        assert "cips_ref" in response
        assert response["cips_ref"] is not None

    @pytest.mark.asyncio
    async def test_should_initiate_cross_border_payment_successfully(self, cips_gateway_instance, cross_border_payment_data):
        """Test successful initiation of a cross-border payment."""
        response = await cips_gateway_instance.initiate_payment(
            is_cross_border=True,
            **cross_border_payment_data
        )
        assert response["status"] == CIPS_SUCCESS_STATUS
        assert "cips_ref" in response
        assert response["cips_ref"] is not None

    @pytest.mark.asyncio
    @pytest.mark.parametrize("missing_field", ["transaction_id", "amount", "currency"])
    async def test_should_fail_when_required_fields_are_missing(self, cips_gateway_instance, domestic_payment_data, missing_field):
        """Test payment initiation failure when required data is missing."""
        data = domestic_payment_data.copy()
        data[missing_field] = None
        
        response = await cips_gateway_instance.initiate_payment(
            is_cross_border=False,
            **data
        )
        assert response["status"] == CIPS_FAILURE_STATUS
        assert "Missing required fields" in response["message"]

    @pytest.mark.asyncio
    async def test_should_fail_when_amount_is_invalid(self, cips_gateway_instance, domestic_payment_data):
        """Test payment initiation failure when amount is zero or negative (edge case)."""
        data = domestic_payment_data.copy()
        data["amount"] = 0.00
        
        response = await cips_gateway_instance.initiate_payment(
            is_cross_border=False,
            **data
        )
        assert response["status"] == CIPS_FAILURE_STATUS
        assert "Invalid amount" in response["message"]

    @pytest.mark.asyncio
    async def test_should_fail_on_internal_cips_auth_error(self, cips_gateway_instance, domestic_payment_data):
        """Test payment initiation failure due to an internal CIPS authentication error."""
        data = domestic_payment_data.copy()
        data["transaction_id"] = "FAIL_AUTH" # Special ID to trigger mock failure
        
        response = await cips_gateway_instance.initiate_payment(
            is_cross_border=False,
            **data
        )
        assert response["status"] == CIPS_FAILURE_STATUS
        assert "Internal CIPS Auth Error" in response["message"]

    @pytest.mark.asyncio
    async def test_should_fail_cross_border_with_unsupported_currency(self, cips_gateway_instance, cross_border_payment_data):
        """Test cross-border payment failure with a currency not supported for CB (edge case)."""
        data = cross_border_payment_data.copy()
        data["currency"] = "INR" # Unsupported currency for CB in mock
        
        response = await cips_gateway_instance.initiate_payment(
            is_cross_border=True,
            **data
        )
        assert response["status"] == CIPS_FAILURE_STATUS
        assert "Unsupported cross-border currency" in response["message"]

    @pytest.mark.asyncio
    async def test_should_use_iso20022_for_domestic_payment(self, cips_gateway_instance, domestic_payment_data):
        """Test that the correct message format (ISO 20022) is used for domestic payments."""
        # We mock the _send_request to inspect the data it receives
        with patch.object(cips_gateway_instance, '_send_request', wraps=cips_gateway_instance._send_request) as mock_send:
            await cips_gateway_instance.initiate_payment(
                is_cross_border=False,
                **domestic_payment_data
            )
            # Check the data passed to _send_request
            call_args = mock_send.call_args[0][1]
            assert call_args["message_format"] == "ISO_20022"
            assert call_args["message_body"].startswith("<Document>")

    @pytest.mark.asyncio
    async def test_should_use_swift_mt_for_cross_border_payment(self, cips_gateway_instance, cross_border_payment_data):
        """Test that the correct message format (SWIFT MT) is used for cross-border payments."""
        # We mock the _send_request to inspect the data it receives
        with patch.object(cips_gateway_instance, '_send_request', wraps=cips_gateway_instance._send_request) as mock_send:
            await cips_gateway_instance.initiate_payment(
                is_cross_border=True,
                **cross_border_payment_data
            )
            # Check the data passed to _send_request
            call_args = mock_send.call_args[0][1]
            assert call_args["message_format"] == "SWIFT_MT"
            assert call_args["message_body"].startswith("{1:F01BANKXXXXXX}")

    @pytest.mark.asyncio
    async def test_should_get_successful_payment_status(self, cips_gateway_instance):
        """Test retrieval of a successfully settled payment status."""
        cips_ref = "REF_SUCCESS"
        response = await cips_gateway_instance.get_payment_status(cips_ref)
        assert response["status"] == CIPS_SUCCESS_STATUS
        assert "Settled successfully" in response["details"]

    @pytest.mark.asyncio
    async def test_should_get_pending_payment_status(self, cips_gateway_instance):
        """Test retrieval of a payment status that is still pending."""
        cips_ref = "REF_PENDING"
        response = await cips_gateway_instance.get_payment_status(cips_ref)
        assert response["status"] == CIPS_PENDING_STATUS
        assert "Still waiting for settlement" in response["details"]

    @pytest.mark.asyncio
    async def test_should_get_rejected_payment_status(self, cips_gateway_instance):
        """Test retrieval of a rejected payment status."""
        cips_ref = "REF_REJECTED"
        response = await cips_gateway_instance.get_payment_status(cips_ref)
        assert response["status"] == CIPS_FAILURE_STATUS
        assert "Rejected by beneficiary bank" in response["details"]

    @pytest.mark.asyncio
    async def test_should_fail_when_cips_ref_is_not_found(self, cips_gateway_instance):
        """Test failure when the CIPS reference is not found."""
        cips_ref = "REF_NOT_FOUND"
        response = await cips_gateway_instance.get_payment_status(cips_ref)
        assert response["status"] == "ERROR"
        assert response["code"] == "NOT_FOUND"
        assert "CIPS reference not found" in response["message"]

    @pytest.mark.asyncio
    async def test_should_fail_when_cips_ref_is_missing(self, cips_gateway_instance):
        """Test failure when the CIPS reference is an empty string."""
        cips_ref = ""
        response = await cips_gateway_instance.get_payment_status(cips_ref)
        assert response["status"] == "ERROR"
        assert response["code"] == "MISSING_REF"
        assert "Missing CIPS reference" in response["message"]