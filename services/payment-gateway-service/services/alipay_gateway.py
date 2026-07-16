"""
Alipay Gateway Integration
Supports web payments, mobile payments, and QR code payments
"""

import base64
import json
from datetime import datetime
from typing import Dict, Optional
from urllib.parse import quote, urlencode
import httpx
from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_v1_5
from Crypto.Hash import SHA256


class AlipayGateway:
    """Alipay payment gateway implementation"""
    
    def __init__(
        self,
        app_id: str,
        private_key: str,
        alipay_public_key: str,
        app_private_key_path: Optional[str] = None,
        alipay_public_key_path: Optional[str] = None
    ):
        self.app_id = app_id
        self.gateway_url = "https://openapi.alipay.com/gateway.do"
        self.gateway_url_dev = "https://openapi.alipaydev.com/gateway.do"
        
        # Load private key
        if app_private_key_path:
            with open(app_private_key_path) as f:
                self.private_key = RSA.import_key(f.read())
        else:
            self.private_key = RSA.import_key(private_key)
        
        # Load Alipay public key
        if alipay_public_key_path:
            with open(alipay_public_key_path) as f:
                self.alipay_public_key = RSA.import_key(f.read())
        else:
            self.alipay_public_key = RSA.import_key(alipay_public_key)
    
    def _sign(self, unsigned_string: str) -> str:
        """Generate RSA signature"""
        signer = PKCS1_v1_5.new(self.private_key)
        signature = signer.sign(SHA256.new(unsigned_string.encode('utf-8')))
        return base64.b64encode(signature).decode('utf-8')
    
    def _verify(self, data: str, signature: str) -> bool:
        """Verify RSA signature"""
        verifier = PKCS1_v1_5.new(self.alipay_public_key)
        digest = SHA256.new(data.encode('utf-8'))
        return verifier.verify(digest, base64.b64decode(signature))
    
    def _build_request_params(self, method: str, biz_content: Dict) -> Dict:
        """Build common request parameters"""
        params = {
            "app_id": self.app_id,
            "method": method,
            "format": "JSON",
            "charset": "utf-8",
            "sign_type": "RSA2",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "version": "1.0",
            "biz_content": json.dumps(biz_content, separators=(',', ':'))
        }
        return params
    
    def _generate_sign_string(self, params: Dict) -> str:
        """Generate string to sign"""
        sorted_params = sorted(params.items())
        return "&".join([f"{k}={v}" for k, v in sorted_params if v])
    
    async def create_web_payment(
        self,
        out_trade_no: str,
        total_amount: float,
        subject: str,
        return_url: str,
        notify_url: str,
        product_code: str = "FAST_INSTANT_TRADE_PAY"
    ) -> str:
        """
        Create web payment (returns payment URL)
        
        Args:
            out_trade_no: Merchant order number
            total_amount: Amount in CNY
            subject: Product subject
            return_url: Return URL after payment
            notify_url: Async notification URL
            product_code: Product code
        """
        biz_content = {
            "out_trade_no": out_trade_no,
            "total_amount": str(total_amount),
            "subject": subject,
            "product_code": product_code
        }
        
        params = self._build_request_params("alipay.trade.page.pay", biz_content)
        params["return_url"] = return_url
        params["notify_url"] = notify_url
        
        # Generate signature
        sign_string = self._generate_sign_string(params)
        params["sign"] = self._sign(sign_string)
        
        # Build payment URL
        payment_url = f"{self.gateway_url}?{urlencode(params)}"
        return payment_url
    
    async def create_mobile_payment(
        self,
        out_trade_no: str,
        total_amount: float,
        subject: str,
        notify_url: str,
        product_code: str = "QUICK_MSECURITY_PAY"
    ) -> str:
        """
        Create mobile payment (returns order string for SDK)
        
        Args:
            out_trade_no: Merchant order number
            total_amount: Amount in CNY
            subject: Product subject
            notify_url: Async notification URL
            product_code: Product code
        """
        biz_content = {
            "out_trade_no": out_trade_no,
            "total_amount": str(total_amount),
            "subject": subject,
            "product_code": product_code
        }
        
        params = self._build_request_params("alipay.trade.app.pay", biz_content)
        params["notify_url"] = notify_url
        
        # Generate signature
        sign_string = self._generate_sign_string(params)
        params["sign"] = self._sign(sign_string)
        
        # Build order string
        order_string = urlencode(params)
        return order_string
    
    async def create_qr_payment(
        self,
        out_trade_no: str,
        total_amount: float,
        subject: str,
        notify_url: str
    ) -> Dict:
        """
        Create QR code payment
        
        Args:
            out_trade_no: Merchant order number
            total_amount: Amount in CNY
            subject: Product subject
            notify_url: Async notification URL
        """
        biz_content = {
            "out_trade_no": out_trade_no,
            "total_amount": str(total_amount),
            "subject": subject
        }
        
        params = self._build_request_params("alipay.trade.precreate", biz_content)
        params["notify_url"] = notify_url
        
        # Generate signature
        sign_string = self._generate_sign_string(params)
        params["sign"] = self._sign(sign_string)
        
        # Make API request
        async with httpx.AsyncClient() as client:
            response = await client.post(self.gateway_url, data=params)
            result = response.json()
        
        response_data = result.get("alipay_trade_precreate_response", {})
        
        if response_data.get("code") == "10000":
            return {
                "status": "success",
                "qr_code": response_data.get("qr_code"),
                "out_trade_no": out_trade_no
            }
        else:
            return {
                "status": "failed",
                "error": response_data.get("sub_msg") or response_data.get("msg"),
                "error_code": response_data.get("sub_code") or response_data.get("code")
            }
    
    async def query_order(self, out_trade_no: Optional[str] = None, trade_no: Optional[str] = None) -> Dict:
        """
        Query order status
        
        Args:
            out_trade_no: Merchant order number
            trade_no: Alipay trade number
        """
        biz_content = {}
        if out_trade_no:
            biz_content["out_trade_no"] = out_trade_no
        elif trade_no:
            biz_content["trade_no"] = trade_no
        else:
            raise ValueError("Either out_trade_no or trade_no must be provided")
        
        params = self._build_request_params("alipay.trade.query", biz_content)
        
        # Generate signature
        sign_string = self._generate_sign_string(params)
        params["sign"] = self._sign(sign_string)
        
        # Make API request
        async with httpx.AsyncClient() as client:
            response = await client.post(self.gateway_url, data=params)
            result = response.json()
        
        response_data = result.get("alipay_trade_query_response", {})
        
        if response_data.get("code") == "10000":
            return {
                "status": "success",
                "trade_status": response_data.get("trade_status"),
                "trade_no": response_data.get("trade_no"),
                "out_trade_no": response_data.get("out_trade_no"),
                "total_amount": float(response_data.get("total_amount", 0)),
                "buyer_user_id": response_data.get("buyer_user_id")
            }
        else:
            return {
                "status": "failed",
                "error": response_data.get("sub_msg") or response_data.get("msg")
            }
    
    async def refund(
        self,
        out_trade_no: str,
        refund_amount: float,
        refund_reason: Optional[str] = None,
        out_request_no: Optional[str] = None
    ) -> Dict:
        """
        Process refund
        
        Args:
            out_trade_no: Original merchant order number
            refund_amount: Refund amount in CNY
            refund_reason: Refund reason
            out_request_no: Refund request number
        """
        biz_content = {
            "out_trade_no": out_trade_no,
            "refund_amount": str(refund_amount)
        }
        
        if refund_reason:
            biz_content["refund_reason"] = refund_reason
        if out_request_no:
            biz_content["out_request_no"] = out_request_no
        
        params = self._build_request_params("alipay.trade.refund", biz_content)
        
        # Generate signature
        sign_string = self._generate_sign_string(params)
        params["sign"] = self._sign(sign_string)
        
        # Make API request
        async with httpx.AsyncClient() as client:
            response = await client.post(self.gateway_url, data=params)
            result = response.json()
        
        response_data = result.get("alipay_trade_refund_response", {})
        
        if response_data.get("code") == "10000":
            return {
                "status": "success",
                "trade_no": response_data.get("trade_no"),
                "out_trade_no": response_data.get("out_trade_no"),
                "refund_fee": float(response_data.get("refund_fee", 0))
            }
        else:
            return {
                "status": "failed",
                "error": response_data.get("sub_msg") or response_data.get("msg")
            }
    
    async def close_order(self, out_trade_no: str) -> Dict:
        """Close unpaid order"""
        biz_content = {"out_trade_no": out_trade_no}
        
        params = self._build_request_params("alipay.trade.close", biz_content)
        
        # Generate signature
        sign_string = self._generate_sign_string(params)
        params["sign"] = self._sign(sign_string)
        
        # Make API request
        async with httpx.AsyncClient() as client:
            response = await client.post(self.gateway_url, data=params)
            result = response.json()
        
        response_data = result.get("alipay_trade_close_response", {})
        
        if response_data.get("code") == "10000":
            return {"status": "success", "message": "Order closed successfully"}
        else:
            return {
                "status": "failed",
                "error": response_data.get("sub_msg") or response_data.get("msg")
            }
    
    def verify_notify(self, params: Dict) -> bool:
        """Verify payment notification signature"""
        sign = params.pop("sign", None)
        sign_type = params.pop("sign_type", None)
        
        if not sign or sign_type != "RSA2":
            return False
        
        # Build string to verify
        sorted_params = sorted(params.items())
        unsigned_string = "&".join([f"{k}={v}" for k, v in sorted_params if v])
        
        return self._verify(unsigned_string, sign)
