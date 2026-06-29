"""
Mojaloop-NIBSS Bridge Connector
Connects Mojaloop payment hub with CBN NIBSS infrastructure

This bridge enables:
- Mojaloop participants to send/receive payments via NIBSS NIP
- Cross-border payments to settle in Nigerian banks via NIBSS
- High-value transfers via NIBSS RTGS
- BVN verification for compliance
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from enum import Enum

from nibss_service import (
    NIBSSClient,
    NIBSSAccount,
    NIPTransaction,
    RTGSTransaction,
    NIBSSProduct,
    NIBSSTransactionType,
    NIBSSBankDirectory,
    NIBSSResponseCode,
)


logger = logging.getLogger(__name__)


class MojaloopNIBSSBridge:
    """
    Bridge between Mojaloop and NIBSS
    
    Translates Mojaloop payment requests to NIBSS format and vice versa
    """
    
    def __init__(
        self,
        nibss_client: NIBSSClient,
        mojaloop_participant_id: str,
        default_bank_code: str,
        default_account_number: str
    ) -> None:
        self.nibss_client = nibss_client
        self.mojaloop_participant_id = mojaloop_participant_id
        self.default_bank_code = default_bank_code
        self.default_account_number = default_account_number
        
        # Transaction mapping (Mojaloop ID -> NIBSS Session ID)
        self.transaction_mapping: Dict[str, str] = {}
    
    async def process_mojaloop_quote(
        self,
        quote_request: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process Mojaloop quote request
        
        Args:
            quote_request: Mojaloop quote request
            
        Returns:
            Quote response with fees and exchange rate
        """
        try:
            # Extract Mojaloop quote details
            payer_fsp = quote_request.get("payer", {}).get("partyIdInfo", {})
            payee_fsp = quote_request.get("payee", {}).get("partyIdInfo", {})
            amount_type = quote_request.get("amountType", "SEND")
            amount = float(quote_request.get("amount", {}).get("amount", 0))
            currency = quote_request.get("amount", {}).get("currency", "NGN")
            
            # Parse NIBSS account from Mojaloop party identifier
            payee_account = self._parse_party_identifier(payee_fsp)
            
            if not payee_account:
                return {
                    "success": False,
                    "error": "Invalid payee account format",
                }
            
            # Perform name enquiry to verify account
            name_enquiry = await self.nibss_client.name_enquiry(
                account_number=payee_account["account_number"],
                bank_code=payee_account["bank_code"]
            )
            
            if not name_enquiry["success"]:
                return {
                    "success": False,
                    "error": f"Account verification failed: {name_enquiry.get('error')}",
                }
            
            # Calculate fees based on amount and product
            fees = self._calculate_nibss_fees(amount, NIBSSProduct.NIP)
            
            # Create quote response
            quote_response = {
                "success": True,
                "quote_id": quote_request.get("quoteId"),
                "transfer_amount": {
                    "amount": str(amount),
                    "currency": currency,
                },
                "payee_receive_amount": {
                    "amount": str(amount),
                    "currency": currency,
                },
                "fees": {
                    "amount": str(fees),
                    "currency": currency,
                },
                "total_amount": {
                    "amount": str(amount + fees),
                    "currency": currency,
                },
                "payee_name": name_enquiry["account_name"],
                "nibss_session_id": name_enquiry["session_id"],
                "expiration": self._get_expiration_time(minutes=5),
            }
            
            # Store mapping
            self.transaction_mapping[quote_request.get("quoteId")] = name_enquiry["session_id"]
            
            return quote_response
        
        except Exception as e:
            logger.error(f"Quote processing error: {e}")
            return {
                "success": False,
                "error": str(e),
            }
    
    async def process_mojaloop_transfer(
        self,
        transfer_request: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process Mojaloop transfer request and execute via NIBSS
        
        Args:
            transfer_request: Mojaloop transfer request
            
        Returns:
            Transfer response with NIBSS reference
        """
        try:
            # Extract transfer details
            transfer_id = transfer_request.get("transferId")
            quote_id = transfer_request.get("quoteId")
            payer_fsp = transfer_request.get("payerFsp")
            payee_fsp = transfer_request.get("payeeFsp")
            amount = float(transfer_request.get("amount", {}).get("amount", 0))
            currency = transfer_request.get("amount", {}).get("currency", "NGN")
            
            # Get NIBSS session ID from quote
            nibss_session_id = self.transaction_mapping.get(quote_id)
            
            if not nibss_session_id:
                return {
                    "success": False,
                    "error": "Quote not found or expired",
                }
            
            # Parse accounts
            payer_account_info = self._get_payer_account(payer_fsp)
            payee_account_info = self._parse_party_identifier(
                transfer_request.get("payee", {}).get("partyIdInfo", {})
            )
            
            # Create NIBSS accounts
            source_account = NIBSSAccount(
                account_number=payer_account_info["account_number"],
                bank_code=payer_account_info["bank_code"],
                account_name=payer_account_info["account_name"],
                bvn=payer_account_info.get("bvn")
            )
            
            destination_account = NIBSSAccount(
                account_number=payee_account_info["account_number"],
                bank_code=payee_account_info["bank_code"],
                account_name=payee_account_info.get("account_name", ""),
            )
            
            # Determine NIBSS product based on amount
            if amount >= 10_000_000:  # 10 million NGN
                # Use RTGS for high-value transfers
                rtgs_transaction = RTGSTransaction(
                    transaction_id=transfer_id,
                    settlement_date=datetime.utcnow().strftime("%Y-%m-%d"),
                    source_account=source_account,
                    destination_account=destination_account,
                    amount=amount,
                    currency=currency,
                    narration=transfer_request.get("ilpPacket", {}).get("data", {}).get("note", "")[:140]
                )
                
                result = await self.nibss_client.send_rtgs_transaction(rtgs_transaction)
                
                if result["success"]:
                    return {
                        "success": True,
                        "transfer_id": transfer_id,
                        "transfer_state": "COMMITTED",
                        "nibss_product": "RTGS",
                        "nibss_reference": result["rtgs_reference"],
                        "settlement_date": result["settlement_date"],
                        "completion_time": result["timestamp"],
                    }
                else:
                    return {
                        "success": False,
                        "transfer_id": transfer_id,
                        "transfer_state": "ABORTED",
                        "error": result.get("error"),
                        "response_code": result.get("response_code"),
                    }
            
            else:
                # Use NIP for regular transfers
                nip_transaction = NIPTransaction(
                    transaction_id=transfer_id,
                    session_id=nibss_session_id,
                    source_account=source_account,
                    destination_account=destination_account,
                    amount=amount,
                    currency=currency,
                    narration=transfer_request.get("ilpPacket", {}).get("data", {}).get("note", "")[:30],
                    payment_reference=transfer_id,
                    transaction_type=NIBSSTransactionType.CREDIT
                )
                
                result = await self.nibss_client.send_nip_transaction(nip_transaction)
                
                if result["success"]:
                    return {
                        "success": True,
                        "transfer_id": transfer_id,
                        "transfer_state": "COMMITTED",
                        "nibss_product": "NIP",
                        "nibss_reference": result["nibss_reference"],
                        "completion_time": result["timestamp"],
                    }
                elif result.get("pending"):
                    return {
                        "success": False,
                        "transfer_id": transfer_id,
                        "transfer_state": "RESERVED",
                        "pending": True,
                        "nibss_reference": nibss_session_id,
                    }
                else:
                    return {
                        "success": False,
                        "transfer_id": transfer_id,
                        "transfer_state": "ABORTED",
                        "error": result.get("error"),
                        "response_code": result.get("response_code"),
                    }
        
        except Exception as e:
            logger.error(f"Transfer processing error: {e}")
            return {
                "success": False,
                "transfer_id": transfer_request.get("transferId"),
                "transfer_state": "ABORTED",
                "error": str(e),
            }
    
    async def query_transfer_status(
        self,
        transfer_id: str
    ) -> Dict[str, Any]:
        """
        Query transfer status from NIBSS
        
        Args:
            transfer_id: Mojaloop transfer ID
            
        Returns:
            Transfer status
        """
        # Get NIBSS session ID
        nibss_session_id = None
        for mojaloop_id, session_id in self.transaction_mapping.items():
            if transfer_id in mojaloop_id:
                nibss_session_id = session_id
                break
        
        if not nibss_session_id:
            return {
                "success": False,
                "error": "Transfer not found",
            }
        
        # Query NIBSS
        result = await self.nibss_client.query_transaction_status(nibss_session_id)
        
        # Map NIBSS status to Mojaloop state
        nibss_status = result.get("status", "")
        response_code = result.get("response_code", "")
        
        if response_code == NIBSSResponseCode.SUCCESS.value:
            transfer_state = "COMMITTED"
        elif response_code == NIBSSResponseCode.PENDING.value:
            transfer_state = "RESERVED"
        else:
            transfer_state = "ABORTED"
        
        return {
            "success": True,
            "transfer_id": transfer_id,
            "transfer_state": transfer_state,
            "nibss_status": nibss_status,
            "response_code": response_code,
            "timestamp": result.get("timestamp"),
        }
    
    async def verify_participant_bvn(
        self,
        participant_id: str,
        bvn: str,
        account_number: str,
        bank_code: str
    ) -> Dict[str, Any]:
        """
        Verify participant BVN for compliance
        
        Args:
            participant_id: Mojaloop participant ID
            bvn: Bank Verification Number
            account_number: Account number
            bank_code: Bank code
            
        Returns:
            BVN verification result
        """
        result = await self.nibss_client.verify_bvn(
            bvn=bvn,
            account_number=account_number,
            bank_code=bank_code
        )
        
        if result["success"] and result["verified"]:
            return {
                "success": True,
                "participant_id": participant_id,
                "bvn_verified": True,
                "customer_name": result["customer_name"],
                "date_of_birth": result.get("date_of_birth"),
                "phone_number": result.get("phone_number"),
            }
        else:
            return {
                "success": False,
                "participant_id": participant_id,
                "bvn_verified": False,
                "error": result.get("error"),
            }
    
    def _parse_party_identifier(
        self,
        party_info: Dict[str, Any]
    ) -> Optional[Dict[str, str]]:
        """
        Parse Mojaloop party identifier to extract NIBSS account details
        
        Expected format: "ACCOUNT_NUMBER@BANK_CODE" or "MSISDN"
        
        Args:
            party_info: Mojaloop party information
            
        Returns:
            Parsed account details
        """
        party_id_type = party_info.get("partyIdType")
        party_identifier = party_info.get("partyIdentifier", "")
        
        if party_id_type == "ACCOUNT_ID":
            # Format: "0123456789@057" (account@bank_code)
            if "@" in party_identifier:
                account_number, bank_code = party_identifier.split("@")
                return {
                    "account_number": account_number,
                    "bank_code": bank_code,
                }
        
        elif party_id_type == "MSISDN":
            # For MSISDN, would need to lookup account via wallet/mobile money
            # This is a placeholder - actual implementation would query a registry
            logger.warning(f"MSISDN lookup not implemented: {party_identifier}")
            return None
        
        return None
    
    def _get_payer_account(self, payer_fsp: str) -> Dict[str, str]:
        """
        Get payer account details from FSP
        
        Args:
            payer_fsp: Payer FSP identifier
            
        Returns:
            Payer account details
        """
        # In production, this would lookup the payer's account from database
        # For now, return default account
        return {
            "account_number": self.default_account_number,
            "bank_code": self.default_bank_code,
            "account_name": f"{payer_fsp} Settlement Account",
            "bvn": None,
        }
    
    def _calculate_nibss_fees(
        self,
        amount: float,
        product: NIBSSProduct
    ) -> float:
        """
        Calculate NIBSS transaction fees
        
        Args:
            amount: Transaction amount
            product: NIBSS product
            
        Returns:
            Fee amount
        """
        if product == NIBSSProduct.NIP:
            # NIP fees (as of 2025)
            if amount <= 5000:
                return 10.00
            elif amount <= 50000:
                return 25.00
            else:
                return 50.00
        
        elif product == NIBSSProduct.RTGS:
            # RTGS fees (flat fee)
            return 500.00
        
        else:
            return 0.00
    
    def _get_expiration_time(self, minutes: int = 5) -> str:
        """
        Get expiration time for quote
        
        Args:
            minutes: Minutes until expiration
            
        Returns:
            ISO 8601 timestamp
        """
        from datetime import timedelta
        expiration = datetime.utcnow() + timedelta(minutes=minutes)
        return expiration.isoformat() + "Z"


class NIBSSWebhookHandler:
    """
    Handle NIBSS webhooks for transaction notifications
    
    NIBSS sends webhooks for:
    - Transaction completion
    - Transaction failure
    - Reversal notifications
    - Settlement notifications
    """
    
    def __init__(self, bridge: MojaloopNIBSSBridge) -> None:
        self.bridge = bridge
    
    async def handle_transaction_notification(
        self,
        webhook_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle NIBSS transaction notification webhook
        
        Args:
            webhook_data: NIBSS webhook payload
            
        Returns:
            Processing result
        """
        try:
            session_id = webhook_data.get("SessionID")
            response_code = webhook_data.get("ResponseCode")
            transaction_status = webhook_data.get("TransactionStatus")
            
            logger.info(f"NIBSS webhook received: {session_id}, status: {transaction_status}")
            
            # Find corresponding Mojaloop transfer
            mojaloop_transfer_id = None
            for transfer_id, nibss_session in self.bridge.transaction_mapping.items():
                if nibss_session == session_id:
                    mojaloop_transfer_id = transfer_id
                    break
            
            if not mojaloop_transfer_id:
                logger.warning(f"No Mojaloop transfer found for NIBSS session: {session_id}")
                return {
                    "success": False,
                    "error": "Transfer not found",
                }
            
            # Process based on status
            if response_code == NIBSSResponseCode.SUCCESS.value:
                # Transaction successful - notify Mojaloop
                logger.info(f"NIBSS transaction successful: {session_id}")
                
                # Here you would call Mojaloop API to update transfer state
                # await mojaloop_client.fulfill_transfer(mojaloop_transfer_id)
                
                return {
                    "success": True,
                    "transfer_id": mojaloop_transfer_id,
                    "action": "COMMITTED",
                }
            
            else:
                # Transaction failed - notify Mojaloop
                logger.error(f"NIBSS transaction failed: {session_id}, code: {response_code}")
                
                # Here you would call Mojaloop API to abort transfer
                # await mojaloop_client.abort_transfer(mojaloop_transfer_id)
                
                return {
                    "success": True,
                    "transfer_id": mojaloop_transfer_id,
                    "action": "ABORTED",
                    "error_code": response_code,
                }
        
        except Exception as e:
            logger.error(f"Webhook handling error: {e}")
            return {
                "success": False,
                "error": str(e),
            }
    
    async def handle_reversal_notification(
        self,
        webhook_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle NIBSS reversal notification
        
        Args:
            webhook_data: NIBSS reversal webhook payload
            
        Returns:
            Processing result
        """
        try:
            original_session_id = webhook_data.get("OriginalSessionID")
            reversal_reason = webhook_data.get("ReversalReason")
            
            logger.warning(f"NIBSS reversal received: {original_session_id}, reason: {reversal_reason}")
            
            # Find corresponding Mojaloop transfer
            mojaloop_transfer_id = None
            for transfer_id, nibss_session in self.bridge.transaction_mapping.items():
                if nibss_session == original_session_id:
                    mojaloop_transfer_id = transfer_id
                    break
            
            if mojaloop_transfer_id:
                # Here you would initiate Mojaloop reversal
                # await mojaloop_client.reverse_transfer(mojaloop_transfer_id, reversal_reason)
                
                return {
                    "success": True,
                    "transfer_id": mojaloop_transfer_id,
                    "action": "REVERSED",
                    "reason": reversal_reason,
                }
            
            return {
                "success": False,
                "error": "Transfer not found",
            }
        
        except Exception as e:
            logger.error(f"Reversal handling error: {e}")
            return {
                "success": False,
                "error": str(e),
            }


# Example usage
async def example_bridge_usage() -> None:
    """Example usage of Mojaloop-NIBSS bridge"""
    
    # Initialize NIBSS client
    async with NIBSSClient(
        base_url="https://api.nibss-plc.com.ng",
        institution_code="ABC",
        api_key="your-api-key",
        secret_key="your-secret-key"
    ) as nibss_client:
        
        # Initialize bridge
        bridge = MojaloopNIBSSBridge(
            nibss_client=nibss_client,
            mojaloop_participant_id="mojaloop-hub",
            default_bank_code="044",  # Access Bank
            default_account_number="1234567890"
        )
        
        # 1. Process Mojaloop quote
        quote_request = {
            "quoteId": str(uuid.uuid4()),
            "transactionId": str(uuid.uuid4()),
            "payer": {
                "partyIdInfo": {
                    "partyIdType": "MSISDN",
                    "partyIdentifier": "+2348012345678"
                }
            },
            "payee": {
                "partyIdInfo": {
                    "partyIdType": "ACCOUNT_ID",
                    "partyIdentifier": "0123456789@057"  # Account@BankCode
                }
            },
            "amountType": "SEND",
            "amount": {
                "amount": "50000",
                "currency": "NGN"
            }
        }
        
        quote_response = await bridge.process_mojaloop_quote(quote_request)
        
        if quote_response["success"]:
            print(f"Quote created: {quote_response['quote_id']}")
            print(f"Payee: {quote_response['payee_name']}")
            print(f"Fees: {quote_response['fees']['amount']} {quote_response['fees']['currency']}")
            
            # 2. Process Mojaloop transfer
            transfer_request = {
                "transferId": str(uuid.uuid4()),
                "quoteId": quote_response["quote_id"],
                "payerFsp": "mojaloop-hub",
                "payeeFsp": "nibss-nigeria",
                "amount": {
                    "amount": "50000",
                    "currency": "NGN"
                },
                "payee": {
                    "partyIdInfo": {
                        "partyIdType": "ACCOUNT_ID",
                        "partyIdentifier": "0123456789@057"
                    }
                },
                "ilpPacket": {
                    "data": {
                        "note": "Payment for services"
                    }
                }
            }
            
            transfer_response = await bridge.process_mojaloop_transfer(transfer_request)
            
            if transfer_response["success"]:
                print(f"Transfer successful: {transfer_response['transfer_id']}")
                print(f"NIBSS Product: {transfer_response['nibss_product']}")
                print(f"NIBSS Reference: {transfer_response['nibss_reference']}")
            else:
                print(f"Transfer failed: {transfer_response.get('error')}")


if __name__ == "__main__":
    asyncio.run(example_bridge_usage())

