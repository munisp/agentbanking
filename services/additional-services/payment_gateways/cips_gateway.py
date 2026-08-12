import os
import re
import json
import hmac
import hashlib
import time
import logging
from typing import Dict, Any, Optional, List, Callable
from functools import wraps

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --- Configuration and Constants ---

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# CIPS API configuration — no working mock defaults; missing config fails closed.
CIPS_API_BASE_URL = os.environ.get("CIPS_API_BASE_URL", "")
CIPS_SENDER_ID = os.environ.get("CIPS_SENDER_ID", "")
CIPS_WEBHOOK_SECRET = os.environ.get("CIPS_WEBHOOK_SECRET", "")
CIPS_SIMULATION_MODE = os.environ.get("CIPS_SIMULATION_MODE", "false").strip().lower() == "true"
_ENVIRONMENT = os.environ.get("ENVIRONMENT", "development").strip().lower()

if CIPS_SIMULATION_MODE and _ENVIRONMENT == "production":
    raise RuntimeError(
        "CIPS_SIMULATION_MODE=true is forbidden when ENVIRONMENT=production. "
        "Refusing to start with a simulated CIPS gateway."
    )

ENDPOINTS = {
    "payment_initiation": "/payment/initiate",
    "payment_status": "/payment/status",
    "webhook_ack": "/webhook/acknowledge",
}

# Error Codes and Messages (based on common financial API practices)
CIPS_ERROR_CODES = {
    "0000": "Success",
    "1001": "Invalid ISO 20022 Message Format",
    "1002": "Authentication Failed (mTLS)",
    "2001": "Insufficient Funds",
    "2002": "Beneficiary Account Invalid",
    "3001": "Transaction Timeout (RTGS)",
    "4001": "System Maintenance",
}

# Transaction Statuses
class TransactionStatus:
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SETTLED = "SETTLED"
    FAILED = "FAILED"
    REVERSED = "REVERSED"

# --- Utility Functions and Decorators ---

def retry_on_failure(max_retries: int = 3, delay: int = 5) -> Callable:
    """Decorator to implement retry logic for API calls."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            for attempt in range(max_retries):
                try:
                    result = func(*args, **kwargs)
                    # Check for a business-level failure in the response structure
                    if result and result.get("status") == "error":
                        error_code = result.get("error_code", "UNKNOWN")
                        if error_code in ["3001", "4001"]: # Retryable errors (Timeout, System Maintenance)
                            logger.warning(f"Retryable error {error_code} on attempt {attempt + 1}. Retrying in {delay}s...")
                            time.sleep(delay)
                            continue
                        else:
                            # Non-retryable business error
                            return result
                    return result
                except requests.exceptions.RequestException as e:
                    logger.error(f"Network/Request error on attempt {attempt + 1}: {e}")
                    if attempt < max_retries - 1:
                        logger.warning(f"Retrying in {delay}s...")
                        time.sleep(delay)
                    else:
                        logger.error("Max retries reached. Failing transaction.")
                        raise
            return None # Should not be reached if max_retries > 0
        return wrapper
    return decorator

# --- Message Formatters (ISO 20022 / SWIFT MT) ---

class MessageFormatter:
    """
    Handles the creation and parsing of ISO 20022 and SWIFT MT messages.
    """
    @staticmethod
    def create_iso20022_pain001(
        payment_details: Dict[str, Any],
        sender_id: str,
        message_id: str
    ) -> str:
        """
        Creates an ISO 20022 pain.001 (Customer Credit Transfer Initiation) message.
        This is a simplified JSON representation of the complex XML structure.
        """
        iso_message = {
            "GrpHdr": {
                "MsgId": message_id,
                "CreDtTm": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "NbOfTxs": 1,
                "InitgPty": {"Id": {"OrgId": {"Othr": [{"Id": sender_id}]}}}
            },
            "PmtInf": {
                "PmtInfId": f"PMT_{message_id}",
                "PmtMtd": "TRF",
                "BtchBookg": True,
                "PmtTpInf": {"SvcLvl": {"Cd": "URGP"}}, # RTGS/Real-time
                "ReqdExctnDt": payment_details.get("execution_date", time.strftime("%Y-%m-%d")),
                "CdtTrfTxInf": {
                    "PmtId": {"EndToEndId": payment_details["transaction_id"]},
                    "Amt": {"InstdAmt": {"Ccy": "CNY", "Value": payment_details["amount"]}},
                    "Dbtr": {"Nm": payment_details["debtor_name"]},
                    "CdtrAgt": {"FinInstnId": {"BICFI": payment_details["beneficiary_bank_bic"]}},
                    "Cdtr": {"Nm": payment_details["beneficiary_name"]},
                    "CdtrAcct": {"Id": {"Othr": [{"Id": payment_details["beneficiary_account"]}]}},
                    "RmtInf": {"Ustrd": payment_details.get("purpose", "Cross-Border Payment")}
                }
            }
        }
        return json.dumps(iso_message, indent=2)

    @staticmethod
    def parse_swift_mt103(mt_message: str) -> Dict[str, Any]:
        """
        Parses a SWIFT MT103 (Customer Transfer) message, extracting the core
        fields from the block-based MT format.

        :param mt_message: The raw MT103 message text.
        :raises ValueError: If the message is not a parseable MT103.
        :return: The parsed fields.
        """
        if not mt_message or ":20:" not in mt_message:
            raise ValueError("Not a parseable SWIFT MT103 message (missing :20: transaction reference).")

        def _tag(tag: str) -> Optional[str]:
            match = re.search(rf"{re.escape(tag)}(.*?)(?=:\d{{2}}[A-Z]?:|$)", mt_message, re.DOTALL)
            return match.group(1).strip() if match else None

        transaction_reference = _tag(":20:")
        value_date_ccy_amount = _tag(":32A:")
        ordering_customer = _tag(":50K:") or _tag(":50F:")
        beneficiary_customer = _tag(":59:")

        value_date = currency = amount = None
        if value_date_ccy_amount:
            compact = value_date_ccy_amount.replace("\n", "")
            match = re.match(r"(\d{6})([A-Z]{3})([\d,\.]+)", compact)
            if match:
                value_date, currency, amount = match.group(1), match.group(2), match.group(3)

        return {
            "message_type": "MT103",
            "transaction_reference": transaction_reference,
            "value_date": value_date,
            "currency": currency,
            "amount": amount,
            "ordering_customer": ordering_customer,
            "beneficiary_customer": beneficiary_customer,
        }

# --- CIPS Gateway Adapter Class ---

class CIPSGatewayAdapter:
    """
    Adapter for the CIPS (Cross-Border Interbank Payment System) Gateway.

    Handles mTLS authentication, ISO 20022 message formatting, transaction
    tracking, error handling, and retry logic. All calls go to the real CIPS
    API configured via CIPS_* environment variables; missing configuration or
    provider failures are surfaced as explicit errors — nothing is fabricated.
    """
    def __init__(self, cert_file: str, key_file: str, ca_bundle_file: str, api_base_url: str = CIPS_API_BASE_URL):
        """
        Initializes the CIPS Gateway Adapter.

        :param cert_file: Path to the client's digital certificate file (.pem).
        :param key_file: Path to the client's private key file (.pem).
        :param ca_bundle_file: Path to the CA bundle file for server verification.
        :param api_base_url: Base URL for the CIPS API.
        :raises ValueError: If CIPS_SENDER_ID or the API base URL is not configured.
        :raises FileNotFoundError: If any certificate/key file is missing.
        """
        self.api_base_url = api_base_url
        if not self.api_base_url:
            raise ValueError("CIPS API base URL is not configured (set CIPS_API_BASE_URL).")
        if not CIPS_SENDER_ID:
            raise ValueError("CIPS sender id is not configured (set CIPS_SENDER_ID).")
        self.cert_file = cert_file
        self.key_file = key_file
        self.ca_bundle_file = ca_bundle_file
        self.session = self._setup_mtls_session()
        self.message_formatter = MessageFormatter()
        logger.info("CIPS Gateway Adapter initialized with mTLS configuration.")

    def _setup_mtls_session(self) -> requests.Session:
        """
        Sets up a requests.Session with mTLS (Mutual TLS) configuration and retry mechanism.

        :return: Configured requests.Session object.
        :raises FileNotFoundError: If any certificate/key file is missing.
        """
        missing = [f for f in [self.cert_file, self.key_file, self.ca_bundle_file] if not os.path.exists(f)]
        if missing:
            raise FileNotFoundError(f"mTLS certificate/key files are missing: {missing}")

        session = requests.Session()
        # mTLS configuration: client certificate and key
        session.cert = (self.cert_file, self.key_file)
        # Server certificate verification using CA bundle
        session.verify = self.ca_bundle_file

        # Configure retry strategy for transient network errors
        retry_strategy = Retry(
            total=5,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST", "GET"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)

        return session

    def _send_request(self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Internal method to send an authenticated request to the CIPS API.

        :param method: HTTP method ('POST' or 'GET').
        :param endpoint: The specific API endpoint path.
        :param data: JSON payload for POST requests.
        :return: Parsed JSON response from the API.
        """
        path = ENDPOINTS.get(endpoint)
        if not path:
            raise ValueError(f"Unknown API endpoint: {endpoint}")
        url = f"{self.api_base_url.rstrip('/')}{path}"

        try:
            if method == 'POST':
                response = self.session.post(url, json=data, timeout=30)
            elif method == 'GET':
                response = self.session.get(url, params=data, timeout=30)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            return self._handle_api_response(response.json())

        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP Error {e.response.status_code} for {url}: {e.response.text}")
            return self._create_error_response(f"HTTP_ERROR_{e.response.status_code}", str(e))
        except requests.exceptions.RequestException as e:
            logger.error(f"Network/Request Error for {url}: {e}")
            return self._create_error_response("NETWORK_ERROR", str(e))
        except Exception as e:
            logger.critical(f"Unexpected Error during API call to {url}: {e}")
            return self._create_error_response("UNEXPECTED_ERROR", str(e))

    def _handle_api_response(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes the raw API response, checks for business errors, and logs.

        :param response_data: The JSON response from the CIPS API.
        :return: The processed response data.
        """
        status_code = response_data.get("code", "9999")
        status_message = CIPS_ERROR_CODES.get(status_code, "Unknown Status")

        if status_code != "0000":
            logger.error(f"CIPS Business Error: Code={status_code}, Message={status_message}")
            response_data["status"] = "error"
            response_data["error_code"] = status_code
            response_data["error_message"] = status_message
        else:
            response_data["status"] = "success"
            logger.info(f"CIPS Success: {status_message}")

        return response_data

    def _create_error_response(self, error_code: str, error_message: str) -> Dict[str, Any]:
        """
        Creates a standardized error response dictionary.
        """
        return {
            "status": "error",
            "error_code": error_code,
            "error_message": error_message,
            "timestamp": time.time()
        }

    @retry_on_failure(max_retries=5, delay=10)
    def initiate_cross_border_payment(self, payment_details: Dict[str, Any]) -> Dict[str, Any]:
        """
        Initiates a cross-border RMB/CNY payment via the CIPS RTGS protocol.

        The payment message is formatted as an ISO 20022 pain.001 message.

        :param payment_details: Dictionary containing payment data (amount, currency, accounts, etc.).
        :return: API response dictionary with transaction status.
        """
        # 1. Validate required fields
        required_fields = ["transaction_id", "amount", "debtor_name", "beneficiary_name", "beneficiary_account", "beneficiary_bank_bic"]
        if not all(field in payment_details for field in required_fields):
            return self._create_error_response("VALIDATION_ERROR", "Missing required payment details.")

        # 2. Format the ISO 20022 message
        try:
            iso_message = self.message_formatter.create_iso20022_pain001(
                payment_details=payment_details,
                sender_id=CIPS_SENDER_ID,
                message_id=payment_details["transaction_id"]
            )
            logger.info(f"ISO 20022 pain.001 message created for TXN: {payment_details['transaction_id']}")
        except Exception as e:
            return self._create_error_response("MESSAGE_FORMAT_ERROR", f"Failed to format ISO 20022 message: {e}")

        # 3. Prepare API payload
        payload = {
            "message_type": "ISO_20022_PAIN001",
            "message_content": iso_message,
            "transaction_id": payment_details["transaction_id"],
            "currency": "CNY", # Enforce RMB/CNY
            "settlement_type": "RTGS"
        }

        # 4. Send request (mTLS secured)
        response = self._send_request('POST', 'payment_initiation', data=payload)

        # 5. Track settlement status from the provider response
        if response.get("status") == "success":
            response["initial_status"] = response.get("cips_status", TransactionStatus.PROCESSING)
            self.track_transaction_status(payment_details["transaction_id"]) # Start tracking
        
        return response

    def track_transaction_status(self, transaction_id: str) -> Dict[str, Any]:
        """
        Queries the CIPS Gateway for the current status of a transaction.

        Never defaults to SETTLED: if the provider does not report a status,
        an explicit error is returned.

        :param transaction_id: The unique ID of the transaction.
        :return: Dictionary containing the latest transaction status.
        """
        logger.info(f"Tracking status for transaction: {transaction_id}")
        
        # 1. Prepare API payload
        payload = {
            "query_type": "TxStatusReq",
            "transaction_id": transaction_id,
            "query_timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")
        }

        # 2. Send request (mTLS secured)
        response = self._send_request('GET', 'payment_status', data=payload)

        # 3. Process and return status
        if response.get("status") == "success":
            current_status = response.get("cips_status")
            if not current_status:
                logger.error(f"CIPS status response for {transaction_id} did not include a status.")
                return self._create_error_response(
                    "STATUS_UNAVAILABLE",
                    f"CIPS did not report a status for transaction {transaction_id}."
                )
            response["current_status"] = current_status
            logger.info(f"Transaction {transaction_id} status: {current_status}")
        
        return response

    def handle_webhook(self, webhook_data: Dict[str, Any], raw_signature: str) -> Dict[str, Any]:
        """
        Processes an incoming webhook notification from the CIPS Gateway.

        Verifies an HMAC-SHA256 signature over the canonical payload using
        CIPS_WEBHOOK_SECRET. Fails closed when no secret is configured.

        :param webhook_data: The payload received from the webhook.
        :param raw_signature: The signature header for verification.
        :return: A dictionary for the webhook acknowledgment response.
        """
        logger.info("Received webhook. Starting verification and processing.")
        
        # 1. Signature Verification (HMAC-SHA256 over canonical JSON body)
        if not CIPS_WEBHOOK_SECRET:
            logger.error("CIPS_WEBHOOK_SECRET is not configured; failing webhook validation closed.")
            return {"status": "error", "message": "Webhook verification not configured"}

        canonical_body = json.dumps(webhook_data, sort_keys=True, separators=(",", ":"))
        expected_signature = hmac.new(
            CIPS_WEBHOOK_SECRET.encode("utf-8"),
            canonical_body.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        if not raw_signature or not hmac.compare_digest(expected_signature, raw_signature):
            logger.error("Webhook signature verification failed.")
            return {"status": "error", "message": "Invalid signature"}

        # 2. Process Event
        event_type = webhook_data.get("event_type")
        transaction_id = webhook_data.get("transaction_id")
        new_status = webhook_data.get("new_status")

        if event_type == "PAYMENT_STATUS_UPDATE":
            logger.info(f"Webhook: TXN {transaction_id} updated to {new_status}")
            # In production: Update local database record for the transaction
            # self.db.update_transaction_status(transaction_id, new_status)
            
            # 3. Acknowledge the webhook
            ack_response = self._send_request('POST', 'webhook_ack', data={"transaction_id": transaction_id, "status": "ACKNOWLEDGED"})
            return ack_response
        
        logger.warning(f"Unhandled webhook event type: {event_type}")
        return {"status": "success", "message": "Event processed or ignored"}

    def generate_mt_report(self, transaction_id: str) -> Dict[str, Any]:
        """
        Generates a SWIFT MT report (e.g., MT103) for a transaction.

        Requires a real MT message source; fails loud because none is configured.

        :param transaction_id: The unique ID of the transaction.
        :raises NotImplementedError: Always, until a real reporting source is wired.
        """
        raise NotImplementedError(
            "SWIFT MT reporting requires a real MT message source (reporting API or "
            "message store) which is not configured; refusing to fabricate an MT103 report "
            f"for transaction {transaction_id}."
        )

# --- Example Usage ---

if __name__ == "__main__":
    cert_file = os.environ.get("CIPS_CERT_FILE", "/etc/ssl/certs/client.pem")
    key_file = os.environ.get("CIPS_KEY_FILE", "/etc/ssl/private/client.key")
    ca_bundle = os.environ.get("CIPS_CA_BUNDLE", "/etc/ssl/certs/cips_ca.pem")

    try:
        gateway = CIPSGatewayAdapter(
            cert_file=cert_file,
            key_file=key_file,
            ca_bundle_file=ca_bundle
        )
        logger.info("CIPS adapter initialized against the configured CIPS API.")
    except Exception as e:
        logger.error(f"Failed to initialize CIPS Gateway Adapter: {e}")
        exit(1)

# End of cips_gateway.py
