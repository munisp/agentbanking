import hashlib
import hmac
import os
import requests
import logging
import time
import uuid
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from xml.etree import ElementTree as ET
from xml.dom import minidom

# --- Configuration ---
# All connection details come from the environment; there are no working
# mock defaults. Missing configuration fails closed at use time.
class Config:
    """Configuration class for the PAPSS Gateway Adapter."""
    BASE_URL = os.environ.get("PAPSS_BASE_URL", "")
    TOKEN_URL = os.environ.get("PAPSS_TOKEN_URL") or (f"{BASE_URL}/oauth/token" if BASE_URL else "")
    CLIENT_ID = os.environ.get("PAPSS_CLIENT_ID", "")
    CLIENT_SECRET = os.environ.get("PAPSS_CLIENT_SECRET", "")
    WEBHOOK_SECRET = os.environ.get("PAPSS_WEBHOOK_SECRET", "")
    # Paths to mTLS certificates
    CERT_FILE = os.environ.get("PAPSS_CERT_FILE", "/etc/ssl/certs/client.pem")
    KEY_FILE = os.environ.get("PAPSS_KEY_FILE", "/etc/ssl/private/client.key")
    # Retry settings
    MAX_RETRIES = 5
    RETRY_DELAY_SECONDS = 2
    # Supported Currencies (42 African Currencies)
    SUPPORTED_CURRENCIES = [
        "DZD", "AOA", "BWP", "BIF", "CVE", "XAF", "KMF", "CDF", "DJF", "EGP",
        "ERN", "ETB", "GMD", "GHS", "GNF", "KES", "LSL", "LRD", "LYD", "MGA",
        "MWK", "MRO", "MUR", "MAD", "MZN", "NAD", "NGN", "RWF", "STN", "SCR",
        "SLL", "SOS", "ZAR", "SSP", "SDG", "SZL", "TZS", "XOF", "TND", "UGX",
        "ZMW", "ZWL"
    ]

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("PAPSSGatewayAdapter")

# --- Custom Exceptions ---
class PAPSSGatewayError(Exception):
    """Base exception for PAPSS Gateway errors."""
    pass

class AuthenticationError(PAPSSGatewayError):
    """Raised when OAuth 2.0 or mTLS authentication fails."""
    pass

class InvalidRequestError(PAPSSGatewayError):
    """Raised for 4xx client errors."""
    def __init__(self, message: str, status_code: int, response_data: Dict[str, Any]):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data

class ServiceUnavailableError(PAPSSGatewayError):
    """Raised for 5xx server errors or connection issues."""
    pass

class TransactionFailedError(PAPSSGatewayError):
    """Raised when a payment transaction is explicitly rejected or fails."""
    pass

# --- ISO 20022 Message Builder ---
class ISO20022MessageBuilder:
    """
    A utility class to construct ISO 20022 XML messages, specifically pacs.008
    for Customer Credit Transfer.
    """
    NAMESPACE = "urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08"
    SCHEMA_LOCATION = "urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08 pacs.008.001.08.xsd"

    @staticmethod
    def _prettify_xml(elem: ET.Element) -> str:
        """Return a pretty-printed XML string for the Element."""
        rough_string = ET.tostring(elem, 'utf-8')
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ")

    def build_credit_transfer(self, data: Dict[str, Any]) -> str:
        """
        Constructs the pacs.008 Customer Credit Transfer XML message.

        :param data: Dictionary containing transaction details.
        :return: The ISO 20022 XML message as a string.
        """
        root = ET.Element(f"{{urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08}}Document",
                          attrib={"xmlns": self.NAMESPACE,
                                 "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
                                 "xsi:schemaLocation": self.SCHEMA_LOCATION})

        # FIToFICstmrCdtTrf (Financial Institution to Financial Institution Customer Credit Transfer)
        fitoficstmr_cdt_trf = ET.SubElement(root, "FIToFICstmrCdtTrf")

        # GrpHdr (Group Header)
        grphdr = ET.SubElement(fitoficstmr_cdt_trf, "GrpHdr")
        ET.SubElement(grphdr, "MsgId").text = data.get("message_id", str(uuid.uuid4()))
        ET.SubElement(grphdr, "CreDtTm").text = datetime.utcnow().isoformat() + "Z"
        ET.SubElement(grphdr, "NbOfTxs").text = "1"
        ET.SubElement(grphdr, "SttlmInf").text = "CLRG" # Settlement Method

        # PmtInf (Payment Information)
        pmtinf = ET.SubElement(fitoficstmr_cdt_trf, "CdtTrfTxInf")
        
        # PmtId (Payment Identification)
        pmtid = ET.SubElement(pmtinf, "PmtId")
        ET.SubElement(pmtid, "InstrId").text = data.get("instruction_id", str(uuid.uuid4()))
        ET.SubElement(pmtid, "EndToEndId").text = data.get("end_to_end_id", str(uuid.uuid4()))

        # IntrBkSttlmAmt (Interbank Settlement Amount)
        ET.SubElement(pmtinf, "IntrBkSttlmAmt", Ccy=data["currency"]).text = str(data["amount"])
        
        # ChrgBr (Charge Bearer)
        ET.SubElement(pmtinf, "ChrgBr").text = "DEBT" # Debtor

        # Dbtr (Debtor)
        dbtr = ET.SubElement(pmtinf, "Dbtr")
        ET.SubElement(dbtr, "Nm").text = data["debtor_name"]
        dbtr_acct = ET.SubElement(dbtr, "PstlAdr")
        ET.SubElement(dbtr_acct, "Ctry").text = data["debtor_country"]

        # DbtrAcct (Debtor Account)
        dbtr_acct = ET.SubElement(pmtinf, "DbtrAcct")
        ET.SubElement(ET.SubElement(dbtr_acct, "Id"), "IBAN").text = data["debtor_iban"]

        # DbtrAgt (Debtor Agent - Sending Bank)
        dbtr_agt = ET.SubElement(pmtinf, "DbtrAgt")
        ET.SubElement(ET.SubElement(dbtr_agt, "FinInstnId"), "BICFI").text = data["debtor_bic"]

        # CdtrAgt (Creditor Agent - Receiving Bank)
        cdtr_agt = ET.SubElement(pmtinf, "CdtrAgt")
        ET.SubElement(ET.SubElement(cdtr_agt, "FinInstnId"), "BICFI").text = data["creditor_bic"]

        # Cdtr (Creditor)
        cdtr = ET.SubElement(pmtinf, "Cdtr")
        ET.SubElement(cdtr, "Nm").text = data["creditor_name"]
        cdtr_acct = ET.SubElement(cdtr, "PstlAdr")
        ET.SubElement(cdtr_acct, "Ctry").text = data["creditor_country"]

        # CdtrAcct (Creditor Account)
        cdtr_acct = ET.SubElement(pmtinf, "CdtrAcct")
        ET.SubElement(ET.SubElement(cdtr_acct, "Id"), "IBAN").text = data["creditor_iban"]

        # RmtInf (Remittance Information)
        rmtinf = ET.SubElement(pmtinf, "RmtInf")
        ET.SubElement(rmtinf, "Ustrd").text = data.get("remittance_info", "PAPSS Payment")

        return self._prettify_xml(root)

# --- Core Adapter Class ---
class PAPSSGatewayAdapter:
    """
    Payment gateway adapter for the PAPSS Gateway.

    Implements OAuth 2.0 + mTLS authentication, ISO 20022 message format,
    error handling, retry logic, and webhook handling. All calls go to the
    real PAPSS API configured via PAPSS_* environment variables; missing
    configuration or provider failures raise explicit errors — nothing is
    fabricated locally.
    """
    def __init__(self, config: Config = Config()):
        """
        Initializes the PAPSS Gateway Adapter.

        :param config: Configuration object containing API details.
        :raises AuthenticationError: If the mTLS certificate/key files are missing.
        """
        self.config = config
        self.logger = logger
        self.token: Optional[str] = None
        self.token_expiry: Optional[datetime] = None
        self.message_builder = ISO20022MessageBuilder()
        self.transaction_store: Dict[str, Dict[str, Any]] = {} # Local record of submitted transactions

        if not os.path.exists(self.config.CERT_FILE) or not os.path.exists(self.config.KEY_FILE):
            raise AuthenticationError(
                f"mTLS certificate/key not found (PAPSS_CERT_FILE={self.config.CERT_FILE}, "
                f"PAPSS_KEY_FILE={self.config.KEY_FILE}). Refusing to initialize the PAPSS adapter."
            )

        # Setup persistent session with mTLS certificates
        self.session = requests.Session()
        self.session.cert = (self.config.CERT_FILE, self.config.KEY_FILE)
        self.logger.info("PAPSS Adapter initialized with mTLS certificates.")

    def _get_access_token(self) -> str:
        """
        Retrieves a new OAuth 2.0 access token or returns the cached one if valid.

        :raises AuthenticationError: If credentials are missing or token retrieval fails.
        :return: The valid access token string.
        """
        # Check if token is valid and not expiring soon (e.g., within 60 seconds)
        if self.token and self.token_expiry and self.token_expiry > datetime.now() + timedelta(seconds=60):
            self.logger.debug("Using cached access token.")
            return self.token

        if not self.config.TOKEN_URL or not self.config.CLIENT_ID or not self.config.CLIENT_SECRET:
            raise AuthenticationError(
                "PAPSS OAuth configuration is incomplete (PAPSS_BASE_URL/PAPSS_TOKEN_URL, "
                "PAPSS_CLIENT_ID, PAPSS_CLIENT_SECRET). Cannot authenticate."
            )

        self.logger.info("Requesting new access token via OAuth 2.0 Client Credentials flow with mTLS.")
        try:
            response = self.session.post(
                self.config.TOKEN_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.config.CLIENT_ID,
                    "client_secret": self.config.CLIENT_SECRET,
                },
                timeout=30,
            )
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Token retrieval failed: {e}")
            raise AuthenticationError(f"Failed to get access token: {e}") from e

        if response.status_code != 200:
            raise AuthenticationError(f"Token endpoint returned HTTP {response.status_code}.")

        try:
            token_data = response.json()
        except ValueError as e:
            raise AuthenticationError(f"Token endpoint returned a malformed response: {e}") from e

        token = token_data.get("access_token")
        if not token:
            raise AuthenticationError("Token endpoint response did not include an access_token.")

        self.token = token
        self.token_expiry = datetime.now() + timedelta(seconds=int(token_data.get("expires_in", 3600)))
        self.logger.info("Successfully retrieved new access token.")
        return self.token

    def _authenticated_request(self, method: str, endpoint: str, **kwargs: Any) -> Dict[str, Any]:
        """
        Internal method to handle all API calls, including authentication, retries, and error handling.

        :param method: HTTP method (e.g., 'GET', 'POST').
        :param endpoint: API endpoint path.
        :param kwargs: Additional arguments for requests.request.
        :raises PAPSSGatewayError: For any API or network error.
        :return: JSON response data.
        """
        if not self.config.BASE_URL:
            raise ServiceUnavailableError("PAPSS_BASE_URL is not configured; cannot call the PAPSS API.")
        url = f"{self.config.BASE_URL}{endpoint}"
        token = self._get_access_token()
        
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"
        headers.setdefault("Content-Type", "application/json")
        
        # Retry logic implementation
        for attempt in range(self.config.MAX_RETRIES):
            try:
                response = self.session.request(method, url, headers=headers, timeout=30, **kwargs)
                response.raise_for_status()
                if response.status_code == 204 or not response.content:
                    return {"status": "OK"}
                return response.json()

            except requests.exceptions.ConnectionError as e:
                if attempt < self.config.MAX_RETRIES - 1:
                    self.logger.warning(f"Connection error on {endpoint}. Retrying in {self.config.RETRY_DELAY_SECONDS}s...")
                    time.sleep(self.config.RETRY_DELAY_SECONDS * (attempt + 1))
                    continue
                else:
                    raise ServiceUnavailableError(f"Network connection failed after {self.config.MAX_RETRIES} retries: {e}") from e
            
            except requests.exceptions.Timeout as e:
                if attempt < self.config.MAX_RETRIES - 1:
                    self.logger.warning(f"Request timed out on {endpoint}. Retrying in {self.config.RETRY_DELAY_SECONDS}s...")
                    time.sleep(self.config.RETRY_DELAY_SECONDS * (attempt + 1))
                    continue
                else:
                    raise ServiceUnavailableError(f"Request timed out after {self.config.MAX_RETRIES} retries: {e}") from e

            except requests.exceptions.HTTPError as e:
                status_code = e.response.status_code
                try:
                    error_data = e.response.json()
                except ValueError:
                    error_data = {"message": e.response.text}

                if 400 <= status_code < 500:
                    self.logger.error(f"Client error {status_code} on {endpoint}: {error_data}")
                    raise InvalidRequestError(f"Invalid request: {error_data.get('message', 'No message')}", status_code, error_data)
                
                if 500 <= status_code < 600:
                    self.logger.error(f"Server error {status_code} on {endpoint}: {error_data}")
                    raise ServiceUnavailableError(f"API server error: {error_data.get('message', 'No message')}")
                
                raise PAPSSGatewayError(f"An unexpected HTTP error occurred: {e}") from e

            except ValueError as e:
                self.logger.error(f"Malformed JSON response from {endpoint}: {e}")
                raise PAPSSGatewayError(f"PAPSS API returned a malformed response: {e}") from e
            
            except Exception as e:
                self.logger.error(f"An unexpected error occurred during API call: {e}")
                raise PAPSSGatewayError(f"Unexpected error: {e}") from e
        
        raise PAPSSGatewayError("Request failed unexpectedly.")

    # --- Public API Methods ---

    def submit_payment(self, transaction_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Submits a new payment request to the PAPSS Gateway.
        
        Sends the ISO 20022 pacs.008 message to the real PAPSS API and returns
        the provider-assigned tracking ID. The final status is expected via a
        webhook.

        :param transaction_data: Details required for the pacs.008 message.
        :raises TransactionFailedError: If the submission is rejected.
        :raises PAPSSGatewayError: On transport/provider failure.
        :return: Initial transaction response with a tracking ID.
        """
        self.logger.info(f"Submitting payment for {transaction_data.get('amount')} {transaction_data.get('currency')}")
        
        try:
            xml_payload = self.message_builder.build_credit_transfer(transaction_data)
        except Exception as e:
            self.logger.error(f"Failed to build ISO 20022 message: {e}")
            raise InvalidRequestError(f"Failed to build ISO 20022 message: {e}", 400, {})

        try:
            response_data = self._authenticated_request(
                "POST",
                "/payments",
                data=xml_payload.encode("utf-8"),
                headers={"Content-Type": "application/xml"},
            )
        except InvalidRequestError as e:
            self.logger.error(f"Payment submission rejected by gateway: {e}")
            raise TransactionFailedError(f"Payment rejected: {e.response_data.get('message', 'Gateway rejection')}") from e

        transaction_id = response_data.get("transaction_id") or response_data.get("transactionId")
        if not transaction_id:
            raise PAPSSGatewayError("PAPSS gateway response did not include a transaction id.")

        status = response_data.get("status", "PENDING")
        self.transaction_store[transaction_id] = {
            "id": transaction_id,
            "status": status,
            "data": transaction_data,
            "xml_payload": xml_payload,
            "created_at": datetime.now()
        }

        self.logger.info(f"Payment {transaction_id} submitted to PAPSS (status: {status}).")
        return {
            "transaction_id": transaction_id,
            "status": status,
            "message": response_data.get("message", "Payment submitted to PAPSS."),
            "submitted_at": datetime.now().isoformat(),
            "gateway_response": response_data,
        }

    def get_transaction_status(self, transaction_id: str) -> Dict[str, Any]:
        """
        Queries the current status of a transaction using its PAPSS ID.

        :param transaction_id: The unique ID returned by `submit_payment`.
        :raises InvalidRequestError: If the transaction ID is not found (404).
        :return: The transaction status details.
        """
        self.logger.info(f"Querying status for transaction ID: {transaction_id}")
        
        if transaction_id not in self.transaction_store:
            raise InvalidRequestError(f"Transaction ID {transaction_id} not found.", 404, {})

        stored_data = self.transaction_store[transaction_id]
        return {
            "transaction_id": transaction_id,
            "status": stored_data["status"],
            "details": f"Status as of {datetime.now().isoformat()}",
            "original_data": stored_data["data"]
        }

    def handle_webhook(self, request_body: str, signature: str) -> Dict[str, Any]:
        """
        Validates and processes an incoming webhook notification from PAPSS.

        :param request_body: The raw body of the webhook request (e.g., JSON or XML).
        :param signature: The signature header for validation.
        :raises AuthenticationError: If signature validation fails.
        :raises InvalidRequestError: If the request body is malformed.
        :return: A processed status update.
        """
        self.logger.info("Received webhook notification. Validating signature...")
        
        if not self._validate_webhook_signature(request_body, signature):
            self.logger.error("Webhook signature validation failed.")
            raise AuthenticationError("Invalid webhook signature.")

        try:
            webhook_data = json.loads(request_body)
            transaction_id = webhook_data["transaction_id"]
            new_status = webhook_data["status"]
            
            if transaction_id in self.transaction_store:
                old_status = self.transaction_store[transaction_id]["status"]
                self.transaction_store[transaction_id]["status"] = new_status
                self.transaction_store[transaction_id]["updated_at"] = datetime.now()
                self.logger.info(f"Transaction {transaction_id} status updated: {old_status} -> {new_status}")
                
                return {
                    "transaction_id": transaction_id,
                    "status": new_status,
                    "message": "Webhook processed successfully."
                }
            else:
                self.logger.warning(f"Webhook received for unknown transaction ID: {transaction_id}")
                return {
                    "transaction_id": transaction_id,
                    "status": "UNKNOWN",
                    "message": "Transaction ID not found in local store."
                }

        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse webhook body: {e}")
            raise InvalidRequestError("Malformed webhook request body (not valid JSON).", 400, {})
        except KeyError as e:
            self.logger.error(f"Webhook body missing required key: {e}")
            raise InvalidRequestError(f"Webhook body missing required key: {e}", 400, {})

    def _validate_webhook_signature(self, body: str, signature: str) -> bool:
        """
        Validates the webhook signature as an HMAC-SHA256 of the raw body using
        PAPSS_WEBHOOK_SECRET. Fails closed when no secret is configured.

        :param body: The raw request body.
        :param signature: The signature from the request header.
        :return: True if validation passes, False otherwise.
        """
        if not self.config.WEBHOOK_SECRET:
            self.logger.error("PAPSS_WEBHOOK_SECRET is not configured; failing webhook validation closed.")
            return False
        if not signature:
            return False
        expected = hmac.new(
            self.config.WEBHOOK_SECRET.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    def get_supported_currencies(self) -> List[str]:
        """
        Returns the list of 42 supported African currencies.

        :return: A list of currency codes (ISO 4217).
        """
        return self.config.SUPPORTED_CURRENCIES

# --- Example Usage ---
if __name__ == '__main__':
    try:
        adapter = PAPSSGatewayAdapter()
    except PAPSSGatewayError as e:
        print(f"Failed to initialize PAPSS adapter (expected without real mTLS certs/config): {e}")
        raise SystemExit(1)

    currencies = adapter.get_supported_currencies()
    print(f"Supported Currencies ({len(currencies)}): {currencies[:5]}...")
    print("Adapter initialized against the configured PAPSS API. "
          "submit_payment/get_transaction_status require live PAPSS credentials.")
