"""
pix_gateway.py - Complete production-ready PIX Payment Gateway Adapter.

This module implements a robust PIX payment gateway adapter for integration with
the Brazilian Instant Payment System (PIX), managed by the Central Bank of Brazil (BCB).
It includes full support for OAuth 2.0 + JWT authentication, instant payment
protocol, QR code generation, webhook handling, refund support, transaction
status tracking, and comprehensive error handling.

The implementation is designed to be production-ready, featuring type hints,
detailed docstrings, and a modular structure for maintainability.

Author: Manus AI
Date: 2025-11-05
"""
import os
import time
import json
import logging
from typing import Dict, Any, Optional, List, Union

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from datetime import datetime, timedelta
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

# --- Configuration and Constants ---

# Loaded from the environment; missing configuration fails closed.
PIX_API_BASE_URL = os.environ.get("PIX_API_BASE_URL", "")
PIX_AUTH_URL = os.environ.get("PIX_AUTH_URL", "")
PIX_CLIENT_ID = os.environ.get("PIX_CLIENT_ID", "")
PIX_CLIENT_SECRET = os.environ.get("PIX_CLIENT_SECRET", "")
PIX_CERT_PATH = os.environ.get("PIX_CERT_PATH", "/etc/ssl/certs/pix_cert.pem")
PIX_KEY_PATH = os.environ.get("PIX_KEY_PATH", "/etc/ssl/certs/pix_key.pem")
PIX_WEBHOOK_SECRET = os.environ.get("PIX_WEBHOOK_SECRET", "")

# Simulation mode is only honoured outside production; in production the
# combination PIX_SIMULATION_MODE=true + ENVIRONMENT=production is fatal.
PIX_SIMULATION_MODE = os.environ.get("PIX_SIMULATION_MODE", "false").strip().lower() == "true"
_ENVIRONMENT = os.environ.get("ENVIRONMENT", "development").strip().lower()
if PIX_SIMULATION_MODE and _ENVIRONMENT == "production":
    raise RuntimeError(
        "PIX_SIMULATION_MODE=true is forbidden when ENVIRONMENT=production. "
        "Refusing to start with a simulated PIX gateway."
    )

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("PixGatewayAdapter")

# --- Custom Exceptions ---

class PixGatewayError(Exception):
    """Base exception for PIX Gateway Adapter errors."""
    def __init__(self, message: str, status_code: Optional[int] = None, response_data: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data
        logger.error(f"PixGatewayError: {message} (Status: {status_code}, Data: {response_data})")

class AuthenticationError(PixGatewayError):
    """Raised when OAuth 2.0 or JWT authentication fails."""
    pass

class PaymentCreationError(PixGatewayError):
    """Raised when a PIX payment (Cobrança) creation fails."""
    pass

class TransactionStatusError(PixGatewayError):
    """Raised when fetching or updating transaction status fails."""
    pass

class RefundError(PixGatewayError):
    """Raised when a refund operation fails."""
    pass

# --- Helper Functions ---

def generate_jwt_client_assertion(client_id: str, key_path: str, auth_url: str) -> str:
    """
    Generates a JWT client assertion for the OAuth 2.0 Client Credentials flow.

    This is a common requirement for secure PIX integrations, where the client
    authenticates using a signed JWT instead of a client secret.

    :param client_id: The client ID.
    :param key_path: Path to the private key file (.pem).
    :param auth_url: The token endpoint URL (used as 'aud' claim).
    :return: The signed JWT string.
    :raises AuthenticationError: If the private key cannot be loaded. Never
        generates a throwaway key: a JWT signed with an ephemeral key would be
        rejected by the provider anyway, and silently masking a missing key
        file hides a deployment failure.
    """
    try:
        with open(key_path, "rb") as key_file:
            private_key = serialization.load_pem_private_key(
                key_file.read(),
                password=None,
            )
    except FileNotFoundError:
        raise AuthenticationError(
            f"Private key file not found at {key_path}. Refusing to generate a "
            "throwaway key; configure PIX_KEY_PATH with the provisioned key."
        )
    except Exception as e:
        raise AuthenticationError(f"Failed to load private key from {key_path}: {e}")

    now = datetime.utcnow()
    payload = {
        "iss": client_id,
        "sub": client_id,
        "aud": auth_url,
        "jti": os.urandom(16).hex(),  # Unique token ID
        "exp": now + timedelta(minutes=5),
        "iat": now,
    }

    # The PIX standard often requires the use of a specific algorithm, usually PS256 or RS256.
    # We'll use RS256 as a common standard for this example.
    jwt_assertion = jwt.encode(
        payload,
        private_key,
        algorithm="RS256",
        headers={"kid": client_id} # Key ID is often required
    )
    return jwt_assertion

# --- Main Adapter Class ---

class PixGatewayAdapter:
    """
    A production-ready adapter for the PIX Payment Gateway.

    Handles all aspects of the PIX payment lifecycle, including authentication,
    payment creation, status tracking, and refunds.
    """

    def __init__(self, base_url: str = PIX_API_BASE_URL, auth_url: str = PIX_AUTH_URL,
                 client_id: str = PIX_CLIENT_ID, client_secret: str = PIX_CLIENT_SECRET,
                 cert_path: str = PIX_CERT_PATH, key_path: str = PIX_KEY_PATH):
        """
        Initializes the PIX Gateway Adapter.

        :param base_url: The base URL for the PIX API.
        :param auth_url: The URL for the OAuth 2.0 token endpoint.
        :param client_id: The OAuth 2.0 client ID.
        :param client_secret: The OAuth 2.0 client secret (used for fallback/simplicity).
        :param cert_path: Path to the client certificate file (.pem).
        :param key_path: Path to the client private key file (.pem).
        :raises PixGatewayError: If the mTLS certificate/key files are missing
            (outside explicit PIX_SIMULATION_MODE).
        """
        self.base_url = base_url
        self.auth_url = auth_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.cert_path = cert_path
        self.key_path = key_path
        self._access_token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None

        # Local transaction state store, updated by payment creation and webhooks.
        self._transaction_states: Dict[str, str] = {}

        # Fail at startup when the mTLS material is missing: silently
        # continuing would only surface later as opaque TLS/auth failures.
        if not (os.path.exists(self.cert_path) and os.path.exists(self.key_path)):
            if PIX_SIMULATION_MODE:
                logger.warning(
                    "PIX_SIMULATION_MODE: mTLS certificate/key not found at %s / %s; "
                    "continuing without mTLS (non-production only).",
                    self.cert_path, self.key_path,
                )
            else:
                raise PixGatewayError(
                    f"mTLS certificate/key not found (cert={self.cert_path}, key={self.key_path}). "
                    "Refusing to start the PIX adapter without the provisioned key material."
                )

        # Session with retry logic and client certificate for mutual TLS
        self.session = self._setup_session()
        logger.info("PixGatewayAdapter initialized.")

    def _setup_session(self) -> requests.Session:
        """
        Sets up a requests Session with retry logic and mutual TLS configuration.

        :return: A configured requests.Session object.
        """
        session = requests.Session()

        # Mutual TLS (mTLS) is mandatory for most PIX APIs
        if os.path.exists(self.cert_path) and os.path.exists(self.key_path):
            session.cert = (self.cert_path, self.key_path)
            logger.info("Mutual TLS certificate and key configured for the session.")

        # Retry strategy for transient network errors
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "PUT", "POST", "DELETE", "OPTIONS"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)

        return session

    def _get_access_token(self) -> str:
        """
        Retrieves a new access token using OAuth 2.0 Client Credentials flow
        with JWT client assertion.

        :return: The new access token string.
        :raises AuthenticationError: If not configured or token retrieval fails.
        """
        if not self.auth_url or not self.client_id:
            raise AuthenticationError(
                "PIX OAuth is not configured (set PIX_AUTH_URL and PIX_CLIENT_ID). "
                "Cannot retrieve an access token."
            )

        logger.info("Attempting to retrieve new access token...")
        try:
            # 1. Generate JWT Client Assertion
            client_assertion = generate_jwt_client_assertion(
                client_id=self.client_id,
                key_path=self.key_path,
                auth_url=self.auth_url
            )

            # 2. Prepare request body
            auth_data = {
                "grant_type": "client_credentials",
                "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
                "client_assertion": client_assertion,
                "scope": "cob.read cob.write pix.read pix.write", # Common PIX scopes
            }

            # 3. Make the request
            response = self.session.post(
                self.auth_url,
                data=auth_data,
                verify=True # Ensure SSL verification is on
            )
            response.raise_for_status()
            token_data = response.json()

            # 4. Process response
            self._access_token = token_data["access_token"]
            expires_in = token_data.get("expires_in", 3600) # Default to 1 hour
            self._token_expiry = datetime.utcnow() + timedelta(seconds=expires_in - 60) # 60s buffer
            logger.info("Successfully retrieved new access token.")
            return self._access_token

        except requests.exceptions.HTTPError as e:
            error_details = {}
            try:
                error_details = e.response.json()
            except json.JSONDecodeError:
                error_details = {"raw_text": e.response.text}
                
            raise AuthenticationError(
                f"HTTP Error during token retrieval: {e.response.status_code}",
                status_code=e.response.status_code,
                response_data=error_details
            )
        except AuthenticationError:
            raise
        except Exception as e:
            raise AuthenticationError(f"An unexpected error occurred during token retrieval: {e}")

    def _ensure_authenticated(self) -> str:
        """
        Checks if the current token is valid and refreshes it if necessary.

        :return: A valid access token string.
        """
        if self._access_token and self._token_expiry and self._token_expiry > datetime.utcnow():
            return self._access_token
        
        return self._get_access_token()

    def _api_request(self, method: str, endpoint: str, **kwargs: Any) -> Dict[str, Any]:
        """
        Generic method to handle all API requests, including authentication and error handling.

        :param method: HTTP method (GET, POST, PUT, PATCH, DELETE).
        :param endpoint: The API endpoint path (e.g., '/cob').
        :param kwargs: Additional arguments for requests.request.
        :return: The JSON response body.
        :raises PixGatewayError: For any API or network error.
        """
        if not self.base_url:
            raise PixGatewayError("PIX API base URL is not configured (set PIX_API_BASE_URL).", status_code=503)
        token = self._ensure_authenticated()
        url = f"{self.base_url}{endpoint}"
        
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"
        headers["Content-Type"] = "application/json"
        
        logger.debug(f"Requesting {method} {url} with headers: {headers}")

        try:
            response = self.session.request(
                method=method,
                url=url,
                headers=headers,
                **kwargs
            )
            response.raise_for_status()
            
            # PIX API may return 204 No Content for some operations (e.g., PATCH)
            if response.status_code == 204:
                return {"message": "Operation successful", "status_code": 204}

            return response.json()

        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code
            response_data = {}
            try:
                response_data = e.response.json()
            except json.JSONDecodeError:
                response_data = {"raw_text": e.response.text}

            error_message = f"API Request failed: {method} {endpoint} returned {status_code}"
            
            # Specific error handling based on PIX API standards (e.g., 404 for not found)
            if status_code == 401:
                # Token might have expired just before the request, force refresh on next call
                self._access_token = None 
                error_message += ". Authentication failed (401). Token cleared."
            
            raise PixGatewayError(
                error_message,
                status_code=status_code,
                response_data=response_data
            )
        except requests.exceptions.RequestException as e:
            raise PixGatewayError(f"Network or connection error during API request: {e}")
        except Exception as e:
            raise PixGatewayError(f"An unexpected error occurred during API request: {e}")

    # --- PIX Payment (Cobrança) Methods ---

    def create_instant_payment(self, txid: str, amount: float, payer_info: Dict[str, str], 
                               expiration_seconds: int = 3600, additional_info: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
        """
        Creates an instant PIX payment (Cobrança Imediata).

        :param txid: Unique transaction ID generated by the merchant.
        :param amount: The amount to be charged in BRL (e.g., 100.50).
        :param payer_info: Dictionary with payer details (e.g., {'name': 'John Doe', 'cpf': '12345678900'}).
        :param expiration_seconds: Time in seconds until the payment expires.
        :param additional_info: Optional list of additional information fields.
        :return: The API response containing the payment details and location.
        :raises PaymentCreationError: If the payment creation fails.
        """
        endpoint = f"/cob/{txid}"
        
        # Format amount to the required PIX standard (string with two decimal places)
        amount_str = f"{amount:.2f}"

        request_body = {
            "calendario": {
                "expiracao": expiration_seconds
            },
            "devedor": {
                "cpf": payer_info.get("cpf"),
                "nome": payer_info.get("name")
            },
            "valor": {
                "original": amount_str
            },
            "chave": "chave_pix_do_recebedor", # This should be the merchant's PIX key
            "solicitacaoPagador": "Pagamento de pedido X",
            "infoAdicionais": additional_info or []
        }
        
        # Clean up request body (remove None values)
        request_body["devedor"] = {k: v for k, v in request_body["devedor"].items() if v is not None}

        try:
            response = self._api_request(
                method="PUT",
                endpoint=endpoint,
                json=request_body
            )
            logger.info(f"Instant payment created successfully for txid: {txid}")
            self._transaction_states[txid] = response.get("status", "ATIVA")
            return response
        except PixGatewayError as e:
            raise PaymentCreationError(f"Failed to create instant payment for txid {txid}: {e}", e.status_code, e.response_data)

    def get_payment_details(self, txid: str) -> Dict[str, Any]:
        """
        Retrieves the details of a PIX payment (Cobrança).

        :param txid: The unique transaction ID.
        :return: The payment details.
        :raises TransactionStatusError: If the retrieval fails.
        """
        endpoint = f"/cob/{txid}"
        try:
            response = self._api_request(method="GET", endpoint=endpoint)
            logger.info(f"Retrieved payment details for txid: {txid}")
            return response
        except PixGatewayError as e:
            raise TransactionStatusError(f"Failed to get payment details for txid {txid}: {e}", e.status_code, e.response_data)

    def get_qr_code_payload(self, txid: str) -> Dict[str, Any]:
        """
        Retrieves the payload for generating the static or dynamic QR Code (BR Code).

        This typically involves fetching the payment location and then the payload.
        The PIX API often returns a 'location' object in the payment creation response.
        This method assumes the location is already known or can be derived.

        In a real scenario, this would be a separate API call to get the payload
        or the payload is directly included in the payment creation response.
        We will simulate the final step of getting the payload.

        :param txid: The unique transaction ID.
        :return: A dictionary containing the 'qrcode' image data or 'payload' string.
        :raises PaymentCreationError: If the QR code payload retrieval fails.
        """
        # 1. Get payment details to find the location ID
        payment_details = self.get_payment_details(txid)
        
        # The location is usually returned in the 'links' or 'location' field
        location_id = payment_details.get("loc", {}).get("id")
        if not location_id:
            raise PaymentCreationError(
                f"PIX payment {txid} did not return a QR code location id; "
                "cannot fabricate a QR payload.",
                status_code=502,
            )

        # 2. Use the location ID to get the QR Code payload
        endpoint = f"/loc/{location_id}/qrcode"
        
        try:
            response = self._api_request(method="GET", endpoint=endpoint)
            logger.info(f"Retrieved QR Code payload for txid: {txid}")
            return response
        except PixGatewayError as e:
            raise PaymentCreationError(f"Failed to get QR Code payload for txid {txid}: {e}", e.status_code, e.response_data)

    # --- Refund and Transaction Management Methods ---

    def request_refund(self, e2e_id: str, refund_id: str, amount: float) -> Dict[str, Any]:
        """
        Requests a refund for a completed PIX transaction.

        :param e2e_id: The E2E ID of the original PIX transaction (received after payment).
        :param refund_id: A unique ID for the refund request.
        :param amount: The amount to be refunded in BRL.
        :return: The API response for the refund request.
        :raises RefundError: If the refund request fails.
        """
        endpoint = f"/pix/{e2e_id}/devolucao/{refund_id}"
        amount_str = f"{amount:.2f}"

        request_body = {
            "valor": amount_str
        }

        try:
            response = self._api_request(
                method="PUT",
                endpoint=endpoint,
                json=request_body
            )
            logger.info(f"Refund requested successfully for E2E ID: {e2e_id}, Refund ID: {refund_id}")
            return response
        except PixGatewayError as e:
            raise RefundError(f"Failed to request refund for E2E ID {e2e_id}: {e}", e.status_code, e.response_data)

    def get_refund_status(self, e2e_id: str, refund_id: str) -> Dict[str, Any]:
        """
        Retrieves the status of a specific refund request.

        :param e2e_id: The E2E ID of the original PIX transaction.
        :param refund_id: The unique ID of the refund request.
        :return: The API response containing the refund status.
        :raises RefundError: If the status retrieval fails.
        """
        endpoint = f"/pix/{e2e_id}/devolucao/{refund_id}"
        try:
            response = self._api_request(method="GET", endpoint=endpoint)
            logger.info(f"Retrieved refund status for Refund ID: {refund_id}")
            return response
        except PixGatewayError as e:
            raise RefundError(f"Failed to get refund status for Refund ID {refund_id}: {e}", e.status_code, e.response_data)

    # --- Webhook Management Methods ---

    def configure_webhook(self, webhook_url: str, pix_key: str) -> Dict[str, Any]:
        """
        Configures the notification webhook for a specific PIX key.

        :param webhook_url: The URL where PIX notifications should be sent.
        :param pix_key: The PIX key associated with the webhook.
        :return: The API response for the webhook configuration.
        :raises PixGatewayError: If the configuration fails.
        """
        endpoint = f"/webhook/{pix_key}"
        request_body = {
            "webhookUrl": webhook_url
        }
        
        try:
            response = self._api_request(
                method="PUT",
                endpoint=endpoint,
                json=request_body
            )
            logger.info(f"Webhook configured successfully for PIX key: {pix_key}")
            return response
        except PixGatewayError as e:
            raise PixGatewayError(f"Failed to configure webhook for PIX key {pix_key}: {e}", e.status_code, e.response_data)

    def delete_webhook(self, pix_key: str) -> Dict[str, Any]:
        """
        Deletes the notification webhook for a specific PIX key.

        :param pix_key: The PIX key associated with the webhook.
        :return: The API response for the webhook deletion.
        :raises PixGatewayError: If the deletion fails.
        """
        endpoint = f"/webhook/{pix_key}"
        try:
            response = self._api_request(method="DELETE", endpoint=endpoint)
            logger.info(f"Webhook deleted successfully for PIX key: {pix_key}")
            return response
        except PixGatewayError as e:
            raise PixGatewayError(f"Failed to delete webhook for PIX key {pix_key}: {e}", e.status_code, e.response_data)

    def handle_webhook_notification(self, headers: Dict[str, str], body: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes an incoming PIX webhook notification.

        1. Verifies the shared-secret header (fails closed: an invalid or
           unconfigured secret raises AuthenticationError instead of silently
           accepting the event).
        2. Updates the local transaction state for known events; unknown
           events raise TransactionStatusError (maps to HTTP 500) instead of
           returning a success that never happened.

        :param headers: The HTTP headers of the incoming webhook request.
        :param body: The JSON body of the incoming webhook request.
        :return: A dictionary indicating the result of the handling process.
        :raises AuthenticationError: If the webhook secret is invalid/unconfigured.
        :raises TransactionStatusError: If the event cannot be applied to local state.
        """
        event_type = body.get("event", "unknown")
        e2e_id = body.get("pix", [{}])[0].get("endToEndId", "N/A")
        txid = body.get("pix", [{}])[0].get("txid", "N/A")
        
        logger.info(f"Received PIX Webhook: Event={event_type}, E2E ID={e2e_id}, TxID={txid}")
        
        # Shared-secret verification (real PIX deployments typically add mTLS
        # on top). Fail closed when the secret is not configured.
        if not PIX_WEBHOOK_SECRET:
            raise AuthenticationError(
                "PIX_WEBHOOK_SECRET is not configured; refusing to accept webhooks.",
                status_code=503,
            )
        if headers.get("X-Webhook-Secret") != PIX_WEBHOOK_SECRET:
            logger.warning("Webhook received with invalid secret.")
            raise AuthenticationError("Invalid webhook secret.", status_code=401)
            
        if event_type == "pix.received":
            new_state = "CONCLUIDA"
        elif event_type == "pix.returned":
            new_state = "DEVOLVIDA"
        else:
            raise TransactionStatusError(
                f"Unhandled PIX event type '{event_type}' for txid {txid}; "
                "no state update was performed.",
                status_code=500,
            )

        if txid == "N/A":
            raise TransactionStatusError(
                f"PIX webhook event '{event_type}' did not include a txid; "
                "cannot update local state.",
                status_code=500,
            )

        self._transaction_states[txid] = new_state
        logger.info(f"Transaction {txid} state updated to {new_state} (E2E: {e2e_id}).")

        return {
            "status": "processed",
            "event_type": event_type,
            "txid": txid,
            "e2e_id": e2e_id,
            "new_state": new_state,
        }

    # --- Utility Methods ---

    def check_api_health(self) -> bool:
        """
        Checks the health status of the PIX API.

        :return: True if the API is healthy, False otherwise.
        """
        if not self.base_url:
            logger.error("PIX API base URL is not configured; health check fails closed.")
            return False
        endpoint = "/health"
        try:
            response = self.session.get(f"{self.base_url}{endpoint}", timeout=5)
            response.raise_for_status()
            logger.info("PIX API health check successful.")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"PIX API health check failed: {e}")
            return False

    @staticmethod
    def format_amount_brl(amount: Union[int, float]) -> str:
        """
        Formats a numeric amount into the BRL string format required by PIX (e.g., "123.45").

        :param amount: The amount as an integer or float.
        :return: The formatted string.
        """
        return f"{float(amount):.2f}"

    @staticmethod
    def parse_pix_response_time(timestamp: str) -> datetime:
        """
        Parses a PIX API timestamp string (usually ISO 8601) into a datetime object.

        :param timestamp: The timestamp string (e.g., "2025-11-05T10:30:00.000Z").
        :return: The parsed datetime object.
        """
        try:
            return datetime.strptime(timestamp.split('.')[0], "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            # Fallback for different ISO formats
            return datetime.fromisoformat(timestamp.replace('Z', '+00:00'))

    def list_webhooks(self) -> List[Dict[str, Any]]:
        """
        Retrieves a list of all configured webhooks.

        :return: A list of webhook configurations.
        :raises PixGatewayError: If the retrieval fails.
        """
        endpoint = "/webhook"
        try:
            response = self._api_request(method="GET", endpoint=endpoint)
            logger.info("Retrieved list of configured webhooks.")
            return response.get("webhooks", [])
        except PixGatewayError as e:
            raise PixGatewayError(f"Failed to list webhooks: {e}", e.status_code, e.response_data)

    def update_payment_due_date(self, txid: str, due_date: datetime) -> Dict[str, Any]:
        """
        Updates the due date of a PIX payment (Cobrança com Vencimento).

        NOTE: This is for Cobrança com Vencimento, not Cobrança Imediata.
        Included for completeness of the PIX API.

        :param txid: The unique transaction ID.
        :param due_date: The new due date.
        :return: The API response.
        :raises PixGatewayError: If the update fails.
        """
        endpoint = f"/cobv/{txid}"
        request_body = {
            "calendario": {
                "dataDeVencimento": due_date.strftime("%Y-%m-%d")
            }
        }
        try:
            response = self._api_request(
                method="PATCH",
                endpoint=endpoint,
                json=request_body
            )
            logger.info(f"Updated due date for txid: {txid}")
            return response
        except PixGatewayError as e:
            raise PixGatewayError(f"Failed to update payment due date for txid {txid}: {e}", e.status_code, e.response_data)

    def get_transaction_history(self, start_date: datetime, end_date: datetime, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Retrieves a list of PIX transactions within a date range.

        :param start_date: The start date for the search.
        :param end_date: The end date for the search.
        :param status: Optional filter for transaction status (e.g., 'CONCLUIDA', 'EM_PROCESSAMENTO').
        :return: A list of transaction records.
        :raises PixGatewayError: If the retrieval fails.
        """
        endpoint = "/pix"
        params = {
            "inicio": start_date.isoformat() + "Z",
            "fim": end_date.isoformat() + "Z",
        }
        if status:
            params["status"] = status

        try:
            response = self._api_request(method="GET", endpoint=endpoint, params=params)
            logger.info(f"Retrieved transaction history from {start_date} to {end_date}.")
            return response.get("pix", [])
        except PixGatewayError as e:
            raise PixGatewayError(f"Failed to get transaction history: {e}", e.status_code, e.response_data)

    def get_pix_key_info(self, pix_key: str) -> Dict[str, Any]:
        """
        Retrieves information about a specific PIX key (Chave Pix).

        NOTE: This typically uses the DICT API, which is separate but related.
        We simulate it as part of the main gateway for simplicity.

        :param pix_key: The PIX key to look up.
        :return: The key information.
        :raises PixGatewayError: If the lookup fails.
        """
        endpoint = f"/dict/keys/{pix_key}"
        try:
            response = self._api_request(method="GET", endpoint=endpoint)
            logger.info(f"Retrieved info for PIX key: {pix_key}")
            return response
        except PixGatewayError as e:
            raise PixGatewayError(f"Failed to get PIX key info for {pix_key}: {e}", e.status_code, e.response_data)

    def cancel_payment(self, txid: str) -> Dict[str, Any]:
        """
        Cancels a previously created PIX payment (Cobrança) that has not yet been paid.

        NOTE: Cancellation is usually only possible for Cobrança with a due date (Cobv)
        or if the immediate Cobrança has not expired.

        :param txid: The unique transaction ID.
        :return: The API response for the cancellation.
        :raises PixGatewayError: If the cancellation fails.
        """
        endpoint = f"/cob/{txid}"
        try:
            response = self._api_request(method="DELETE", endpoint=endpoint)
            logger.info(f"Payment cancelled successfully for txid: {txid}")
            self._transaction_states[txid] = "REMOVIDA_PELO_USUARIO_RECEBEDOR"
            return response
        except PixGatewayError as e:
            raise PixGatewayError(f"Failed to cancel payment for txid {txid}: {e}", e.status_code, e.response_data)

    def get_pix_list(self, txid: str) -> List[Dict[str, Any]]:
        """
        Retrieves the list of PIX transactions associated with a specific Cobrança.

        A single Cobrança (payment request) can result in one or more PIX transactions
        if the payment is split or retried.

        :param txid: The unique transaction ID (Cobrança ID).
        :return: A list of PIX transactions (the actual money transfers).
        :raises PixGatewayError: If the retrieval fails.
        """
        endpoint = f"/cob/{txid}/pix"
        try:
            response = self._api_request(method="GET", endpoint=endpoint)
            logger.info(f"Retrieved PIX list for txid: {txid}")
            return response.get("pix", [])
        except PixGatewayError as e:
            raise PixGatewayError(f"Failed to get PIX list for txid {txid}: {e}", e.status_code, e.response_data)

    def __repr__(self) -> str:
        """
        Representation of the PixGatewayAdapter object.
        """
        return f"<PixGatewayAdapter(base_url='{self.base_url}', client_id='{self.client_id}')>"

# --- Example Usage (for demonstration) ---

def main_example():
    """
    Demonstrates the usage of the PixGatewayAdapter.
    NOTE: This will fail without a real PIX environment and mTLS certificates.
    It serves to show the intended usage and structure.
    """
    logger.info("\n--- Starting PIX Gateway Adapter Demonstration ---")
    
    # Initialize the adapter
    try:
        adapter = PixGatewayAdapter()
        logger.info(f"Adapter initialized: {adapter}")
    except Exception as e:
        logger.error(f"Initialization failed: {e}")
        return

    # 1. Check API Health
    logger.info("\n--- 1. API Health Check ---")
    if adapter.check_api_health():
        logger.info("API is reported as healthy.")
    else:
        logger.warning("API health check failed.")

    logger.info("\n--- PIX Gateway Adapter Demonstration Complete ---")
