"""
Lightning Network Gateway Integration
Supports instant Bitcoin payments with low fees
"""

import hashlib
import secrets
from typing import Dict, Optional
import httpx
from datetime import datetime, timedelta


class LightningGateway:
    """Lightning Network payment gateway implementation"""
    
    def __init__(
        self,
        lnd_host: str,
        macaroon: str,
        tls_cert_path: Optional[str] = None
    ):
        self.lnd_host = lnd_host
        self.macaroon = macaroon
        self.tls_cert_path = tls_cert_path
        self.headers = {
            "Grpc-Metadata-macaroon": macaroon
        }
    
    async def create_invoice(
        self,
        amount_sats: int,
        memo: str,
        expiry: int = 3600
    ) -> Dict:
        """
        Create Lightning invoice
        
        Args:
            amount_sats: Amount in satoshis
            memo: Invoice memo/description
            expiry: Expiry time in seconds (default 1 hour)
        """
        payload = {
            "value": str(amount_sats),
            "memo": memo,
            "expiry": str(expiry)
        }
        
        try:
            async with httpx.AsyncClient(verify=self.tls_cert_path if self.tls_cert_path else True) as client:
                response = await client.post(
                    f"{self.lnd_host}/v1/invoices",
                    json=payload,
                    headers=self.headers
                )
                result = response.json()
            
            if response.status_code == 200:
                return {
                    "status": "success",
                    "payment_request": result.get("payment_request"),
                    "r_hash": result.get("r_hash"),
                    "add_index": result.get("add_index"),
                    "payment_addr": result.get("payment_addr")
                }
            else:
                return {
                    "status": "failed",
                    "error": result.get("message", "Failed to create invoice"),
                    "error_code": result.get("code")
                }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e)
            }
    
    async def decode_invoice(self, payment_request: str) -> Dict:
        """
        Decode Lightning invoice
        
        Args:
            payment_request: BOLT11 payment request string
        """
        try:
            async with httpx.AsyncClient(verify=self.tls_cert_path if self.tls_cert_path else True) as client:
                response = await client.get(
                    f"{self.lnd_host}/v1/payreq/{payment_request}",
                    headers=self.headers
                )
                result = response.json()
            
            if response.status_code == 200:
                return {
                    "status": "success",
                    "destination": result.get("destination"),
                    "payment_hash": result.get("payment_hash"),
                    "num_satoshis": int(result.get("num_satoshis", 0)),
                    "timestamp": int(result.get("timestamp", 0)),
                    "expiry": int(result.get("expiry", 0)),
                    "description": result.get("description"),
                    "cltv_expiry": int(result.get("cltv_expiry", 0))
                }
            else:
                return {
                    "status": "failed",
                    "error": result.get("message", "Failed to decode invoice")
                }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e)
            }
    
    async def pay_invoice(
        self,
        payment_request: str,
        amount_sats: Optional[int] = None,
        fee_limit_sats: int = 100
    ) -> Dict:
        """
        Pay Lightning invoice
        
        Args:
            payment_request: BOLT11 payment request
            amount_sats: Amount in satoshis (for zero-amount invoices)
            fee_limit_sats: Maximum fee in satoshis
        """
        payload = {
            "payment_request": payment_request,
            "fee_limit": {
                "fixed": str(fee_limit_sats)
            }
        }
        
        if amount_sats:
            payload["amt"] = str(amount_sats)
        
        try:
            async with httpx.AsyncClient(
                verify=self.tls_cert_path if self.tls_cert_path else True,
                timeout=60.0
            ) as client:
                response = await client.post(
                    f"{self.lnd_host}/v1/channels/transactions",
                    json=payload,
                    headers=self.headers
                )
                result = response.json()
            
            if response.status_code == 200:
                if result.get("payment_error"):
                    return {
                        "status": "failed",
                        "error": result.get("payment_error")
                    }
                
                return {
                    "status": "success",
                    "payment_preimage": result.get("payment_preimage"),
                    "payment_hash": result.get("payment_hash"),
                    "payment_route": result.get("payment_route")
                }
            else:
                return {
                    "status": "failed",
                    "error": result.get("message", "Payment failed")
                }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e)
            }
    
    async def lookup_invoice(self, r_hash: str) -> Dict:
        """
        Lookup invoice by payment hash
        
        Args:
            r_hash: Payment hash (hex encoded)
        """
        try:
            async with httpx.AsyncClient(verify=self.tls_cert_path if self.tls_cert_path else True) as client:
                response = await client.get(
                    f"{self.lnd_host}/v1/invoice/{r_hash}",
                    headers=self.headers
                )
                result = response.json()
            
            if response.status_code == 200:
                state_map = {
                    "OPEN": "pending",
                    "SETTLED": "paid",
                    "CANCELED": "cancelled",
                    "ACCEPTED": "accepted"
                }
                
                return {
                    "status": "success",
                    "state": state_map.get(result.get("state"), "unknown"),
                    "value": int(result.get("value", 0)),
                    "settled": result.get("settled", False),
                    "settle_date": int(result.get("settle_date", 0)),
                    "payment_request": result.get("payment_request"),
                    "memo": result.get("memo")
                }
            else:
                return {
                    "status": "failed",
                    "error": result.get("message", "Invoice not found")
                }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e)
            }
    
    async def get_balance(self) -> Dict:
        """Get Lightning wallet balance"""
        try:
            async with httpx.AsyncClient(verify=self.tls_cert_path if self.tls_cert_path else True) as client:
                response = await client.get(
                    f"{self.lnd_host}/v1/balance/channels",
                    headers=self.headers
                )
                result = response.json()
            
            if response.status_code == 200:
                return {
                    "status": "success",
                    "balance_sats": int(result.get("balance", 0)),
                    "pending_open_balance": int(result.get("pending_open_balance", 0))
                }
            else:
                return {
                    "status": "failed",
                    "error": result.get("message", "Failed to get balance")
                }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e)
            }
    
    async def get_node_info(self) -> Dict:
        """Get Lightning node information"""
        try:
            async with httpx.AsyncClient(verify=self.tls_cert_path if self.tls_cert_path else True) as client:
                response = await client.get(
                    f"{self.lnd_host}/v1/getinfo",
                    headers=self.headers
                )
                result = response.json()
            
            if response.status_code == 200:
                return {
                    "status": "success",
                    "identity_pubkey": result.get("identity_pubkey"),
                    "alias": result.get("alias"),
                    "num_active_channels": int(result.get("num_active_channels", 0)),
                    "num_peers": int(result.get("num_peers", 0)),
                    "block_height": int(result.get("block_height", 0)),
                    "synced_to_chain": result.get("synced_to_chain", False),
                    "version": result.get("version")
                }
            else:
                return {
                    "status": "failed",
                    "error": result.get("message", "Failed to get node info")
                }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e)
            }
    
    async def list_payments(self, max_payments: int = 100) -> Dict:
        """
        List recent payments
        
        Args:
            max_payments: Maximum number of payments to return
        """
        try:
            async with httpx.AsyncClient(verify=self.tls_cert_path if self.tls_cert_path else True) as client:
                response = await client.get(
                    f"{self.lnd_host}/v1/payments?max_payments={max_payments}",
                    headers=self.headers
                )
                result = response.json()
            
            if response.status_code == 200:
                payments = []
                for payment in result.get("payments", []):
                    payments.append({
                        "payment_hash": payment.get("payment_hash"),
                        "value_sats": int(payment.get("value_sat", 0)),
                        "creation_date": int(payment.get("creation_date", 0)),
                        "fee_sats": int(payment.get("fee_sat", 0)),
                        "payment_preimage": payment.get("payment_preimage"),
                        "status": payment.get("status")
                    })
                
                return {
                    "status": "success",
                    "payments": payments
                }
            else:
                return {
                    "status": "failed",
                    "error": result.get("message", "Failed to list payments")
                }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e)
            }
    
    async def list_invoices(self, num_max_invoices: int = 100, pending_only: bool = False) -> Dict:
        """
        List invoices
        
        Args:
            num_max_invoices: Maximum number of invoices to return
            pending_only: Return only pending invoices
        """
        try:
            params = f"num_max_invoices={num_max_invoices}&pending_only={str(pending_only).lower()}"
            
            async with httpx.AsyncClient(verify=self.tls_cert_path if self.tls_cert_path else True) as client:
                response = await client.get(
                    f"{self.lnd_host}/v1/invoices?{params}",
                    headers=self.headers
                )
                result = response.json()
            
            if response.status_code == 200:
                invoices = []
                for invoice in result.get("invoices", []):
                    invoices.append({
                        "payment_request": invoice.get("payment_request"),
                        "r_hash": invoice.get("r_hash"),
                        "value_sats": int(invoice.get("value", 0)),
                        "settled": invoice.get("settled", False),
                        "creation_date": int(invoice.get("creation_date", 0)),
                        "settle_date": int(invoice.get("settle_date", 0)),
                        "memo": invoice.get("memo"),
                        "state": invoice.get("state")
                    })
                
                return {
                    "status": "success",
                    "invoices": invoices
                }
            else:
                return {
                    "status": "failed",
                    "error": result.get("message", "Failed to list invoices")
                }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e)
            }
