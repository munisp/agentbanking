#!/usr/bin/env python3
"""
Open Banking Integration Service - Phase 2
PSD2 compliance, Plaid integration, instant bank verification, account aggregation
"""

from typing import Dict, List, Optional, Tuple
from decimal import Decimal
from datetime import datetime, timedelta
from enum import Enum
import logging
import uuid
import hashlib
import hmac
import base64
from dataclasses import dataclass, asdict
import json
import aiohttp

logger = logging.getLogger(__name__)


class BankingProvider(str, Enum):
    """Open banking providers"""
    PLAID = "plaid"
    TINK = "tink"
    YAPILY = "yapily"
    TRUELAYER = "truelayer"
    FINICITY = "finicity"


class AccountType(str, Enum):
    """Bank account types"""
    CHECKING = "checking"
    SAVINGS = "savings"
    CREDIT_CARD = "credit_card"
    INVESTMENT = "investment"
    LOAN = "loan"


class VerificationStatus(str, Enum):
    """Verification status"""
    PENDING = "pending"
    VERIFIED = "verified"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass
class BankAccount:
    """Bank account details"""
    account_id: str
    user_id: str
    provider: str
    institution_id: str
    institution_name: str
    account_type: str
    account_number_masked: str
    routing_number: Optional[str]
    iban: Optional[str]
    swift_code: Optional[str]
    balance: Optional[Decimal]
    currency: str
    verification_status: str
    linked_at: str
    last_synced: Optional[str]


@dataclass
class Transaction:
    """Bank transaction"""
    transaction_id: str
    account_id: str
    amount: Decimal
    currency: str
    description: str
    merchant_name: Optional[str]
    category: List[str]
    transaction_date: str
    posted_date: str
    pending: bool


class OpenBankingService:
    """
    Comprehensive Open Banking Integration Service
    
    Features:
    - PSD2 compliance (Europe)
    - Plaid integration (US/Canada)
    - Instant bank verification
    - Account aggregation
    - Transaction categorization
    - Balance checking
    - Payment initiation
    - Consent management
    - Multi-provider support
    """
    
    def __init__(self, config: Dict) -> None:
        """Initialize open banking service"""
        self.config = config
        
        # Provider credentials
        self.plaid_client_id = config.get("plaid_client_id")
        self.plaid_secret = config.get("plaid_secret")
        self.plaid_env = config.get("plaid_env", "sandbox")  # sandbox, development, production
        
        self.tink_client_id = config.get("tink_client_id")
        self.tink_client_secret = config.get("tink_client_secret")
        
        self.yapily_app_id = config.get("yapily_app_id")
        self.yapily_secret = config.get("yapily_secret")
        
        # API endpoints
        self.plaid_base_url = self._get_plaid_url()
        self.tink_base_url = "https://api.tink.com"
        self.yapily_base_url = "https://api.yapily.com"
        
        # Cache
        self.linked_accounts = {}
        self.access_tokens = {}
        self.consent_cache = {}
        
        logger.info("Open banking service initialized")
    
    def _get_plaid_url(self) -> str:
        """Get Plaid API URL based on environment"""
        urls = {
            "sandbox": "https://sandbox.plaid.com",
            "development": "https://development.plaid.com",
            "production": "https://production.plaid.com"
        }
        return urls.get(self.plaid_env, urls["sandbox"])
    
    # ========== Plaid Integration ==========
    
    async def create_plaid_link_token(
        self,
        user_id: str,
        products: List[str] = None,
        country_codes: List[str] = None
    ) -> Dict:
        """
        Create Plaid Link token for account linking
        
        Args:
            user_id: User identifier
            products: Plaid products (auth, transactions, balance, etc.)
            country_codes: Country codes (US, CA, GB, etc.)
            
        Returns:
            Link token and expiration
        """
        if products is None:
            products = ["auth", "transactions", "balance", "identity"]
        
        if country_codes is None:
            country_codes = ["US", "CA", "GB"]
        
        payload = {
            "client_id": self.plaid_client_id,
            "secret": self.plaid_secret,
            "client_name": "Nigerian Remittance Platform",
            "user": {
                "client_user_id": user_id
            },
            "products": products,
            "country_codes": country_codes,
            "language": "en",
            "webhook": f"{self.config.get('webhook_base_url')}/webhooks/plaid",
            "redirect_uri": f"{self.config.get('app_base_url')}/plaid/oauth-redirect"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.plaid_base_url}/link/token/create",
                json=payload
            ) as response:
                result = await response.json()
                
                if response.status == 200:
                    return {
                        "link_token": result["link_token"],
                        "expiration": result["expiration"],
                        "request_id": result["request_id"]
                    }
                else:
                    raise Exception(f"Plaid error: {result.get('error_message')}")
    
    async def exchange_plaid_public_token(
        self,
        user_id: str,
        public_token: str
    ) -> Dict:
        """
        Exchange Plaid public token for access token
        
        Args:
            user_id: User identifier
            public_token: Public token from Plaid Link
            
        Returns:
            Access token and item ID
        """
        payload = {
            "client_id": self.plaid_client_id,
            "secret": self.plaid_secret,
            "public_token": public_token
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.plaid_base_url}/item/public_token/exchange",
                json=payload
            ) as response:
                result = await response.json()
                
                if response.status == 200:
                    access_token = result["access_token"]
                    item_id = result["item_id"]
                    
                    # Store access token
                    self.access_tokens[user_id] = {
                        "access_token": access_token,
                        "item_id": item_id,
                        "created_at": datetime.utcnow().isoformat()
                    }
                    
                    # Fetch and store account details
                    accounts = await self.get_plaid_accounts(user_id, access_token)
                    
                    return {
                        "access_token": access_token,
                        "item_id": item_id,
                        "accounts": accounts
                    }
                else:
                    raise Exception(f"Plaid error: {result.get('error_message')}")
    
    async def get_plaid_accounts(
        self,
        user_id: str,
        access_token: str
    ) -> List[BankAccount]:
        """
        Get bank accounts from Plaid
        
        Args:
            user_id: User identifier
            access_token: Plaid access token
            
        Returns:
            List of bank accounts
        """
        payload = {
            "client_id": self.plaid_client_id,
            "secret": self.plaid_secret,
            "access_token": access_token
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.plaid_base_url}/accounts/get",
                json=payload
            ) as response:
                result = await response.json()
                
                if response.status == 200:
                    accounts = []
                    
                    for acc in result.get("accounts", []):
                        account = BankAccount(
                            account_id=acc["account_id"],
                            user_id=user_id,
                            provider=BankingProvider.PLAID.value,
                            institution_id=result.get("item", {}).get("institution_id", ""),
                            institution_name=acc.get("name", ""),
                            account_type=acc["type"],
                            account_number_masked=acc.get("mask", "****"),
                            routing_number=None,  # Get from /auth/get
                            iban=None,
                            swift_code=None,
                            balance=Decimal(str(acc["balances"]["current"])) if acc.get("balances") else None,
                            currency=acc["balances"].get("iso_currency_code", "USD"),
                            verification_status=VerificationStatus.VERIFIED.value,
                            linked_at=datetime.utcnow().isoformat(),
                            last_synced=datetime.utcnow().isoformat()
                        )
                        accounts.append(account)
                    
                    # Store accounts
                    if user_id not in self.linked_accounts:
                        self.linked_accounts[user_id] = []
                    self.linked_accounts[user_id].extend(accounts)
                    
                    return accounts
                else:
                    raise Exception(f"Plaid error: {result.get('error_message')}")
    
    async def get_plaid_auth_details(
        self,
        user_id: str,
        access_token: str
    ) -> Dict:
        """
        Get bank account authentication details (routing numbers, account numbers)
        
        Args:
            user_id: User identifier
            access_token: Plaid access token
            
        Returns:
            Authentication details
        """
        payload = {
            "client_id": self.plaid_client_id,
            "secret": self.plaid_secret,
            "access_token": access_token
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.plaid_base_url}/auth/get",
                json=payload
            ) as response:
                result = await response.json()
                
                if response.status == 200:
                    auth_details = {}
                    
                    for acc in result.get("accounts", []):
                        account_id = acc["account_id"]
                        auth_details[account_id] = {
                            "account_number": acc.get("account", ""),
                            "routing_number": acc.get("routing", ""),
                            "wire_routing": acc.get("wire_routing", "")
                        }
                    
                    return auth_details
                else:
                    raise Exception(f"Plaid error: {result.get('error_message')}")
    
    async def get_plaid_transactions(
        self,
        user_id: str,
        access_token: str,
        start_date: str,
        end_date: str
    ) -> List[Transaction]:
        """
        Get transactions from Plaid
        
        Args:
            user_id: User identifier
            access_token: Plaid access token
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            
        Returns:
            List of transactions
        """
        payload = {
            "client_id": self.plaid_client_id,
            "secret": self.plaid_secret,
            "access_token": access_token,
            "start_date": start_date,
            "end_date": end_date,
            "options": {
                "count": 500,
                "offset": 0
            }
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.plaid_base_url}/transactions/get",
                json=payload
            ) as response:
                result = await response.json()
                
                if response.status == 200:
                    transactions = []
                    
                    for txn in result.get("transactions", []):
                        transaction = Transaction(
                            transaction_id=txn["transaction_id"],
                            account_id=txn["account_id"],
                            amount=Decimal(str(txn["amount"])),
                            currency=txn.get("iso_currency_code", "USD"),
                            description=txn.get("name", ""),
                            merchant_name=txn.get("merchant_name"),
                            category=txn.get("category", []),
                            transaction_date=txn["date"],
                            posted_date=txn.get("authorized_date", txn["date"]),
                            pending=txn.get("pending", False)
                        )
                        transactions.append(transaction)
                    
                    return transactions
                else:
                    raise Exception(f"Plaid error: {result.get('error_message')}")
    
    async def get_plaid_balance(
        self,
        user_id: str,
        access_token: str
    ) -> Dict:
        """
        Get real-time balance from Plaid
        
        Args:
            user_id: User identifier
            access_token: Plaid access token
            
        Returns:
            Balance information
        """
        payload = {
            "client_id": self.plaid_client_id,
            "secret": self.plaid_secret,
            "access_token": access_token
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.plaid_base_url}/accounts/balance/get",
                json=payload
            ) as response:
                result = await response.json()
                
                if response.status == 200:
                    balances = {}
                    
                    for acc in result.get("accounts", []):
                        balances[acc["account_id"]] = {
                            "current": float(acc["balances"]["current"]),
                            "available": float(acc["balances"].get("available")),
                            "limit": float(acc["balances"].get("limit")) if acc["balances"].get("limit") else None,
                            "currency": acc["balances"].get("iso_currency_code", "USD")
                        }
                    
                    return balances
                else:
                    raise Exception(f"Plaid error: {result.get('error_message')}")
    
    async def verify_account_instantly(
        self,
        user_id: str,
        account_id: str
    ) -> Dict:
        """
        Instantly verify bank account using Plaid
        
        Args:
            user_id: User identifier
            account_id: Account identifier
            
        Returns:
            Verification result
        """
        # Get access token
        token_data = self.access_tokens.get(user_id)
        if not token_data:
            raise Exception("No access token found for user")
        
        access_token = token_data["access_token"]
        
        # Get auth details
        auth_details = await self.get_plaid_auth_details(user_id, access_token)
        
        if account_id in auth_details:
            # Account verified
            return {
                "account_id": account_id,
                "verification_status": VerificationStatus.VERIFIED.value,
                "verification_method": "instant",
                "verified_at": datetime.utcnow().isoformat(),
                "account_details": {
                    "account_number_masked": f"****{auth_details[account_id]['account_number'][-4:]}",
                    "routing_number": auth_details[account_id]["routing_number"]
                }
            }
        else:
            raise Exception("Account not found")
    
    # ========== PSD2 Integration (Europe) ==========
    
    async def create_psd2_consent(
        self,
        user_id: str,
        institution_id: str,
        permissions: List[str] = None
    ) -> Dict:
        """
        Create PSD2 consent for account access
        
        Args:
            user_id: User identifier
            institution_id: Bank institution ID
            permissions: Requested permissions
            
        Returns:
            Consent details and authorization URL
        """
        if permissions is None:
            permissions = ["ReadAccountsBasic", "ReadAccountsDetail", "ReadBalances", "ReadTransactionsBasic", "ReadTransactionsDetail"]
        
        # Using Yapily for PSD2
        payload = {
            "applicationUserId": user_id,
            "institutionId": institution_id,
            "callback": f"{self.config.get('app_base_url')}/psd2/callback",
            "oneTimeToken": False,
            "scopes": permissions
        }
        
        headers = {
            "Authorization": f"Basic {self._get_yapily_auth()}",
            "Content-Type": "application/json"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.yapily_base_url}/account-auth-requests",
                json=payload,
                headers=headers
            ) as response:
                result = await response.json()
                
                if response.status == 201:
                    consent_id = result["id"]
                    auth_url = result["authorisationUrl"]
                    
                    # Store consent
                    self.consent_cache[consent_id] = {
                        "user_id": user_id,
                        "institution_id": institution_id,
                        "permissions": permissions,
                        "status": "pending",
                        "created_at": datetime.utcnow().isoformat()
                    }
                    
                    return {
                        "consent_id": consent_id,
                        "authorization_url": auth_url,
                        "expires_at": result.get("expiresAt")
                    }
                else:
                    raise Exception(f"PSD2 error: {result.get('message')}")
    
    async def get_psd2_accounts(
        self,
        user_id: str,
        consent_token: str
    ) -> List[BankAccount]:
        """
        Get accounts via PSD2
        
        Args:
            user_id: User identifier
            consent_token: Consent token
            
        Returns:
            List of bank accounts
        """
        headers = {
            "Authorization": f"Bearer {consent_token}",
            "Content-Type": "application/json"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.yapily_base_url}/accounts",
                headers=headers
            ) as response:
                result = await response.json()
                
                if response.status == 200:
                    accounts = []
                    
                    for acc in result.get("data", []):
                        account = BankAccount(
                            account_id=acc["id"],
                            user_id=user_id,
                            provider="yapily_psd2",
                            institution_id=acc.get("institutionId", ""),
                            institution_name=acc.get("institutionName", ""),
                            account_type=acc.get("accountType", "unknown"),
                            account_number_masked=acc.get("accountIdentifications", [{}])[0].get("identification", "")[-4:],
                            routing_number=None,
                            iban=next((id["identification"] for id in acc.get("accountIdentifications", []) if id["type"] == "IBAN"), None),
                            swift_code=next((id["identification"] for id in acc.get("accountIdentifications", []) if id["type"] == "SWIFT"), None),
                            balance=Decimal(str(acc["balance"]["amount"])) if acc.get("balance") else None,
                            currency=acc.get("currency", "EUR"),
                            verification_status=VerificationStatus.VERIFIED.value,
                            linked_at=datetime.utcnow().isoformat(),
                            last_synced=datetime.utcnow().isoformat()
                        )
                        accounts.append(account)
                    
                    return accounts
                else:
                    raise Exception(f"PSD2 error: {result.get('message')}")
    
    def _get_yapily_auth(self) -> str:
        """Get Yapily basic auth"""
        credentials = f"{self.yapily_app_id}:{self.yapily_secret}"
        return base64.b64encode(credentials.encode()).decode()
    
    # ========== Account Aggregation ==========
    
    async def aggregate_accounts(
        self,
        user_id: str
    ) -> Dict:
        """
        Aggregate all linked accounts across providers
        
        Args:
            user_id: User identifier
            
        Returns:
            Aggregated account data
        """
        accounts = self.linked_accounts.get(user_id, [])
        
        # Calculate totals
        total_balance = sum(acc.balance for acc in accounts if acc.balance)
        
        # Group by type
        by_type = {}
        for acc in accounts:
            acc_type = acc.account_type
            if acc_type not in by_type:
                by_type[acc_type] = []
            by_type[acc_type].append(asdict(acc))
        
        # Group by provider
        by_provider = {}
        for acc in accounts:
            provider = acc.provider
            if provider not in by_provider:
                by_provider[provider] = []
            by_provider[provider].append(asdict(acc))
        
        return {
            "user_id": user_id,
            "total_accounts": len(accounts),
            "total_balance": float(total_balance),
            "accounts": [asdict(acc) for acc in accounts],
            "by_type": by_type,
            "by_provider": by_provider,
            "last_updated": datetime.utcnow().isoformat()
        }
    
    async def sync_all_accounts(
        self,
        user_id: str
    ) -> Dict:
        """
        Sync all linked accounts
        
        Args:
            user_id: User identifier
            
        Returns:
            Sync result
        """
        accounts = self.linked_accounts.get(user_id, [])
        synced_count = 0
        failed_count = 0
        
        for account in accounts:
            try:
                if account.provider == BankingProvider.PLAID.value:
                    token_data = self.access_tokens.get(user_id)
                    if token_data:
                        await self.get_plaid_balance(user_id, token_data["access_token"])
                        synced_count += 1
                # Add other providers...
            except Exception as e:
                logger.error(f"Failed to sync account {account.account_id}: {e}")
                failed_count += 1
        
        return {
            "user_id": user_id,
            "total_accounts": len(accounts),
            "synced": synced_count,
            "failed": failed_count,
            "synced_at": datetime.utcnow().isoformat()
        }
    
    # ========== Payment Initiation ==========
    
    async def initiate_payment(
        self,
        user_id: str,
        account_id: str,
        beneficiary_account: str,
        amount: Decimal,
        currency: str,
        reference: str
    ) -> Dict:
        """
        Initiate payment via Open Banking
        
        Args:
            user_id: User identifier
            account_id: Source account ID
            beneficiary_account: Beneficiary account details
            amount: Payment amount
            currency: Currency code
            reference: Payment reference
            
        Returns:
            Payment initiation result
        """
        # This would use PSD2 payment initiation or Plaid Transfer
        payment_id = str(uuid.uuid4())
        
        return {
            "payment_id": payment_id,
            "status": "pending_authorization",
            "authorization_url": f"{self.config.get('app_base_url')}/payments/{payment_id}/authorize",
            "amount": float(amount),
            "currency": currency,
            "initiated_at": datetime.utcnow().isoformat()
        }


# Example usage
if __name__ == "__main__":
    config = {
        "plaid_client_id": "your_client_id",
        "plaid_secret": "your_secret",
        "plaid_env": "sandbox",
        "webhook_base_url": "https://api.yourplatform.com",
        "app_base_url": "https://yourplatform.com"
    }
    
    service = OpenBankingService(config)
    
    async def example() -> None:
        # Create link token
        link_token = await service.create_plaid_link_token("user_123")
        print(f"Link token: {link_token}")
        
        # After user completes Plaid Link, exchange public token
        # access_token_data = await service.exchange_plaid_public_token("user_123", "public-sandbox-xxx")
        
        # Get accounts
        # accounts = await service.get_plaid_accounts("user_123", access_token)
        
        # Verify account
        # verification = await service.verify_account_instantly("user_123", "account_id")
        
        # Aggregate accounts
        # aggregated = await service.aggregate_accounts("user_123")
    
    # asyncio.run(example())

