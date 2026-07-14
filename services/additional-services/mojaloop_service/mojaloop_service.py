"""
Mojaloop Integration Service
Open-source interoperability layer for financial services
"""

from typing import Dict, List, Optional, Any
import httpx
import uuid
import hashlib
import base64
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass
import logging
import json

logger = logging.getLogger(__name__)


class PartyIdType(Enum):
    """Party identifier types"""
    MSISDN = "MSISDN"  # Mobile phone number
    EMAIL = "EMAIL"
    IBAN = "IBAN"
    ACCOUNT_ID = "ACCOUNT_ID"


class TransactionScenario(Enum):
    """Transaction scenarios"""
    TRANSFER = "TRANSFER"
    DEPOSIT = "DEPOSIT"
    WITHDRAWAL = "WITHDRAWAL"
    REFUND = "REFUND"


class TransferState(Enum):
    """Transfer states"""
    RECEIVED = "RECEIVED"
    RESERVED = "RESERVED"
    COMMITTED = "COMMITTED"
    ABORTED = "ABORTED"


@dataclass
class PartyInfo:
    """Party information from lookup"""
    party_id_type: str
    party_identifier: str
    fsp_id: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: Optional[str] = None


@dataclass
class QuoteResponse:
    """Quote response from Mojaloop"""
    quote_id: str
    transaction_id: str
    transfer_amount: int
    transfer_currency: str
    payee_receive_amount: int
    payee_receive_currency: str
    payee_fsp_fee: int
    payee_fsp_commission: int
    expiration: str
    ilp_packet: str
    condition: str


@dataclass
class TransferResponse:
    """Transfer response from Mojaloop"""
    transfer_id: str
    transfer_state: TransferState
    fulfilment: Optional[str] = None
    completed_timestamp: Optional[str] = None
    error_code: Optional[str] = None
    error_description: Optional[str] = None


class MojaloupService:
    """
    Mojaloop integration service for interoperable payments
    
    Features:
    - Party lookup (discovery)
    - Quote requests (pricing)
    - Transfer initiation (execution)
    - Transfer callbacks (notifications)
    - Settlement integration
    """
    
    def __init__(
        self,
        base_url: str,
        participant_id: str,
        private_key: str,
        timeout: int = 30
    ):
        """
        Initialize Mojaloop client
        
        Args:
            base_url: Mojaloop switch base URL
            participant_id: Our participant ID (FSP ID)
            private_key: Private key for signing
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.participant_id = participant_id
        self.private_key = private_key
        
        self.client = httpx.AsyncClient(timeout=timeout)
        
        # Cache for party lookups
        self.party_cache: Dict[str, PartyInfo] = {}
        
        # Pending transfers
        self.pending_transfers: Dict[str, QuoteResponse] = {}
        
        logger.info(f"Mojaloop service initialized: participant={participant_id}")
    
    # ==================== Party Lookup ====================
    
    async def lookup_party(
        self,
        party_id_type: PartyIdType,
        party_identifier: str,
        use_cache: bool = True
    ) -> Optional[PartyInfo]:
        """
        Lookup party information
        
        Args:
            party_id_type: Type of identifier (MSISDN, EMAIL, etc.)
            party_identifier: Party identifier value
            use_cache: Use cached result if available
        
        Returns:
            PartyInfo or None if not found
        """
        cache_key = f"{party_id_type.value}:{party_identifier}"
        
        # Check cache
        if use_cache and cache_key in self.party_cache:
            logger.info(f"Party lookup (cached): {cache_key}")
            return self.party_cache[cache_key]
        
        # Make API request
        url = f"{self.base_url}/parties/{party_id_type.value}/{party_identifier}"
        headers = self._get_headers()
        
        try:
            response = await self.client.get(url, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            party_data = data.get("party", {})
            party_id_info = party_data.get("partyIdInfo", {})
            personal_info = party_data.get("personalInfo", {})
            complex_name = personal_info.get("complexName", {})
            
            party_info = PartyInfo(
                party_id_type=party_id_info.get("partyIdType"),
                party_identifier=party_id_info.get("partyIdentifier"),
                fsp_id=party_id_info.get("fspId"),
                first_name=complex_name.get("firstName"),
                last_name=complex_name.get("lastName")
            )
            
            # Build full name
            if party_info.first_name and party_info.last_name:
                party_info.full_name = f"{party_info.first_name} {party_info.last_name}"
            
            # Cache result
            self.party_cache[cache_key] = party_info
            
            logger.info(
                f"Party lookup successful: {cache_key} -> "
                f"{party_info.full_name} @ {party_info.fsp_id}"
            )
            
            return party_info
        
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"Party not found: {cache_key}")
                return None
            else:
                logger.error(f"Party lookup failed: {e}")
                raise
        except Exception as e:
            logger.error(f"Party lookup error: {e}")
            raise
    
    # ==================== Quote Request ====================
    
    async def request_quote(
        self,
        payer_id: str,
        payer_id_type: PartyIdType,
        payee_id: str,
        payee_id_type: PartyIdType,
        amount: int,
        currency: str,
        amount_type: str = "SEND",
        scenario: TransactionScenario = TransactionScenario.TRANSFER
    ) -> QuoteResponse:
        """
        Request quote for transfer
        
        Args:
            payer_id: Payer identifier
            payer_id_type: Payer identifier type
            payee_id: Payee identifier
            payee_id_type: Payee identifier type
            amount: Amount in smallest currency unit (cents)
            currency: Currency code
            amount_type: "SEND" or "RECEIVE"
            scenario: Transaction scenario
        
        Returns:
            QuoteResponse
        """
        quote_id = str(uuid.uuid4())
        transaction_id = str(uuid.uuid4())
        
        payload = {
            "quoteId": quote_id,
            "transactionId": transaction_id,
            "payer": {
                "partyIdInfo": {
                    "partyIdType": payer_id_type.value,
                    "partyIdentifier": payer_id,
                    "fspId": self.participant_id
                }
            },
            "payee": {
                "partyIdInfo": {
                    "partyIdType": payee_id_type.value,
                    "partyIdentifier": payee_id
                }
            },
            "amountType": amount_type,
            "amount": {
                "currency": currency,
                "amount": str(amount)
            },
            "transactionType": {
                "scenario": scenario.value,
                "initiator": "PAYER",
                "initiatorType": "CONSUMER"
            }
        }
        
        url = f"{self.base_url}/quotes"
        headers = self._get_headers()
        
        try:
            response = await self.client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            
            quote_response = QuoteResponse(
                quote_id=quote_id,
                transaction_id=transaction_id,
                transfer_amount=int(data["transferAmount"]["amount"]),
                transfer_currency=data["transferAmount"]["currency"],
                payee_receive_amount=int(data.get("payeeReceiveAmount", {}).get("amount", 0)),
                payee_receive_currency=data.get("payeeReceiveAmount", {}).get("currency", currency),
                payee_fsp_fee=int(data.get("payeeFspFee", {}).get("amount", 0)),
                payee_fsp_commission=int(data.get("payeeFspCommission", {}).get("amount", 0)),
                expiration=data["expiration"],
                ilp_packet=data["ilpPacket"],
                condition=data["condition"]
            )
            
            # Store for later use
            self.pending_transfers[transaction_id] = quote_response
            
            logger.info(
                f"Quote created: id={quote_id}, amount={amount} {currency}, "
                f"fee={quote_response.payee_fsp_fee}"
            )
            
            return quote_response
        
        except Exception as e:
            logger.error(f"Quote request failed: {e}")
            raise
    
    # ==================== Transfer Initiation ====================
    
    async def initiate_transfer(
        self,
        transaction_id: str,
        payee_fsp_id: str
    ) -> str:
        """
        Initiate transfer based on quote
        
        Args:
            transaction_id: Transaction ID from quote
            payee_fsp_id: Payee FSP ID
        
        Returns:
            Transfer ID
        """
        # Get quote data
        quote = self.pending_transfers.get(transaction_id)
        if quote is None:
            raise ValueError(f"Quote not found: {transaction_id}")
        
        # Check if quote expired
        expiration = datetime.fromisoformat(quote.expiration.rstrip('Z'))
        if datetime.utcnow() > expiration:
            raise ValueError(f"Quote expired: {transaction_id}")
        
        payload = {
            "transferId": transaction_id,
            "payerFsp": self.participant_id,
            "payeeFsp": payee_fsp_id,
            "amount": {
                "currency": quote.transfer_currency,
                "amount": str(quote.transfer_amount)
            },
            "ilpPacket": quote.ilp_packet,
            "condition": quote.condition,
            "expiration": quote.expiration
        }
        
        url = f"{self.base_url}/transfers"
        headers = self._get_headers()
        
        try:
            response = await self.client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            
            logger.info(f"Transfer initiated: id={transaction_id}")
            
            return transaction_id
        
        except Exception as e:
            logger.error(f"Transfer initiation failed: {e}")
            raise
    
    # ==================== Transfer Callbacks ====================
    
    async def handle_transfer_callback(
        self,
        transfer_id: str,
        callback_data: Dict[str, Any]
    ) -> TransferResponse:
        """
        Handle transfer completion callback from Mojaloop
        
        Args:
            transfer_id: Transfer ID
            callback_data: Callback payload
        
        Returns:
            TransferResponse
        """
        transfer_state = TransferState(callback_data.get("transferState", "RECEIVED"))
        
        response = TransferResponse(
            transfer_id=transfer_id,
            transfer_state=transfer_state,
            fulfilment=callback_data.get("fulfilment"),
            completed_timestamp=callback_data.get("completedTimestamp"),
            error_code=callback_data.get("errorCode"),
            error_description=callback_data.get("errorDescription")
        )
        
        # Remove from pending
        if transfer_id in self.pending_transfers:
            del self.pending_transfers[transfer_id]
        
        logger.info(
            f"Transfer callback: id={transfer_id}, state={transfer_state.value}"
        )
        
        return response
    
    # ==================== Bulk Operations ====================
    
    async def bulk_quote(
        self,
        payer_id: str,
        payer_id_type: PartyIdType,
        transfers: List[Dict[str, Any]],
        currency: str
    ) -> List[QuoteResponse]:
        """
        Request quotes for multiple transfers
        
        Args:
            payer_id: Payer identifier
            payer_id_type: Payer identifier type
            transfers: List of transfer dicts with payee_id and amount
            currency: Currency code
        
        Returns:
            List of QuoteResponse
        """
        quotes = []
        
        for transfer in transfers:
            try:
                quote = await self.request_quote(
                    payer_id=payer_id,
                    payer_id_type=payer_id_type,
                    payee_id=transfer["payee_id"],
                    payee_id_type=PartyIdType(transfer.get("payee_id_type", "MSISDN")),
                    amount=transfer["amount"],
                    currency=currency
                )
                quotes.append(quote)
            except Exception as e:
                logger.error(
                    f"Bulk quote failed for {transfer['payee_id']}: {e}"
                )
                # Continue with other transfers
        
        logger.info(f"Bulk quote completed: {len(quotes)}/{len(transfers)} successful")
        
        return quotes
    
    async def bulk_transfer(
        self,
        transaction_ids: List[str],
        payee_fsp_ids: List[str]
    ) -> List[str]:
        """
        Initiate multiple transfers
        
        Args:
            transaction_ids: List of transaction IDs
            payee_fsp_ids: List of corresponding payee FSP IDs
        
        Returns:
            List of successful transfer IDs
        """
        successful = []
        
        for transaction_id, payee_fsp_id in zip(transaction_ids, payee_fsp_ids):
            try:
                await self.initiate_transfer(transaction_id, payee_fsp_id)
                successful.append(transaction_id)
            except Exception as e:
                logger.error(
                    f"Bulk transfer failed for {transaction_id}: {e}"
                )
                # Continue with other transfers
        
        logger.info(
            f"Bulk transfer completed: {len(successful)}/{len(transaction_ids)} successful"
        )
        
        return successful
    
    # ==================== Settlement ====================
    
    async def get_settlement_report(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, int]:
        """
        Get settlement report from Mojaloop
        
        Args:
            start_time: Start time or None for last settlement
            end_time: End time or None for now
        
        Returns:
            Dictionary of participant -> net position
        """
        # In production, call Mojaloop settlement API
        # url = f"{self.base_url}/settlements"
        # params = {}
        # if start_time:
        #     params["startTime"] = start_time.isoformat()
        # if end_time:
        #     params["endTime"] = end_time.isoformat()
        # 
        # response = await self.client.get(url, params=params, headers=self._get_headers())
        # data = response.json()
        # 
        # net_positions = {}
        # for participant in data["participants"]:
        #     net_positions[participant["id"]] = participant["netPosition"]
        # 
        # return net_positions
        
        # Mock implementation
        return {
            self.participant_id: -50000,  # Net sender
            "bank-a": 30000,  # Net receiver
            "mobile-money": 20000  # Net receiver
        }
    
    # ==================== Helper Methods ====================
    
    def _get_headers(self, destination: Optional[str] = None) -> Dict[str, str]:
        """Generate FSPIOP headers"""
        headers = {
            "Content-Type": "application/vnd.interoperability.transfers+json;version=1.0",
            "Accept": "application/vnd.interoperability.transfers+json;version=1.0",
            "FSPIOP-Source": self.participant_id,
            "Date": datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")
        }
        
        if destination:
            headers["FSPIOP-Destination"] = destination
        
        return headers
    
    def _generate_ilp(self, quote_data: Dict[str, Any]) -> tuple[str, str]:
        """
        Generate ILP packet and condition
        
        Args:
            quote_data: Quote data
        
        Returns:
            (ilp_packet, condition) tuple
        """
        # Simplified ILP generation
        # In production, use proper ILP library
        
        packet_data = {
            "amount": quote_data["amount"],
            "account": quote_data.get("payee", {}).get("partyIdInfo", {}).get("partyIdentifier")
        }
        
        packet = base64.b64encode(json.dumps(packet_data).encode()).decode()
        
        # Generate condition (SHA-256 hash of fulfilment)
        fulfilment = str(uuid.uuid4())
        condition = hashlib.sha256(fulfilment.encode()).digest()
        condition_b64 = base64.b64encode(condition).decode()
        
        return packet, condition_b64
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()


# ==================== Singleton Instance ====================

_mojaloop_service: Optional[MojaloupService] = None


def get_mojaloop_service() -> MojaloupService:
    """Get singleton Mojaloop service instance"""
    global _mojaloop_service
    
    if _mojaloop_service is None:
        # In production, read from environment
        base_url = "https://mojaloop-switch.example.com"
        participant_id = "remittance-platform"
        private_key = "..."  # Load from secure storage
        
        _mojaloop_service = MojaloupService(
            base_url=base_url,
            participant_id=participant_id,
            private_key=private_key
        )
    
    return _mojaloop_service
