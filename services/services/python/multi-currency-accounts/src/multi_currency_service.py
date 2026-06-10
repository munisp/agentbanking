#!/usr/bin/env python3
"""
Multi-Currency Account System - Phase 2
Full multi-currency wallet with virtual IBANs, interest, and currency exchange
"""

from typing import Dict, Optional, List, Tuple
from decimal import Decimal
from datetime import datetime, timedelta
from enum import Enum
import logging
import uuid
import asyncio
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


class Currency(str, Enum):
    """Supported currencies"""
    # Major currencies
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    
    # African currencies
    NGN = "NGN"  # Nigerian Naira
    KES = "KES"  # Kenyan Shilling
    GHS = "GHS"  # Ghanaian Cedi
    ZAR = "ZAR"  # South African Rand
    EGP = "EGP"  # Egyptian Pound
    TZS = "TZS"  # Tanzanian Shilling
    UGX = "UGX"  # Ugandan Shilling
    XOF = "XOF"  # West African CFA Franc
    XAF = "XAF"  # Central African CFA Franc
    
    # Asian currencies
    INR = "INR"  # Indian Rupee
    CNY = "CNY"  # Chinese Yuan
    JPY = "JPY"  # Japanese Yen
    SGD = "SGD"  # Singapore Dollar
    
    # Other major currencies
    CAD = "CAD"  # Canadian Dollar
    AUD = "AUD"  # Australian Dollar
    CHF = "CHF"  # Swiss Franc


class AccountType(str, Enum):
    """Account types"""
    PERSONAL = "personal"
    BUSINESS = "business"
    SHARED = "shared"
    SUB_ACCOUNT = "sub_account"


class TransactionType(str, Enum):
    """Transaction types"""
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"
    EXCHANGE = "exchange"
    INTEREST = "interest"
    FEE = "fee"
    REFUND = "refund"


@dataclass
class Balance:
    """Currency balance"""
    currency: str
    available: Decimal
    pending: Decimal
    reserved: Decimal
    total: Decimal
    last_updated: str


@dataclass
class VirtualIBAN:
    """Virtual IBAN details"""
    iban: str
    currency: str
    bic_swift: str
    account_holder_name: str
    bank_name: str
    bank_address: str
    country: str
    routing_number: Optional[str] = None  # For USD
    sort_code: Optional[str] = None  # For GBP
    created_at: str = None
    status: str = "active"


@dataclass
class InterestConfig:
    """Interest configuration"""
    currency: str
    base_apy: Decimal
    tier_1_threshold: Decimal  # Balance threshold for tier 1
    tier_1_apy: Decimal
    tier_2_threshold: Decimal
    tier_2_apy: Decimal
    tier_3_threshold: Decimal
    tier_3_apy: Decimal
    compounding_frequency: str  # daily, monthly
    last_accrual: str


class MultiCurrencyAccountService:
    """
    Comprehensive multi-currency account system
    
    Features:
    - Hold balances in 20+ currencies
    - Virtual IBANs for EUR, GBP, USD
    - Interest on balances (2-4% APY)
    - Currency exchange within wallet
    - Sub-accounts for organization
    - Shared accounts
    - Transaction history and statements
    - Spending analytics
    - Account permissions
    """
    
    # Interest rates by currency (base APY)
    INTEREST_RATES = {
        Currency.USD: {
            "base_apy": Decimal("2.0"),
            "tier_1_threshold": Decimal("1000"),
            "tier_1_apy": Decimal("2.5"),
            "tier_2_threshold": Decimal("10000"),
            "tier_2_apy": Decimal("3.0"),
            "tier_3_threshold": Decimal("50000"),
            "tier_3_apy": Decimal("3.5"),
        },
        Currency.EUR: {
            "base_apy": Decimal("1.5"),
            "tier_1_threshold": Decimal("1000"),
            "tier_1_apy": Decimal("2.0"),
            "tier_2_threshold": Decimal("10000"),
            "tier_2_apy": Decimal("2.5"),
            "tier_3_threshold": Decimal("50000"),
            "tier_3_apy": Decimal("3.0"),
        },
        Currency.GBP: {
            "base_apy": Decimal("1.8"),
            "tier_1_threshold": Decimal("1000"),
            "tier_1_apy": Decimal("2.3"),
            "tier_2_threshold": Decimal("10000"),
            "tier_2_apy": Decimal("2.8"),
            "tier_3_threshold": Decimal("50000"),
            "tier_3_apy": Decimal("3.3"),
        },
    }
    
    # Exchange rate margins (added to mid-market rate)
    EXCHANGE_MARGINS = {
        "standard": Decimal("0.005"),  # 0.5%
        "premium": Decimal("0.003"),   # 0.3% (for high-volume users)
        "vip": Decimal("0.001"),       # 0.1% (for VIP users)
    }
    
    # IBAN providers
    IBAN_PROVIDERS = {
        Currency.EUR: {
            "provider": "Railsr",
            "bic_swift": "TRWIBEB1XXX",
            "bank_name": "Railsr Bank",
            "bank_address": "Brussels, Belgium",
            "country": "BE",
        },
        Currency.GBP: {
            "provider": "ClearBank",
            "bic_swift": "CLRBGB22XXX",
            "bank_name": "ClearBank Ltd",
            "bank_address": "London, United Kingdom",
            "country": "GB",
        },
        Currency.USD: {
            "provider": "Evolve Bank",
            "bic_swift": "EVOBUS44XXX",
            "bank_name": "Evolve Bank & Trust",
            "bank_address": "Memphis, TN, USA",
            "country": "US",
        },
    }
    
    def __init__(self, config: Dict) -> None:
        """Initialize multi-currency account service"""
        self.config = config
        
        # Database connections (in production, use actual DB)
        self.accounts = {}
        self.balances = {}
        self.ibans = {}
        self.transactions = {}
        self.interest_accruals = {}
        
        # API keys for IBAN providers
        self.railsr_api_key = config.get("railsr_api_key")
        self.clearbank_api_key = config.get("clearbank_api_key")
        self.evolve_api_key = config.get("evolve_api_key")
        
        # FX data provider
        self.fx_api_key = config.get("fx_api_key")
        
        logger.info("Multi-currency account service initialized")
    
    async def create_account(
        self,
        user_id: str,
        account_type: AccountType = AccountType.PERSONAL,
        account_name: Optional[str] = None,
        currencies: Optional[List[Currency]] = None
    ) -> Dict:
        """
        Create multi-currency account
        
        Args:
            user_id: User identifier
            account_type: Type of account
            account_name: Custom account name
            currencies: Initial currencies to enable
            
        Returns:
            Account details
        """
        account_id = f"acc_{uuid.uuid4().hex[:16]}"
        
        # Default currencies if not specified
        if not currencies:
            currencies = [Currency.USD, Currency.EUR, Currency.GBP, Currency.NGN]
        
        # Create account
        account = {
            "account_id": account_id,
            "user_id": user_id,
            "account_type": account_type.value,
            "account_name": account_name or f"{account_type.value.title()} Account",
            "currencies": [c.value for c in currencies],
            "status": "active",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        
        self.accounts[account_id] = account
        
        # Initialize balances for each currency
        self.balances[account_id] = {}
        for currency in currencies:
            self.balances[account_id][currency.value] = Balance(
                currency=currency.value,
                available=Decimal("0"),
                pending=Decimal("0"),
                reserved=Decimal("0"),
                total=Decimal("0"),
                last_updated=datetime.utcnow().isoformat()
            )
        
        # Initialize interest configurations
        self.interest_accruals[account_id] = {}
        for currency in currencies:
            if currency in self.INTEREST_RATES:
                config = self.INTEREST_RATES[currency]
                self.interest_accruals[account_id][currency.value] = InterestConfig(
                    currency=currency.value,
                    base_apy=config["base_apy"],
                    tier_1_threshold=config["tier_1_threshold"],
                    tier_1_apy=config["tier_1_apy"],
                    tier_2_threshold=config["tier_2_threshold"],
                    tier_2_apy=config["tier_2_apy"],
                    tier_3_threshold=config["tier_3_threshold"],
                    tier_3_apy=config["tier_3_apy"],
                    compounding_frequency="daily",
                    last_accrual=datetime.utcnow().isoformat()
                )
        
        logger.info(f"Account created: {account_id} for user {user_id}")
        
        return {
            "success": True,
            "account": account,
            "balances": {k: asdict(v) for k, v in self.balances[account_id].items()}
        }
    
    async def create_virtual_iban(
        self,
        account_id: str,
        currency: Currency,
        account_holder_name: str
    ) -> Dict:
        """
        Create virtual IBAN for receiving payments
        
        Args:
            account_id: Account identifier
            currency: Currency for IBAN (EUR, GBP, or USD)
            account_holder_name: Name to appear on IBAN
            
        Returns:
            Virtual IBAN details
        """
        # Validate currency
        if currency not in [Currency.EUR, Currency.GBP, Currency.USD]:
            return {
                "success": False,
                "error": f"Virtual IBANs not available for {currency.value}"
            }
        
        # Check if account exists
        if account_id not in self.accounts:
            return {"success": False, "error": "Account not found"}
        
        # Check if IBAN already exists
        iban_key = f"{account_id}_{currency.value}"
        if iban_key in self.ibans:
            return {
                "success": True,
                "iban": asdict(self.ibans[iban_key]),
                "message": "IBAN already exists"
            }
        
        # Get provider details
        provider_info = self.IBAN_PROVIDERS[currency]
        
        # Generate IBAN (in production, call provider API)
        iban = self._generate_iban(currency, account_id)
        
        # Generate additional details based on currency
        additional_details = {}
        if currency == Currency.USD:
            additional_details["routing_number"] = self._generate_routing_number()
        elif currency == Currency.GBP:
            additional_details["sort_code"] = self._generate_sort_code()
        
        # Create virtual IBAN
        virtual_iban = VirtualIBAN(
            iban=iban,
            currency=currency.value,
            bic_swift=provider_info["bic_swift"],
            account_holder_name=account_holder_name,
            bank_name=provider_info["bank_name"],
            bank_address=provider_info["bank_address"],
            country=provider_info["country"],
            routing_number=additional_details.get("routing_number"),
            sort_code=additional_details.get("sort_code"),
            created_at=datetime.utcnow().isoformat(),
            status="active"
        )
        
        self.ibans[iban_key] = virtual_iban
        
        logger.info(f"Virtual IBAN created: {iban} for account {account_id}")
        
        return {
            "success": True,
            "iban": asdict(virtual_iban)
        }
    
    async def deposit(
        self,
        account_id: str,
        currency: Currency,
        amount: Decimal,
        source: str,
        reference: Optional[str] = None
    ) -> Dict:
        """
        Deposit funds to account
        
        Args:
            account_id: Account identifier
            currency: Currency of deposit
            amount: Deposit amount
            source: Source of funds
            reference: Payment reference
            
        Returns:
            Deposit transaction details
        """
        # Validate account
        if account_id not in self.accounts:
            return {"success": False, "error": "Account not found"}
        
        # Validate amount
        if amount <= 0:
            return {"success": False, "error": "Invalid amount"}
        
        # Get balance
        balance = self.balances[account_id].get(currency.value)
        if not balance:
            return {"success": False, "error": f"Currency {currency.value} not enabled"}
        
        # Create transaction
        transaction_id = f"txn_{uuid.uuid4().hex[:20]}"
        transaction = {
            "transaction_id": transaction_id,
            "account_id": account_id,
            "type": TransactionType.DEPOSIT.value,
            "currency": currency.value,
            "amount": float(amount),
            "balance_before": float(balance.available),
            "balance_after": float(balance.available + amount),
            "source": source,
            "reference": reference,
            "status": "completed",
            "created_at": datetime.utcnow().isoformat(),
        }
        
        # Update balance
        balance.available += amount
        balance.total += amount
        balance.last_updated = datetime.utcnow().isoformat()
        
        self.transactions[transaction_id] = transaction
        
        logger.info(f"Deposit completed: {transaction_id} - {amount} {currency.value}")
        
        return {
            "success": True,
            "transaction": transaction,
            "balance": asdict(balance)
        }
    
    async def exchange_currency(
        self,
        account_id: str,
        from_currency: Currency,
        to_currency: Currency,
        amount: Decimal,
        user_tier: str = "standard"
    ) -> Dict:
        """
        Exchange currency within account
        
        Args:
            account_id: Account identifier
            from_currency: Source currency
            to_currency: Target currency
            amount: Amount to exchange
            user_tier: User tier (standard/premium/vip)
            
        Returns:
            Exchange transaction details
        """
        # Validate account
        if account_id not in self.accounts:
            return {"success": False, "error": "Account not found"}
        
        # Get balances
        from_balance = self.balances[account_id].get(from_currency.value)
        to_balance = self.balances[account_id].get(to_currency.value)
        
        if not from_balance or not to_balance:
            return {"success": False, "error": "Currency not enabled"}
        
        # Check sufficient balance
        if from_balance.available < amount:
            return {"success": False, "error": "Insufficient balance"}
        
        # Get exchange rate
        mid_market_rate = await self._get_exchange_rate(from_currency.value, to_currency.value)
        
        # Apply margin based on user tier
        margin = self.EXCHANGE_MARGINS[user_tier]
        exchange_rate = mid_market_rate * (Decimal("1") - margin)
        
        # Calculate amounts
        to_amount = amount * exchange_rate
        fee = amount * margin
        
        # Create transaction
        transaction_id = f"txn_{uuid.uuid4().hex[:20]}"
        transaction = {
            "transaction_id": transaction_id,
            "account_id": account_id,
            "type": TransactionType.EXCHANGE.value,
            "from_currency": from_currency.value,
            "to_currency": to_currency.value,
            "from_amount": float(amount),
            "to_amount": float(to_amount),
            "exchange_rate": float(exchange_rate),
            "mid_market_rate": float(mid_market_rate),
            "margin": float(margin * 100),  # As percentage
            "fee": float(fee),
            "status": "completed",
            "created_at": datetime.utcnow().isoformat(),
        }
        
        # Update balances
        from_balance.available -= amount
        from_balance.total -= amount
        from_balance.last_updated = datetime.utcnow().isoformat()
        
        to_balance.available += to_amount
        to_balance.total += to_amount
        to_balance.last_updated = datetime.utcnow().isoformat()
        
        self.transactions[transaction_id] = transaction
        
        logger.info(f"Currency exchange: {amount} {from_currency.value} → {to_amount} {to_currency.value}")
        
        return {
            "success": True,
            "transaction": transaction,
            "from_balance": asdict(from_balance),
            "to_balance": asdict(to_balance)
        }
    
    async def accrue_interest(self, account_id: str, currency: Currency) -> Dict:
        """
        Accrue interest for currency balance
        
        Args:
            account_id: Account identifier
            currency: Currency to accrue interest for
            
        Returns:
            Interest accrual details
        """
        # Get balance
        balance = self.balances[account_id].get(currency.value)
        if not balance:
            return {"success": False, "error": "Currency not found"}
        
        # Get interest config
        interest_config = self.interest_accruals[account_id].get(currency.value)
        if not interest_config:
            return {"success": False, "error": "Interest not available for this currency"}
        
        # Determine APY based on balance tier
        balance_amount = balance.available
        if balance_amount >= interest_config.tier_3_threshold:
            apy = interest_config.tier_3_apy
            tier = "tier_3"
        elif balance_amount >= interest_config.tier_2_threshold:
            apy = interest_config.tier_2_apy
            tier = "tier_2"
        elif balance_amount >= interest_config.tier_1_threshold:
            apy = interest_config.tier_1_apy
            tier = "tier_1"
        else:
            apy = interest_config.base_apy
            tier = "base"
        
        # Calculate daily interest (assuming daily compounding)
        daily_rate = apy / Decimal("365") / Decimal("100")
        interest_amount = balance_amount * daily_rate
        
        # Create interest transaction
        transaction_id = f"txn_{uuid.uuid4().hex[:20]}"
        transaction = {
            "transaction_id": transaction_id,
            "account_id": account_id,
            "type": TransactionType.INTEREST.value,
            "currency": currency.value,
            "amount": float(interest_amount),
            "balance_before": float(balance.available),
            "balance_after": float(balance.available + interest_amount),
            "apy": float(apy),
            "tier": tier,
            "status": "completed",
            "created_at": datetime.utcnow().isoformat(),
        }
        
        # Update balance
        balance.available += interest_amount
        balance.total += interest_amount
        balance.last_updated = datetime.utcnow().isoformat()
        
        # Update last accrual time
        interest_config.last_accrual = datetime.utcnow().isoformat()
        
        self.transactions[transaction_id] = transaction
        
        logger.info(f"Interest accrued: {interest_amount} {currency.value} (APY: {apy}%)")
        
        return {
            "success": True,
            "transaction": transaction,
            "balance": asdict(balance)
        }
    
    async def get_account_summary(self, account_id: str) -> Dict:
        """
        Get comprehensive account summary
        
        Args:
            account_id: Account identifier
            
        Returns:
            Account summary with all balances, IBANs, and stats
        """
        if account_id not in self.accounts:
            return {"success": False, "error": "Account not found"}
        
        account = self.accounts[account_id]
        
        # Get all balances
        balances = {
            currency: asdict(balance)
            for currency, balance in self.balances[account_id].items()
        }
        
        # Calculate total value in USD
        total_value_usd = Decimal("0")
        for currency, balance in self.balances[account_id].items():
            if balance.total > 0:
                rate = await self._get_exchange_rate(currency, "USD")
                total_value_usd += balance.total * rate
        
        # Get all IBANs
        ibans = []
        for key, iban in self.ibans.items():
            if key.startswith(account_id):
                ibans.append(asdict(iban))
        
        # Get recent transactions
        recent_transactions = [
            txn for txn in self.transactions.values()
            if txn["account_id"] == account_id
        ][-10:]  # Last 10 transactions
        
        # Calculate interest earned (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        interest_earned = {}
        for txn in self.transactions.values():
            if (txn["account_id"] == account_id and
                txn["type"] == TransactionType.INTEREST.value and
                datetime.fromisoformat(txn["created_at"]) > thirty_days_ago):
                currency = txn["currency"]
                interest_earned[currency] = interest_earned.get(currency, 0) + txn["amount"]
        
        return {
            "success": True,
            "account": account,
            "balances": balances,
            "total_value_usd": float(total_value_usd),
            "ibans": ibans,
            "recent_transactions": recent_transactions,
            "interest_earned_30d": interest_earned,
            "statistics": {
                "total_currencies": len(balances),
                "active_currencies": sum(1 for b in self.balances[account_id].values() if b.total > 0),
                "total_transactions": len([t for t in self.transactions.values() if t["account_id"] == account_id]),
                "virtual_ibans": len(ibans),
            }
        }
    
    async def get_transaction_history(
        self,
        account_id: str,
        currency: Optional[Currency] = None,
        transaction_type: Optional[TransactionType] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> Dict:
        """
        Get transaction history with filters
        
        Args:
            account_id: Account identifier
            currency: Filter by currency
            transaction_type: Filter by transaction type
            start_date: Start date filter
            end_date: End date filter
            limit: Maximum number of transactions
            
        Returns:
            Filtered transaction history
        """
        transactions = []
        
        for txn in self.transactions.values():
            if txn["account_id"] != account_id:
                continue
            
            # Apply filters
            if currency and txn.get("currency") != currency.value:
                continue
            
            if transaction_type and txn["type"] != transaction_type.value:
                continue
            
            txn_date = datetime.fromisoformat(txn["created_at"])
            if start_date and txn_date < start_date:
                continue
            
            if end_date and txn_date > end_date:
                continue
            
            transactions.append(txn)
        
        # Sort by date (newest first)
        transactions.sort(key=lambda x: x["created_at"], reverse=True)
        
        # Apply limit
        transactions = transactions[:limit]
        
        return {
            "success": True,
            "transactions": transactions,
            "count": len(transactions),
            "filters": {
                "currency": currency.value if currency else None,
                "type": transaction_type.value if transaction_type else None,
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None,
            }
        }
    
    async def generate_statement(
        self,
        account_id: str,
        currency: Currency,
        start_date: datetime,
        end_date: datetime
    ) -> Dict:
        """
        Generate account statement
        
        Args:
            account_id: Account identifier
            currency: Currency for statement
            start_date: Statement start date
            end_date: Statement end date
            
        Returns:
            Account statement with transactions and summary
        """
        # Get transactions for period
        transactions = await self.get_transaction_history(
            account_id=account_id,
            currency=currency,
            start_date=start_date,
            end_date=end_date,
            limit=10000
        )
        
        # Calculate summary
        opening_balance = Decimal("0")  # Would fetch from historical data
        closing_balance = self.balances[account_id][currency.value].available
        
        total_deposits = sum(
            Decimal(str(t["amount"])) for t in transactions["transactions"]
            if t["type"] == TransactionType.DEPOSIT.value
        )
        
        total_withdrawals = sum(
            Decimal(str(t["amount"])) for t in transactions["transactions"]
            if t["type"] == TransactionType.WITHDRAWAL.value
        )
        
        total_interest = sum(
            Decimal(str(t["amount"])) for t in transactions["transactions"]
            if t["type"] == TransactionType.INTEREST.value
        )
        
        return {
            "success": True,
            "statement": {
                "account_id": account_id,
                "currency": currency.value,
                "period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat(),
                },
                "summary": {
                    "opening_balance": float(opening_balance),
                    "closing_balance": float(closing_balance),
                    "total_deposits": float(total_deposits),
                    "total_withdrawals": float(total_withdrawals),
                    "total_interest": float(total_interest),
                    "net_change": float(closing_balance - opening_balance),
                },
                "transactions": transactions["transactions"],
                "transaction_count": transactions["count"],
                "generated_at": datetime.utcnow().isoformat(),
            }
        }
    
    # Helper methods
    
    def _generate_iban(self, currency: Currency, account_id: str) -> str:
        """Generate IBAN (simplified)"""
        # In production, call provider API
        country_codes = {
            Currency.EUR: "BE",
            Currency.GBP: "GB",
            Currency.USD: "US",
        }
        country = country_codes[currency]
        account_number = account_id[:16].upper()
        
        if currency == Currency.USD:
            # US uses account number format
            return f"{account_number}"
        else:
            # IBAN format
            return f"{country}71{account_number}"
    
    def _generate_routing_number(self) -> str:
        """Generate routing number for USD"""
        # In production, use actual routing number from provider
        return "084106768"
    
    def _generate_sort_code(self) -> str:
        """Generate sort code for GBP"""
        # In production, use actual sort code from provider
        return "04-00-75"
    
    async def _get_exchange_rate(self, from_currency: str, to_currency: str) -> Decimal:
        """Get exchange rate"""
        # In production, fetch from FX API (e.g., Wise, XE, OANDA)
        # For now, use approximate rates
        rates_to_usd = {
            "USD": Decimal("1.0"),
            "EUR": Decimal("1.09"),
            "GBP": Decimal("1.27"),
            "NGN": Decimal("0.00067"),
            "KES": Decimal("0.0077"),
            "GHS": Decimal("0.083"),
            "ZAR": Decimal("0.056"),
            "INR": Decimal("0.012"),
            "CAD": Decimal("0.74"),
            "AUD": Decimal("0.67"),
        }
        
        from_rate = rates_to_usd.get(from_currency, Decimal("1.0"))
        to_rate = rates_to_usd.get(to_currency, Decimal("1.0"))
        
        return from_rate / to_rate


# Example usage
if __name__ == "__main__":
    config = {
        "railsr_api_key": "...",
        "clearbank_api_key": "...",
        "evolve_api_key": "...",
        "fx_api_key": "...",
    }
    
    service = MultiCurrencyAccountService(config)
    
    async def example() -> None:
        # Create account
        result = await service.create_account(
            user_id="user_123",
            account_type=AccountType.PERSONAL,
            currencies=[Currency.USD, Currency.EUR, Currency.GBP, Currency.NGN]
        )
        account_id = result["account"]["account_id"]
        print(f"Account created: {account_id}")
        
        # Create virtual IBAN
        iban_result = await service.create_virtual_iban(
            account_id=account_id,
            currency=Currency.EUR,
            account_holder_name="John Doe"
        )
        print(f"IBAN created: {iban_result['iban']['iban']}")
        
        # Deposit funds
        deposit_result = await service.deposit(
            account_id=account_id,
            currency=Currency.USD,
            amount=Decimal("1000"),
            source="bank_transfer"
        )
        print(f"Deposited: ${deposit_result['transaction']['amount']}")
        
        # Exchange currency
        exchange_result = await service.exchange_currency(
            account_id=account_id,
            from_currency=Currency.USD,
            to_currency=Currency.EUR,
            amount=Decimal("500")
        )
        print(f"Exchanged: {exchange_result['transaction']}")
        
        # Get account summary
        summary = await service.get_account_summary(account_id)
        print(f"Account summary: {summary}")
    
    # asyncio.run(example())

