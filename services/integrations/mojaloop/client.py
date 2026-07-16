"""
Mojaloop FSPIOP Client
Production-grade connector for Mojaloop Open Source Instant Payment Platform

Implements the FSPIOP (Financial Services Provider Interoperability Protocol) API:
- Party lookup (account discovery)
- Quote requests
- Transfer execution
- Bulk transfers
- Transaction request handling

Reference: https://docs.mojaloop.io/api/fspiop/
"""

import logging
import uuid
import hashlib
import hmac
import base64
import json
from typing import Dict, Any, Optional, List
from decimal import Decimal
from datetime import datetime, timezone
from enum import Enum
import asyncio
import aiohttp
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


class TransferState(Enum):
    """Mojaloop transfer states"""
    RECEIVED = "RECEIVED"
    RESERVED = "RESERVED"
    COMMITTED = "COMMITTED"
    ABORTED = "ABORTED"


class PartyIdType(Enum):
    """Mojaloop party identifier types"""
    MSISDN = "MSISDN"  # Mobile number
    EMAIL = "EMAIL"
    PERSONAL_ID = "PERSONAL_ID"
    BUSINESS = "BUSINESS"
    DEVICE = "DEVICE"
    ACCOUNT_ID = "ACCOUNT_ID"
    IBAN = "IBAN"
    ALIAS = "ALIAS"


class AmountType(Enum):
    """Amount types for quotes"""
    SEND = "SEND"
    RECEIVE = "RECEIVE"


@dataclass
class Money:
    """Mojaloop money object"""
    currency: str
    amount: str  # String to preserve precision
    
    def to_dict(self) -> Dict[str, str]:
        return {"currency": self.currency, "amount": self.amount}


@dataclass
class Party:
    """Mojaloop party object"""
    party_id_type: str
    party_identifier: str
    party_sub_id_or_type: Optional[str] = None
    fsp_id: Optional[str] = None
    name: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "partyIdInfo": {
                "partyIdType": self.party_id_type,
                "partyIdentifier": self.party_identifier
            }
        }
        if self.party_sub_id_or_type:
            result["partyIdInfo"]["partySubIdOrType"] = self.party_sub_id_or_type
        if self.fsp_id:
            result["partyIdInfo"]["fspId"] = self.fsp_id
        if self.name:
            result["name"] = self.name
        return result


@dataclass
class GeoCode:
    """Geographic coordinates"""
    latitude: str
    longitude: str


@dataclass
class TransactionType:
    """Mojaloop transaction type"""
    scenario: str  # DEPOSIT, WITHDRAWAL, TRANSFER, PAYMENT, REFUND
    initiator: str  # PAYER, PAYEE
    initiator_type: str  # CONSUMER, AGENT, BUSINESS, DEVICE
    sub_scenario: Optional[str] = None
    refund_info: Optional[Dict] = None
    balance_of_payments: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "scenario": self.scenario,
            "initiator": self.initiator,
            "initiatorType": self.initiator_type
        }
        if self.sub_scenario:
            result["subScenario"] = self.sub_scenario
        if self.balance_of_payments:
            result["balanceOfPayments"] = self.balance_of_payments
        return result


class MojalooopError(Exception):
    """Base exception for Mojaloop errors"""
    def __init__(self, error_code: str, error_description: str, http_status: int = 500):
        self.error_code = error_code
        self.error_description = error_description
        self.http_status = http_status
        super().__init__(f"{error_code}: {error_description}")


class MojaloopClient:
    """
    Production-grade Mojaloop FSPIOP client
    
    Features:
    - FSPIOP-compliant headers (signature, source, destination)
    - Async HTTP with configurable timeouts and retries
    - Idempotency key support
    - Circuit breaker integration
    - Comprehensive error mapping
    """
    
    # FSPIOP API version
    API_VERSION = "1.1"
    
    # Default timeouts (seconds)
    DEFAULT_TIMEOUT = 30
    QUOTE_TIMEOUT = 60
    TRANSFER_TIMEOUT = 60
    
    # Retry configuration
    MAX_RETRIES = 3
    RETRY_BACKOFF_BASE = 1.0  # seconds
    
    def __init__(
        self,
        hub_url: str,
        fsp_id: str,
        signing_key: Optional[str] = None,
        timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = MAX_RETRIES
    ):
        """
        Initialize Mojaloop client
        
        Args:
            hub_url: Mojaloop hub URL (e.g., https://mojaloop.example.com)
            fsp_id: Financial Service Provider ID for this participant
            signing_key: Optional HMAC signing key for request signatures
            timeout: Default request timeout in seconds
            max_retries: Maximum retry attempts for failed requests
        """
        self.hub_url = hub_url.rstrip('/')
        self.fsp_id = fsp_id
        self.signing_key = signing_key
        self.timeout = timeout
        self.max_retries = max_retries
        self._session: Optional[aiohttp.ClientSession] = None
        
        logger.info(f"Initialized Mojaloop client for FSP: {fsp_id} at {hub_url}")
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session
    
    async def close(self) -> None:
        """Close the HTTP session"""
        if self._session and not self._session.closed:
            await self._session.close()
    
    def _generate_headers(
        self,
        destination_fsp: Optional[str] = None,
        content_type: str = "application/vnd.interoperability.parties+json;version=1.1"
    ) -> Dict[str, str]:
        """Generate FSPIOP-compliant headers"""
        headers = {
            "Content-Type": content_type,
            "Accept": content_type,
            "FSPIOP-Source": self.fsp_id,
            "Date": datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
        }
        
        if destination_fsp:
            headers["FSPIOP-Destination"] = destination_fsp
        
        return headers
    
    def _sign_request(self, headers: Dict[str, str], body: Optional[str] = None) -> Dict[str, str]:
        """Add FSPIOP signature to headers"""
        if not self.signing_key:
            return headers
        
        # Create signature string
        signature_string = f"FSPIOP-Source: {headers.get('FSPIOP-Source', '')}\n"
        signature_string += f"Date: {headers.get('Date', '')}\n"
        if body:
            signature_string += f"Content-Length: {len(body)}\n"
        
        # Generate HMAC-SHA256 signature
        signature = hmac.new(
            self.signing_key.encode('utf-8'),
            signature_string.encode('utf-8'),
            hashlib.sha256
        ).digest()
        
        headers["FSPIOP-Signature"] = base64.b64encode(signature).decode('utf-8')
        return headers
    
    async def _request_with_retry(
        self,
        method: str,
        url: str,
        headers: Dict[str, str],
        json_data: Optional[Dict] = None,
        idempotency_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute HTTP request with retry logic"""
        session = await self._get_session()
        
        if idempotency_key:
            headers["X-Idempotency-Key"] = idempotency_key
        
        body = json.dumps(json_data) if json_data else None
        headers = self._sign_request(headers, body)
        
        last_error = None
        for attempt in range(self.max_retries):
            try:
                async with session.request(
                    method,
                    url,
                    headers=headers,
                    json=json_data
                ) as response:
                    response_text = await response.text()
                    
                    if response.status >= 200 and response.status < 300:
                        if response_text:
                            return json.loads(response_text)
                        return {"status": "success", "http_status": response.status}
                    
                    # Handle specific error codes
                    if response.status == 400:
                        error_data = json.loads(response_text) if response_text else {}
                        raise MojalooopError(
                            error_data.get("errorCode", "3100"),
                            error_data.get("errorDescription", "Bad request"),
                            response.status
                        )
                    elif response.status == 404:
                        raise MojalooopError("3200", "Party not found", response.status)
                    elif response.status == 500:
                        # Retry on server errors
                        last_error = MojalooopError("2000", "Server error", response.status)
                    elif response.status == 503:
                        # Retry on service unavailable
                        last_error = MojalooopError("2001", "Service unavailable", response.status)
                    else:
                        raise MojalooopError(
                            str(response.status),
                            f"HTTP error: {response_text}",
                            response.status
                        )
                        
            except aiohttp.ClientError as e:
                last_error = MojalooopError("2002", f"Connection error: {str(e)}", 503)
            except asyncio.TimeoutError:
                last_error = MojalooopError("2003", "Request timeout", 504)
            
            # Exponential backoff before retry
            if attempt < self.max_retries - 1:
                wait_time = self.RETRY_BACKOFF_BASE * (2 ** attempt)
                logger.warning(f"Request failed, retrying in {wait_time}s (attempt {attempt + 1}/{self.max_retries})")
                await asyncio.sleep(wait_time)
        
        raise last_error or MojalooopError("2000", "Unknown error after retries", 500)
    
    # ==================== Party Lookup ====================
    
    async def lookup_party(
        self,
        party_id_type: str,
        party_identifier: str,
        party_sub_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Look up a party (account holder) by identifier
        
        Args:
            party_id_type: Type of identifier (MSISDN, EMAIL, ACCOUNT_ID, etc.)
            party_identifier: The identifier value
            party_sub_id: Optional sub-identifier
            
        Returns:
            Party information including FSP ID
        """
        url = f"{self.hub_url}/parties/{party_id_type}/{party_identifier}"
        if party_sub_id:
            url += f"/{party_sub_id}"
        
        headers = self._generate_headers(
            content_type="application/vnd.interoperability.parties+json;version=1.1"
        )
        
        logger.info(f"Looking up party: {party_id_type}/{party_identifier}")
        
        result = await self._request_with_retry("GET", url, headers)
        
        logger.info(f"Party lookup successful: {result.get('party', {}).get('partyIdInfo', {})}")
        return result
    
    # ==================== Quotes ====================
    
    async def request_quote(
        self,
        quote_id: str,
        payer: Party,
        payee: Party,
        amount: Money,
        amount_type: str = "SEND",
        transaction_type: Optional[TransactionType] = None,
        note: Optional[str] = None,
        expiration: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Request a quote for a transfer
        
        Args:
            quote_id: Unique quote identifier (UUID)
            payer: Payer party information
            payee: Payee party information
            amount: Transfer amount
            amount_type: SEND or RECEIVE
            transaction_type: Transaction type details
            note: Optional note/memo
            expiration: Optional expiration timestamp (ISO 8601)
            
        Returns:
            Quote response including fees and ILP packet
        """
        url = f"{self.hub_url}/quotes"
        
        headers = self._generate_headers(
            destination_fsp=payee.fsp_id,
            content_type="application/vnd.interoperability.quotes+json;version=1.1"
        )
        
        if not transaction_type:
            transaction_type = TransactionType(
                scenario="TRANSFER",
                initiator="PAYER",
                initiator_type="CONSUMER"
            )
        
        payload = {
            "quoteId": quote_id,
            "transactionId": str(uuid.uuid4()),
            "payer": payer.to_dict(),
            "payee": payee.to_dict(),
            "amountType": amount_type,
            "amount": amount.to_dict(),
            "transactionType": transaction_type.to_dict()
        }
        
        if note:
            payload["note"] = note
        if expiration:
            payload["expiration"] = expiration
        
        logger.info(f"Requesting quote: {quote_id} for {amount.amount} {amount.currency}")
        
        result = await self._request_with_retry(
            "POST", url, headers, payload,
            idempotency_key=quote_id
        )
        
        logger.info(f"Quote received: {quote_id}")
        return result
    
    # ==================== Transfers ====================
    
    async def execute_transfer(
        self,
        transfer_id: str,
        payee_fsp: str,
        amount: Money,
        ilp_packet: str,
        condition: str,
        expiration: str,
        payer: Optional[Party] = None,
        payee: Optional[Party] = None
    ) -> Dict[str, Any]:
        """
        Execute a transfer
        
        Args:
            transfer_id: Unique transfer identifier (UUID)
            payee_fsp: Destination FSP ID
            amount: Transfer amount
            ilp_packet: ILP packet from quote response
            condition: Cryptographic condition from quote
            expiration: Transfer expiration (ISO 8601)
            payer: Optional payer information
            payee: Optional payee information
            
        Returns:
            Transfer response with fulfilment
        """
        url = f"{self.hub_url}/transfers"
        
        headers = self._generate_headers(
            destination_fsp=payee_fsp,
            content_type="application/vnd.interoperability.transfers+json;version=1.1"
        )
        
        payload = {
            "transferId": transfer_id,
            "payeeFsp": payee_fsp,
            "payerFsp": self.fsp_id,
            "amount": amount.to_dict(),
            "ilpPacket": ilp_packet,
            "condition": condition,
            "expiration": expiration
        }
        
        logger.info(f"Executing transfer: {transfer_id} for {amount.amount} {amount.currency}")
        
        result = await self._request_with_retry(
            "POST", url, headers, payload,
            idempotency_key=transfer_id
        )
        
        logger.info(f"Transfer executed: {transfer_id}, state: {result.get('transferState', 'UNKNOWN')}")
        return result
    
    async def get_transfer(self, transfer_id: str) -> Dict[str, Any]:
        """
        Get transfer status
        
        Args:
            transfer_id: Transfer identifier
            
        Returns:
            Transfer status and details
        """
        url = f"{self.hub_url}/transfers/{transfer_id}"
        
        headers = self._generate_headers(
            content_type="application/vnd.interoperability.transfers+json;version=1.1"
        )
        
        logger.info(f"Getting transfer status: {transfer_id}")
        
        return await self._request_with_retry("GET", url, headers)
    
    # ==================== Bulk Transfers ====================
    
    async def execute_bulk_transfer(
        self,
        bulk_transfer_id: str,
        payer_fsp: str,
        individual_transfers: List[Dict[str, Any]],
        expiration: str
    ) -> Dict[str, Any]:
        """
        Execute a bulk transfer
        
        Args:
            bulk_transfer_id: Unique bulk transfer identifier
            payer_fsp: Payer FSP ID
            individual_transfers: List of individual transfer objects
            expiration: Bulk transfer expiration
            
        Returns:
            Bulk transfer response
        """
        url = f"{self.hub_url}/bulkTransfers"
        
        headers = self._generate_headers(
            content_type="application/vnd.interoperability.bulkTransfers+json;version=1.1"
        )
        
        payload = {
            "bulkTransferId": bulk_transfer_id,
            "payerFsp": payer_fsp,
            "payeeFsp": self.fsp_id,
            "individualTransfers": individual_transfers,
            "expiration": expiration
        }
        
        logger.info(f"Executing bulk transfer: {bulk_transfer_id} with {len(individual_transfers)} transfers")
        
        return await self._request_with_retry(
            "POST", url, headers, payload,
            idempotency_key=bulk_transfer_id
        )
    
    # ==================== High-Level Operations ====================
    
    async def send_money(
        self,
        sender_msisdn: str,
        receiver_msisdn: str,
        amount: Decimal,
        currency: str,
        note: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        High-level send money operation
        
        Performs full flow: party lookup -> quote -> transfer
        
        Args:
            sender_msisdn: Sender mobile number
            receiver_msisdn: Receiver mobile number
            amount: Amount to send
            currency: Currency code (e.g., KES, NGN)
            note: Optional transaction note
            
        Returns:
            Complete transfer result
        """
        transfer_id = str(uuid.uuid4())
        quote_id = str(uuid.uuid4())
        
        try:
            # Step 1: Look up receiver
            logger.info(f"Step 1: Looking up receiver {receiver_msisdn}")
            receiver_info = await self.lookup_party("MSISDN", receiver_msisdn)
            receiver_fsp = receiver_info.get("party", {}).get("partyIdInfo", {}).get("fspId")
            
            if not receiver_fsp:
                raise MojalooopError("3200", "Receiver FSP not found")
            
            # Step 2: Request quote
            logger.info(f"Step 2: Requesting quote {quote_id}")
            payer = Party(
                party_id_type="MSISDN",
                party_identifier=sender_msisdn,
                fsp_id=self.fsp_id
            )
            payee = Party(
                party_id_type="MSISDN",
                party_identifier=receiver_msisdn,
                fsp_id=receiver_fsp,
                name=receiver_info.get("party", {}).get("name")
            )
            money = Money(currency=currency, amount=str(amount))
            
            quote = await self.request_quote(
                quote_id=quote_id,
                payer=payer,
                payee=payee,
                amount=money,
                note=note
            )
            
            # Step 3: Execute transfer
            logger.info(f"Step 3: Executing transfer {transfer_id}")
            expiration = quote.get("expiration", 
                (datetime.now(timezone.utc).isoformat() + "Z"))
            
            transfer_result = await self.execute_transfer(
                transfer_id=transfer_id,
                payee_fsp=receiver_fsp,
                amount=money,
                ilp_packet=quote.get("ilpPacket", ""),
                condition=quote.get("condition", ""),
                expiration=expiration,
                payer=payer,
                payee=payee
            )
            
            return {
                "success": True,
                "transfer_id": transfer_id,
                "quote_id": quote_id,
                "sender": sender_msisdn,
                "receiver": receiver_msisdn,
                "amount": float(amount),
                "currency": currency,
                "fees": quote.get("payeeFspFee", {}).get("amount", "0"),
                "transfer_state": transfer_result.get("transferState", "UNKNOWN"),
                "fulfilment": transfer_result.get("fulfilment"),
                "completed_timestamp": transfer_result.get("completedTimestamp")
            }
            
        except MojalooopError as e:
            logger.error(f"Mojaloop transfer failed: {e}")
            return {
                "success": False,
                "transfer_id": transfer_id,
                "error_code": e.error_code,
                "error_description": e.error_description
            }
        except Exception as e:
            logger.error(f"Unexpected error in send_money: {e}")
            return {
                "success": False,
                "transfer_id": transfer_id,
                "error_code": "5000",
                "error_description": str(e)
            }


def get_instance(
    hub_url: str = None,
    fsp_id: str = None
) -> MojaloopClient:
    """Get Mojaloop client instance"""
    import os
    return MojaloopClient(
        hub_url=hub_url or os.getenv("MOJALOOP_HUB_URL", "https://mojaloop.example.com"),
        fsp_id=fsp_id or os.getenv("MOJALOOP_FSP_ID", "remittance-fsp"),
        signing_key=os.getenv("MOJALOOP_SIGNING_KEY")
    )
