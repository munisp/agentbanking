"""
WorldRemit Payment Gateway Integration
Provider: WorldRemit
Base Country: UK
"""
from typing import Dict, Optional
from decimal import Decimal
import httpx
import asyncio
from datetime import datetime, timedelta

class WorldRemitGateway:
    """
    WorldRemit payment gateway integration.
    
    Supported Features:
    - International money transfers
    - Real-time FX rates
    - Transaction tracking
    - Compliance & KYC
    """
    
    def __init__(self, api_key: str, api_secret: str, environment: str = "sandbox"):
        self.api_key = api_key
        self.api_secret = api_secret
        self.environment = environment
        self.base_url = self._get_base_url()
        self.supported_currencies = ['USD', 'GBP', 'EUR', 'KES', 'GHS', 'NGN']
        self.supported_corridors = self._init_corridors()
    
    def _get_base_url(self) -> str:
        """Get API base URL based on environment."""
        if self.environment == "production":
            return "https://api.worldremit.com/v1"
        return "https://sandbox-api.worldremit.com/v1"
    
    def _init_corridors(self) -> list:
        """Initialize supported payment corridors."""
        corridors = []
        for curr in self.supported_currencies:
            corridors.append(f"USD-{curr}")
            corridors.append(f"EUR-{curr}")
            corridors.append(f"GBP-{curr}")
        return corridors
    
    async def get_quote(self, amount: Decimal, from_currency: str, 
                       to_currency: str) -> Dict:
        """
        Get quote for money transfer.
        
        Args:
            amount: Amount to send
            from_currency: Source currency code
            to_currency: Destination currency code
        
        Returns:
            Quote details including fees and FX rate
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/quotes",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "source_amount": str(amount),
                    "source_currency": from_currency,
                    "target_currency": to_currency
                },
                timeout=30.0
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "quote_id": data.get("id"),
                    "source_amount": Decimal(data.get("source_amount")),
                    "target_amount": Decimal(data.get("target_amount")),
                    "exchange_rate": Decimal(data.get("rate")),
                    "fee": Decimal(data.get("fee", 0)),
                    "total_cost": Decimal(data.get("total_cost")),
                    "expires_at": datetime.fromisoformat(data.get("expires_at")),
                    "provider": "WorldRemit"
                }
            else:
                raise Exception(f"WorldRemit API error: {response.status_code}")
    
    async def create_transfer(self, quote_id: str, sender: Dict, 
                             recipient: Dict, purpose: str = "family_support") -> Dict:
        """
        Create money transfer.
        
        Args:
            quote_id: Quote ID from get_quote()
            sender: Sender details (name, address, etc.)
            recipient: Recipient details (name, account, etc.)
            purpose: Transfer purpose
        
        Returns:
            Transfer details including transaction ID
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/transfers",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "quote_id": quote_id,
                    "sender": sender,
                    "recipient": recipient,
                    "purpose": purpose
                },
                timeout=30.0
            )
            
            if response.status_code in [200, 201]:
                data = response.json()
                return {
                    "transaction_id": data.get("id"),
                    "status": data.get("status", "pending"),
                    "created_at": datetime.fromisoformat(data.get("created_at")),
                    "estimated_delivery": datetime.fromisoformat(data.get("estimated_delivery")),
                    "provider": "WorldRemit",
                    "tracking_url": data.get("tracking_url")
                }
            else:
                raise Exception(f"WorldRemit transfer failed: {response.status_code}")
    
    async def get_transfer_status(self, transaction_id: str) -> Dict:
        """
        Get transfer status.
        
        Args:
            transaction_id: Transaction ID from create_transfer()
        
        Returns:
            Current transfer status
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/transfers/{transaction_id}",
                headers={
                    "Authorization": f"Bearer {self.api_key}"
                },
                timeout=30.0
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "transaction_id": transaction_id,
                    "status": data.get("status"),
                    "updated_at": datetime.fromisoformat(data.get("updated_at")),
                    "provider": "WorldRemit"
                }
            else:
                raise Exception(f"Status check failed: {response.status_code}")
    
    async def cancel_transfer(self, transaction_id: str) -> Dict:
        """
        Cancel pending transfer.
        
        Args:
            transaction_id: Transaction ID to cancel
        
        Returns:
            Cancellation confirmation
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/transfers/{transaction_id}/cancel",
                headers={
                    "Authorization": f"Bearer {self.api_key}"
                },
                timeout=30.0
            )
            
            if response.status_code == 200:
                return {
                    "transaction_id": transaction_id,
                    "status": "cancelled",
                    "cancelled_at": datetime.utcnow(),
                    "provider": "WorldRemit"
                }
            else:
                raise Exception(f"Cancellation failed: {response.status_code}")
    
    def supports_corridor(self, from_country: str, to_country: str) -> bool:
        """Check if corridor is supported."""
        corridor = f"{from_country}-{to_country}"
        return corridor in self.supported_corridors
    
    def get_limits(self, currency: str) -> Dict:
        """Get transaction limits for currency."""
        return {
            "min_amount": Decimal("10.00"),
            "max_amount": Decimal("50000.00"),
            "currency": currency
        }

# Example usage
async def main():
    gateway = WorldRemitGateway(
        api_key=os.environ.get("GATEWAY_API_KEY", ""),
        api_secret=os.environ.get("GATEWAY_API_SECRET", ""),
        environment="sandbox"
    )
    
    # Get quote
    quote = await gateway.get_quote(
        amount=Decimal("1000.00"),
        from_currency="USD",
        to_currency="EUR"
    )
    print(f"Quote: {quote}")
    
    # Create transfer
    transfer = await gateway.create_transfer(
        quote_id=quote["quote_id"],
        sender={
            "name": "John Doe",
            "email": "john@example.com",
            "address": "123 Main St, New York, NY"
        },
        recipient={
            "name": "Jane Smith",
            "account": "GB29NWBK60161331926819",
            "address": "456 High St, London, UK"
        }
    )
    print(f"Transfer: {transfer}")

if __name__ == "__main__":
    asyncio.run(main())
