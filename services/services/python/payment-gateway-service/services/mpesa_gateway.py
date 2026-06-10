"""
M-Pesa Gateway Integration (Safaricom Kenya)
Supports STK Push, B2C, B2B, C2B, and Account Balance
"""

import base64
from datetime import datetime
from typing import Dict, Optional
import httpx


class MPesaGateway:
    """M-Pesa payment gateway implementation"""
    
    def __init__(
        self,
        consumer_key: str,
        consumer_secret: str,
        business_short_code: str,
        passkey: str,
        environment: str = "sandbox"
    ):
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.business_short_code = business_short_code
        self.passkey = passkey
        
        if environment == "production":
            self.base_url = "https://api.safaricom.co.ke"
        else:
            self.base_url = "https://sandbox.safaricom.co.ke"
        
        self.access_token = None
        self.token_expiry = None
    
    async def _get_access_token(self) -> str:
        """Get OAuth access token"""
        if self.access_token and self.token_expiry:
            if datetime.now().timestamp() < self.token_expiry:
                return self.access_token
        
        # Generate basic auth
        auth_string = f"{self.consumer_key}:{self.consumer_secret}"
        auth_bytes = base64.b64encode(auth_string.encode('utf-8'))
        auth_header = f"Basic {auth_bytes.decode('utf-8')}"
        
        # Request token
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/oauth/v1/generate?grant_type=client_credentials",
                headers={"Authorization": auth_header}
            )
            result = response.json()
        
        self.access_token = result.get("access_token")
        self.token_expiry = datetime.now().timestamp() + int(result.get("expires_in", 3600))
        
        return self.access_token
    
    def _generate_password(self, timestamp: str) -> str:
        """Generate password for STK Push"""
        data_to_encode = f"{self.business_short_code}{self.passkey}{timestamp}"
        return base64.b64encode(data_to_encode.encode('utf-8')).decode('utf-8')
    
    async def stk_push(
        self,
        phone_number: str,
        amount: int,
        account_reference: str,
        transaction_desc: str,
        callback_url: str
    ) -> Dict:
        """
        Initiate STK Push (Lipa Na M-Pesa Online)
        
        Args:
            phone_number: Customer phone number (254XXXXXXXXX)
            amount: Amount in KES
            account_reference: Account reference
            transaction_desc: Transaction description
            callback_url: Callback URL for result
        """
        access_token = await self._get_access_token()
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        password = self._generate_password(timestamp)
        
        payload = {
            "BusinessShortCode": self.business_short_code,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": amount,
            "PartyA": phone_number,
            "PartyB": self.business_short_code,
            "PhoneNumber": phone_number,
            "CallBackURL": callback_url,
            "AccountReference": account_reference,
            "TransactionDesc": transaction_desc
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/mpesa/stkpush/v1/processrequest",
                json=payload,
                headers={"Authorization": f"Bearer {access_token}"}
            )
            result = response.json()
        
        if result.get("ResponseCode") == "0":
            return {
                "status": "success",
                "checkout_request_id": result.get("CheckoutRequestID"),
                "merchant_request_id": result.get("MerchantRequestID"),
                "response_description": result.get("ResponseDescription")
            }
        else:
            return {
                "status": "failed",
                "error": result.get("errorMessage") or result.get("ResponseDescription"),
                "error_code": result.get("errorCode") or result.get("ResponseCode")
            }
    
    async def stk_query(self, checkout_request_id: str) -> Dict:
        """
        Query STK Push transaction status
        
        Args:
            checkout_request_id: Checkout request ID from STK push
        """
        access_token = await self._get_access_token()
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        password = self._generate_password(timestamp)
        
        payload = {
            "BusinessShortCode": self.business_short_code,
            "Password": password,
            "Timestamp": timestamp,
            "CheckoutRequestID": checkout_request_id
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/mpesa/stkpushquery/v1/query",
                json=payload,
                headers={"Authorization": f"Bearer {access_token}"}
            )
            result = response.json()
        
        if result.get("ResponseCode") == "0":
            return {
                "status": "success",
                "result_code": result.get("ResultCode"),
                "result_desc": result.get("ResultDesc"),
                "merchant_request_id": result.get("MerchantRequestID"),
                "checkout_request_id": result.get("CheckoutRequestID")
            }
        else:
            return {
                "status": "failed",
                "error": result.get("errorMessage") or result.get("ResponseDescription")
            }
    
    async def b2c_payment(
        self,
        phone_number: str,
        amount: int,
        occasion: str,
        remarks: str,
        result_url: str,
        queue_timeout_url: str,
        command_id: str = "BusinessPayment"
    ) -> Dict:
        """
        Business to Customer payment
        
        Args:
            phone_number: Recipient phone number (254XXXXXXXXX)
            amount: Amount in KES
            occasion: Occasion
            remarks: Remarks
            result_url: Result URL
            queue_timeout_url: Timeout URL
            command_id: Command ID (BusinessPayment, SalaryPayment, PromotionPayment)
        """
        access_token = await self._get_access_token()
        
        payload = {
            "InitiatorName": "testapi",
            "SecurityCredential": "encrypted_security_credential",
            "CommandID": command_id,
            "Amount": amount,
            "PartyA": self.business_short_code,
            "PartyB": phone_number,
            "Remarks": remarks,
            "QueueTimeOutURL": queue_timeout_url,
            "ResultURL": result_url,
            "Occasion": occasion
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/mpesa/b2c/v1/paymentrequest",
                json=payload,
                headers={"Authorization": f"Bearer {access_token}"}
            )
            result = response.json()
        
        if result.get("ResponseCode") == "0":
            return {
                "status": "success",
                "conversation_id": result.get("ConversationID"),
                "originator_conversation_id": result.get("OriginatorConversationID"),
                "response_description": result.get("ResponseDescription")
            }
        else:
            return {
                "status": "failed",
                "error": result.get("errorMessage") or result.get("ResponseDescription")
            }
    
    async def c2b_register_url(
        self,
        validation_url: str,
        confirmation_url: str,
        response_type: str = "Completed"
    ) -> Dict:
        """
        Register C2B URLs
        
        Args:
            validation_url: Validation URL
            confirmation_url: Confirmation URL
            response_type: Response type (Completed or Cancelled)
        """
        access_token = await self._get_access_token()
        
        payload = {
            "ShortCode": self.business_short_code,
            "ResponseType": response_type,
            "ConfirmationURL": confirmation_url,
            "ValidationURL": validation_url
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/mpesa/c2b/v1/registerurl",
                json=payload,
                headers={"Authorization": f"Bearer {access_token}"}
            )
            result = response.json()
        
        if result.get("ResponseCode") == "0":
            return {
                "status": "success",
                "response_description": result.get("ResponseDescription")
            }
        else:
            return {
                "status": "failed",
                "error": result.get("errorMessage") or result.get("ResponseDescription")
            }
    
    async def c2b_simulate(
        self,
        phone_number: str,
        amount: int,
        bill_ref_number: str,
        command_id: str = "CustomerPayBillOnline"
    ) -> Dict:
        """
        Simulate C2B transaction (sandbox only)
        
        Args:
            phone_number: Customer phone number
            amount: Amount in KES
            bill_ref_number: Bill reference number
            command_id: Command ID
        """
        access_token = await self._get_access_token()
        
        payload = {
            "ShortCode": self.business_short_code,
            "CommandID": command_id,
            "Amount": amount,
            "Msisdn": phone_number,
            "BillRefNumber": bill_ref_number
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/mpesa/c2b/v1/simulate",
                json=payload,
                headers={"Authorization": f"Bearer {access_token}"}
            )
            result = response.json()
        
        if result.get("ResponseCode") == "0":
            return {
                "status": "success",
                "response_description": result.get("ResponseDescription")
            }
        else:
            return {
                "status": "failed",
                "error": result.get("errorMessage") or result.get("ResponseDescription")
            }
    
    async def account_balance(
        self,
        result_url: str,
        queue_timeout_url: str,
        remarks: str = "Account Balance Query"
    ) -> Dict:
        """
        Query account balance
        
        Args:
            result_url: Result URL
            queue_timeout_url: Timeout URL
            remarks: Remarks
        """
        access_token = await self._get_access_token()
        
        payload = {
            "Initiator": "testapi",
            "SecurityCredential": "encrypted_security_credential",
            "CommandID": "AccountBalance",
            "PartyA": self.business_short_code,
            "IdentifierType": "4",
            "Remarks": remarks,
            "QueueTimeOutURL": queue_timeout_url,
            "ResultURL": result_url
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/mpesa/accountbalance/v1/query",
                json=payload,
                headers={"Authorization": f"Bearer {access_token}"}
            )
            result = response.json()
        
        if result.get("ResponseCode") == "0":
            return {
                "status": "success",
                "conversation_id": result.get("ConversationID"),
                "originator_conversation_id": result.get("OriginatorConversationID"),
                "response_description": result.get("ResponseDescription")
            }
        else:
            return {
                "status": "failed",
                "error": result.get("errorMessage") or result.get("ResponseDescription")
            }
    
    async def transaction_status(
        self,
        transaction_id: str,
        result_url: str,
        queue_timeout_url: str,
        remarks: str = "Transaction Status Query"
    ) -> Dict:
        """
        Query transaction status
        
        Args:
            transaction_id: M-Pesa transaction ID
            result_url: Result URL
            queue_timeout_url: Timeout URL
            remarks: Remarks
        """
        access_token = await self._get_access_token()
        
        payload = {
            "Initiator": "testapi",
            "SecurityCredential": "encrypted_security_credential",
            "CommandID": "TransactionStatusQuery",
            "TransactionID": transaction_id,
            "PartyA": self.business_short_code,
            "IdentifierType": "4",
            "ResultURL": result_url,
            "QueueTimeOutURL": queue_timeout_url,
            "Remarks": remarks,
            "Occasion": "Transaction Status"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/mpesa/transactionstatus/v1/query",
                json=payload,
                headers={"Authorization": f"Bearer {access_token}"}
            )
            result = response.json()
        
        if result.get("ResponseCode") == "0":
            return {
                "status": "success",
                "conversation_id": result.get("ConversationID"),
                "originator_conversation_id": result.get("OriginatorConversationID"),
                "response_description": result.get("ResponseDescription")
            }
        else:
            return {
                "status": "failed",
                "error": result.get("errorMessage") or result.get("ResponseDescription")
            }
