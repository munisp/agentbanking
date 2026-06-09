"""
Investment Integration Service

Enables savings accounts and micro-investment features

Features:
- High-yield savings accounts
- Round-up micro-investments
- Goal-based savings
- Auto-invest
- Portfolio tracking
"""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional

import httpx


class AccountType(Enum):
    """Investment account type"""
    SAVINGS = "SAVINGS"
    INVESTMENT = "INVESTMENT"
    GOAL = "GOAL"


class InvestmentStrategy(Enum):
    """Investment strategy"""
    CONSERVATIVE = "CONSERVATIVE"  # Low risk, low return
    MODERATE = "MODERATE"  # Balanced risk/return
    AGGRESSIVE = "AGGRESSIVE"  # High risk, high return


class GoalStatus(Enum):
    """Savings goal status"""
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class InvestmentService:
    """
    Investment Integration Service
    
    Provides savings and investment features
    
    Features:
    - Savings accounts (3-5% APY)
    - Micro-investments (round-ups)
    - Goal-based savings
    - Auto-invest from transactions
    - Portfolio management
    """
    
    def __init__(
        self,
        investment_provider_url: str,
        api_key: str,
        api_secret: str
    ):
        """
        Initialize investment service
        
        Args:
            investment_provider_url: Investment provider API endpoint
            api_key: API key
            api_secret: API secret
        """
        self.provider_url = investment_provider_url
        self.api_key = api_key
        self.api_secret = api_secret
        
        self.client: Optional[httpx.AsyncClient] = None
        
        # In-memory storage
        self._accounts: Dict[str, Dict] = {}
        self._goals: Dict[str, Dict] = {}
        self._transactions: Dict[str, List[Dict]] = {}
    
    async def __aenter__(self):
        self.client = httpx.AsyncClient(timeout=30)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()
    
    async def create_savings_account(
        self,
        account_id: str,
        user_id: str,
        currency: str,
        interest_rate: Decimal = Decimal("0.04")  # 4% APY default
    ) -> Dict:
        """
        Create savings account
        
        Args:
            account_id: Unique account ID
            user_id: User ID
            currency: Currency code
            interest_rate: Annual interest rate (e.g., 0.04 = 4%)
            
        Returns:
            Account creation result
        """
        account = {
            "account_id": account_id,
            "user_id": user_id,
            "type": AccountType.SAVINGS.value,
            "currency": currency,
            "balance": 0.0,
            "interest_rate": float(interest_rate),
            "interest_earned": 0.0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_interest_calculation": datetime.now(timezone.utc).isoformat()
        }
        
        self._accounts[account_id] = account
        self._transactions[account_id] = []
        
        return {
            "status": "SUCCESS",
            "account_id": account_id,
            "interest_rate": float(interest_rate),
            "message": f"Savings account created with {float(interest_rate) * 100}% APY"
        }
    
    async def create_investment_account(
        self,
        account_id: str,
        user_id: str,
        currency: str,
        strategy: InvestmentStrategy,
        auto_invest_enabled: bool = False,
        auto_invest_percentage: Optional[Decimal] = None
    ) -> Dict:
        """
        Create investment account
        
        Args:
            account_id: Unique account ID
            user_id: User ID
            currency: Currency code
            strategy: Investment strategy
            auto_invest_enabled: Enable auto-invest from transactions
            auto_invest_percentage: % of transactions to auto-invest
            
        Returns:
            Account creation result
        """
        # Get expected returns based on strategy
        expected_returns = {
            InvestmentStrategy.CONSERVATIVE: Decimal("0.06"),  # 6%
            InvestmentStrategy.MODERATE: Decimal("0.10"),  # 10%
            InvestmentStrategy.AGGRESSIVE: Decimal("0.15")  # 15%
        }
        
        account = {
            "account_id": account_id,
            "user_id": user_id,
            "type": AccountType.INVESTMENT.value,
            "currency": currency,
            "balance": 0.0,
            "invested_amount": 0.0,
            "current_value": 0.0,
            "returns": 0.0,
            "strategy": strategy.value,
            "expected_annual_return": float(expected_returns[strategy]),
            "auto_invest_enabled": auto_invest_enabled,
            "auto_invest_percentage": float(auto_invest_percentage) if auto_invest_percentage else None,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        self._accounts[account_id] = account
        self._transactions[account_id] = []
        
        return {
            "status": "SUCCESS",
            "account_id": account_id,
            "strategy": strategy.value,
            "expected_return": float(expected_returns[strategy]) * 100,
            "message": f"Investment account created with {strategy.value} strategy"
        }
    
    async def create_savings_goal(
        self,
        goal_id: str,
        user_id: str,
        title: str,
        description: str,
        target_amount: Decimal,
        currency: str,
        target_date: str,
        auto_contribute_amount: Optional[Decimal] = None,
        auto_contribute_frequency: Optional[str] = None  # "DAILY", "WEEKLY", "MONTHLY"
    ) -> Dict:
        """
        Create savings goal
        
        Args:
            goal_id: Unique goal ID
            user_id: User ID
            title: Goal title (e.g., "Vacation Fund")
            description: Goal description
            target_amount: Target amount to save
            currency: Currency code
            target_date: Target date (ISO format)
            auto_contribute_amount: Auto-contribution amount
            auto_contribute_frequency: Auto-contribution frequency
            
        Returns:
            Goal creation result
        """
        # Calculate days until target
        target_dt = datetime.fromisoformat(target_date.replace('Z', '+00:00'))
        days_remaining = (target_dt - datetime.now(timezone.utc)).days
        
        # Calculate recommended monthly contribution
        months_remaining = max(1, days_remaining / 30)
        recommended_monthly = target_amount / Decimal(str(months_remaining))
        
        goal = {
            "goal_id": goal_id,
            "user_id": user_id,
            "title": title,
            "description": description,
            "target_amount": float(target_amount),
            "current_amount": 0.0,
            "currency": currency,
            "target_date": target_date,
            "status": GoalStatus.ACTIVE.value,
            "auto_contribute_amount": float(auto_contribute_amount) if auto_contribute_amount else None,
            "auto_contribute_frequency": auto_contribute_frequency,
            "recommended_monthly_contribution": float(recommended_monthly),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": None
        }
        
        self._goals[goal_id] = goal
        
        return {
            "status": "SUCCESS",
            "goal_id": goal_id,
            "recommended_monthly_contribution": float(recommended_monthly),
            "days_remaining": days_remaining
        }
    
    async def deposit(
        self,
        account_id: str,
        amount: Decimal,
        source: str = "manual"
    ) -> Dict:
        """Deposit funds to account"""
        if account_id not in self._accounts:
            return {"status": "NOT_FOUND"}
        
        account = self._accounts[account_id]
        
        # Update balance
        account["balance"] += float(amount)
        
        if account["type"] == AccountType.INVESTMENT.value:
            account["invested_amount"] += float(amount)
            account["current_value"] = account["invested_amount"]  # Simplified
        
        # Record transaction
        transaction = {
            "transaction_id": str(uuid.uuid4()),
            "type": "DEPOSIT",
            "amount": float(amount),
            "source": source,
            "balance_after": account["balance"],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        self._transactions[account_id].append(transaction)
        
        return {
            "status": "SUCCESS",
            "account_id": account_id,
            "new_balance": account["balance"],
            "transaction_id": transaction["transaction_id"]
        }
    
    async def withdraw(
        self,
        account_id: str,
        amount: Decimal
    ) -> Dict:
        """Withdraw funds from account"""
        if account_id not in self._accounts:
            return {"status": "NOT_FOUND"}
        
        account = self._accounts[account_id]
        
        if account["balance"] < float(amount):
            return {
                "status": "REJECTED",
                "reason": "Insufficient balance"
            }
        
        # Update balance
        account["balance"] -= float(amount)
        
        # Record transaction
        transaction = {
            "transaction_id": str(uuid.uuid4()),
            "type": "WITHDRAWAL",
            "amount": float(amount),
            "balance_after": account["balance"],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        self._transactions[account_id].append(transaction)
        
        return {
            "status": "SUCCESS",
            "account_id": account_id,
            "new_balance": account["balance"],
            "transaction_id": transaction["transaction_id"]
        }
    
    async def contribute_to_goal(
        self,
        goal_id: str,
        amount: Decimal
    ) -> Dict:
        """Contribute to savings goal"""
        if goal_id not in self._goals:
            return {"status": "NOT_FOUND"}
        
        goal = self._goals[goal_id]
        
        if goal["status"] != GoalStatus.ACTIVE.value:
            return {
                "status": "REJECTED",
                "reason": f"Goal is {goal['status']}"
            }
        
        # Update goal
        goal["current_amount"] += float(amount)
        
        # Check if goal completed
        if goal["current_amount"] >= goal["target_amount"]:
            goal["status"] = GoalStatus.COMPLETED.value
            goal["completed_at"] = datetime.now(timezone.utc).isoformat()
        
        progress = (goal["current_amount"] / goal["target_amount"]) * 100
        
        return {
            "status": "SUCCESS",
            "goal_id": goal_id,
            "current_amount": goal["current_amount"],
            "target_amount": goal["target_amount"],
            "progress_percentage": progress,
            "completed": goal["status"] == GoalStatus.COMPLETED.value
        }
    
    async def enable_round_up(
        self,
        user_id: str,
        investment_account_id: str
    ) -> Dict:
        """
        Enable round-up micro-investments
        
        Round up transactions to nearest dollar and invest difference
        """
        if investment_account_id not in self._accounts:
            return {"status": "NOT_FOUND"}
        
        account = self._accounts[investment_account_id]
        
        if account["type"] != AccountType.INVESTMENT.value:
            return {
                "status": "REJECTED",
                "reason": "Must be an investment account"
            }
        
        account["round_up_enabled"] = True
        
        return {
            "status": "SUCCESS",
            "message": "Round-up enabled. Transaction amounts will be rounded up and difference invested."
        }
    
    async def process_round_up(
        self,
        account_id: str,
        transaction_amount: Decimal
    ) -> Dict:
        """Process round-up for a transaction"""
        if account_id not in self._accounts:
            return {"status": "NOT_FOUND"}
        
        account = self._accounts[account_id]
        
        if not account.get("round_up_enabled"):
            return {"status": "NOT_ENABLED"}
        
        # Calculate round-up amount
        rounded = Decimal(str(int(transaction_amount) + 1))
        round_up_amount = rounded - transaction_amount
        
        if round_up_amount > 0:
            # Invest round-up amount
            await self.deposit(
                account_id=account_id,
                amount=round_up_amount,
                source="round_up"
            )
            
            return {
                "status": "SUCCESS",
                "transaction_amount": float(transaction_amount),
                "rounded_amount": float(rounded),
                "invested_amount": float(round_up_amount)
            }
        
        return {"status": "NO_ROUND_UP"}
    
    async def calculate_interest(self, account_id: str) -> Dict:
        """Calculate and apply interest for savings account"""
        if account_id not in self._accounts:
            return {"status": "NOT_FOUND"}
        
        account = self._accounts[account_id]
        
        if account["type"] != AccountType.SAVINGS.value:
            return {
                "status": "REJECTED",
                "reason": "Only for savings accounts"
            }
        
        # Calculate daily interest
        daily_rate = Decimal(str(account["interest_rate"])) / 365
        interest = Decimal(str(account["balance"])) * daily_rate
        
        # Apply interest
        account["balance"] += float(interest)
        account["interest_earned"] += float(interest)
        account["last_interest_calculation"] = datetime.now(timezone.utc).isoformat()
        
        # Record transaction
        transaction = {
            "transaction_id": str(uuid.uuid4()),
            "type": "INTEREST",
            "amount": float(interest),
            "balance_after": account["balance"],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        self._transactions[account_id].append(transaction)
        
        return {
            "status": "SUCCESS",
            "interest_earned": float(interest),
            "new_balance": account["balance"],
            "total_interest_earned": account["interest_earned"]
        }
    
    async def get_account(self, account_id: str) -> Optional[Dict]:
        """Get account details"""
        return self._accounts.get(account_id)
    
    async def get_goal(self, goal_id: str) -> Optional[Dict]:
        """Get goal details"""
        return self._goals.get(goal_id)
    
    async def get_user_accounts(self, user_id: str) -> List[Dict]:
        """Get all accounts for user"""
        return [
            account for account in self._accounts.values()
            if account["user_id"] == user_id
        ]
    
    async def get_user_goals(self, user_id: str) -> List[Dict]:
        """Get all goals for user"""
        return [
            goal for goal in self._goals.values()
            if goal["user_id"] == user_id
        ]
    
    async def get_portfolio_summary(self, user_id: str) -> Dict:
        """Get portfolio summary for user"""
        accounts = await self.get_user_accounts(user_id)
        goals = await self.get_user_goals(user_id)
        
        total_savings = sum(
            acc["balance"] for acc in accounts
            if acc["type"] == AccountType.SAVINGS.value
        )
        
        total_invested = sum(
            acc["invested_amount"] for acc in accounts
            if acc["type"] == AccountType.INVESTMENT.value
        )
        
        total_investment_value = sum(
            acc["current_value"] for acc in accounts
            if acc["type"] == AccountType.INVESTMENT.value
        )
        
        total_returns = total_investment_value - total_invested
        
        total_goals_target = sum(goal["target_amount"] for goal in goals)
        total_goals_current = sum(goal["current_amount"] for goal in goals)
        
        return {
            "user_id": user_id,
            "savings": {
                "total_balance": total_savings,
                "accounts_count": len([a for a in accounts if a["type"] == AccountType.SAVINGS.value])
            },
            "investments": {
                "total_invested": total_invested,
                "current_value": total_investment_value,
                "total_returns": total_returns,
                "return_percentage": (total_returns / total_invested * 100) if total_invested > 0 else 0,
                "accounts_count": len([a for a in accounts if a["type"] == AccountType.INVESTMENT.value])
            },
            "goals": {
                "total_target": total_goals_target,
                "total_saved": total_goals_current,
                "progress_percentage": (total_goals_current / total_goals_target * 100) if total_goals_target > 0 else 0,
                "active_goals": len([g for g in goals if g["status"] == GoalStatus.ACTIVE.value]),
                "completed_goals": len([g for g in goals if g["status"] == GoalStatus.COMPLETED.value])
            },
            "total_net_worth": total_savings + total_investment_value + total_goals_current
        }
