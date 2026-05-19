#!/usr/bin/env python3
"""
Loyalty and Referral Rewards Service
Implements tiered loyalty program and referral bonuses
"""

from enum import Enum
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from decimal import Decimal
import logging
import uuid

logger = logging.getLogger(__name__)


class LoyaltyTier(str, Enum):
    """Loyalty program tiers"""
    BRONZE = "bronze"      # 0-10 transactions
    SILVER = "silver"      # 11-50 transactions
    GOLD = "gold"          # 51-100 transactions
    PLATINUM = "platinum"  # 100+ transactions


class RewardType(str, Enum):
    """Types of rewards"""
    CASHBACK = "cashback"
    REFERRAL_BONUS = "referral_bonus"
    MILESTONE_BONUS = "milestone_bonus"
    BIRTHDAY_BONUS = "birthday_bonus"
    LOYALTY_POINTS = "loyalty_points"


class LoyaltyService:
    """Service for managing loyalty and referral programs"""
    
    # Tier requirements and benefits
    TIER_CONFIG = {
        LoyaltyTier.BRONZE: {
            "min_transactions": 0,
            "max_transactions": 10,
            "cashback_percentage": Decimal("0.5"),
            "referral_bonus": Decimal("10.00"),
            "perks": ["Basic support", "Standard processing"]
        },
        LoyaltyTier.SILVER: {
            "min_transactions": 11,
            "max_transactions": 50,
            "cashback_percentage": Decimal("1.0"),
            "referral_bonus": Decimal("15.00"),
            "perks": ["Priority support", "Fee waivers on small transfers", "Monthly newsletter"]
        },
        LoyaltyTier.GOLD: {
            "min_transactions": 51,
            "max_transactions": 100,
            "cashback_percentage": Decimal("1.5"),
            "referral_bonus": Decimal("20.00"),
            "perks": ["24/7 priority support", "Free express transfers (1/month)", "Exclusive rates", "Birthday bonus"]
        },
        LoyaltyTier.PLATINUM: {
            "min_transactions": 101,
            "max_transactions": float('inf'),
            "cashback_percentage": Decimal("2.0"),
            "referral_bonus": Decimal("25.00"),
            "perks": ["Dedicated account manager", "Free express transfers (unlimited)", "VIP rates", "Airport lounge access", "Annual gifts"]
        }
    }
    
    # Referral program configuration
    REFERRAL_CONFIG = {
        "referrer_bonus": Decimal("10.00"),  # Bonus for person who refers
        "referee_bonus": Decimal("10.00"),   # Bonus for person who signs up
        "min_referee_transaction": Decimal("50.00"),  # Minimum first transaction to qualify
        "max_referrals_per_user": 100,
        "bonus_multiplier_tiers": {
            5: Decimal("1.5"),   # 50% bonus after 5 referrals
            10: Decimal("2.0"),  # 100% bonus after 10 referrals
            25: Decimal("2.5"),  # 150% bonus after 25 referrals
        }
    }
    
    # Milestone bonuses
    MILESTONE_BONUSES = {
        1: Decimal("5.00"),      # First transaction
        10: Decimal("10.00"),    # 10th transaction
        50: Decimal("25.00"),    # 50th transaction
        100: Decimal("50.00"),   # 100th transaction
        500: Decimal("100.00"),  # 500th transaction
        1000: Decimal("250.00"), # 1000th transaction
    }
    
    def __init__(self, config: Optional[Dict] = None) -> None:
        """Initialize loyalty service"""
        self.config = config or {}
        
        # In production, use database
        self.user_tiers = {}
        self.user_points = {}
        self.referrals = {}
        self.rewards_history = {}
    
    def get_user_tier(self, user_id: str, transaction_count: int) -> LoyaltyTier:
        """
        Determine user's loyalty tier based on transaction count
        
        Args:
            user_id: User identifier
            transaction_count: Total number of transactions
            
        Returns:
            User's loyalty tier
        """
        for tier in [LoyaltyTier.PLATINUM, LoyaltyTier.GOLD, LoyaltyTier.SILVER, LoyaltyTier.BRONZE]:
            config = self.TIER_CONFIG[tier]
            if config["min_transactions"] <= transaction_count <= config["max_transactions"]:
                self.user_tiers[user_id] = tier
                return tier
        
        return LoyaltyTier.BRONZE
    
    def calculate_cashback(
        self,
        user_id: str,
        transaction_amount: Decimal,
        transaction_fee: Decimal,
        tier: Optional[LoyaltyTier] = None
    ) -> Dict:
        """
        Calculate cashback reward for transaction
        
        Args:
            user_id: User identifier
            transaction_amount: Transaction amount
            transaction_fee: Fee charged
            tier: User's loyalty tier (optional, will be looked up)
            
        Returns:
            Cashback calculation details
        """
        if tier is None:
            tier = self.user_tiers.get(user_id, LoyaltyTier.BRONZE)
        
        tier_config = self.TIER_CONFIG[tier]
        cashback_percentage = tier_config["cashback_percentage"]
        
        # Calculate cashback on fee
        cashback_amount = transaction_fee * (cashback_percentage / 100)
        
        # Minimum cashback
        min_cashback = Decimal("0.10")
        if cashback_amount < min_cashback:
            cashback_amount = Decimal("0.00")  # Don't give tiny amounts
        
        return {
            "user_id": user_id,
            "tier": tier.value,
            "transaction_amount": float(transaction_amount),
            "transaction_fee": float(transaction_fee),
            "cashback_percentage": float(cashback_percentage),
            "cashback_amount": float(cashback_amount),
            "currency": "USD",
            "earned_at": datetime.utcnow().isoformat()
        }
    
    def process_referral(
        self,
        referrer_id: str,
        referee_id: str,
        referee_first_transaction_amount: Decimal
    ) -> Dict:
        """
        Process referral bonus when referee completes first transaction
        
        Args:
            referrer_id: User who made the referral
            referee_id: New user who was referred
            referee_first_transaction_amount: Amount of referee's first transaction
            
        Returns:
            Referral processing result
        """
        # Check if referee's transaction qualifies
        min_transaction = self.REFERRAL_CONFIG["min_referee_transaction"]
        if referee_first_transaction_amount < min_transaction:
            return {
                "success": False,
                "reason": f"First transaction must be at least ${min_transaction}",
                "referee_id": referee_id,
                "transaction_amount": float(referee_first_transaction_amount)
            }
        
        # Check if referrer has reached max referrals
        referrer_referrals = self.referrals.get(referrer_id, [])
        if len(referrer_referrals) >= self.REFERRAL_CONFIG["max_referrals_per_user"]:
            return {
                "success": False,
                "reason": "Maximum referrals reached",
                "referrer_id": referrer_id,
                "max_referrals": self.REFERRAL_CONFIG["max_referrals_per_user"]
            }
        
        # Calculate bonuses with multiplier
        referral_count = len(referrer_referrals)
        multiplier = self._get_referral_multiplier(referral_count)
        
        referrer_bonus = self.REFERRAL_CONFIG["referrer_bonus"] * multiplier
        referee_bonus = self.REFERRAL_CONFIG["referee_bonus"]
        
        # Record referral
        if referrer_id not in self.referrals:
            self.referrals[referrer_id] = []
        
        self.referrals[referrer_id].append({
            "referee_id": referee_id,
            "referred_at": datetime.utcnow().isoformat(),
            "bonus_amount": float(referrer_bonus),
            "multiplier": float(multiplier)
        })
        
        # Record rewards
        self._record_reward(referrer_id, RewardType.REFERRAL_BONUS, referrer_bonus)
        self._record_reward(referee_id, RewardType.REFERRAL_BONUS, referee_bonus)
        
        return {
            "success": True,
            "referrer_id": referrer_id,
            "referee_id": referee_id,
            "referrer_bonus": float(referrer_bonus),
            "referee_bonus": float(referee_bonus),
            "multiplier": float(multiplier),
            "total_referrals": len(self.referrals[referrer_id]),
            "next_multiplier_at": self._get_next_multiplier_threshold(referral_count + 1),
            "processed_at": datetime.utcnow().isoformat()
        }
    
    def _get_referral_multiplier(self, referral_count: int) -> Decimal:
        """Get bonus multiplier based on referral count"""
        multiplier = Decimal("1.0")
        
        for threshold, bonus_multiplier in sorted(
            self.REFERRAL_CONFIG["bonus_multiplier_tiers"].items(),
            reverse=True
        ):
            if referral_count >= threshold:
                multiplier = bonus_multiplier
                break
        
        return multiplier
    
    def _get_next_multiplier_threshold(self, current_count: int) -> Optional[int]:
        """Get next referral count threshold for bonus multiplier"""
        for threshold in sorted(self.REFERRAL_CONFIG["bonus_multiplier_tiers"].keys()):
            if current_count < threshold:
                return threshold
        return None
    
    def check_milestone_bonus(
        self,
        user_id: str,
        transaction_count: int
    ) -> Optional[Dict]:
        """
        Check if user has reached a milestone and award bonus
        
        Args:
            user_id: User identifier
            transaction_count: Current transaction count
            
        Returns:
            Milestone bonus details if applicable
        """
        if transaction_count in self.MILESTONE_BONUSES:
            bonus_amount = self.MILESTONE_BONUSES[transaction_count]
            
            self._record_reward(user_id, RewardType.MILESTONE_BONUS, bonus_amount)
            
            return {
                "user_id": user_id,
                "milestone": transaction_count,
                "bonus_amount": float(bonus_amount),
                "currency": "USD",
                "message": f"Congratulations! You've completed {transaction_count} transactions!",
                "earned_at": datetime.utcnow().isoformat()
            }
        
        # Find next milestone
        next_milestone = None
        for milestone in sorted(self.MILESTONE_BONUSES.keys()):
            if transaction_count < milestone:
                next_milestone = milestone
                break
        
        if next_milestone:
            return {
                "next_milestone": next_milestone,
                "transactions_remaining": next_milestone - transaction_count,
                "next_bonus": float(self.MILESTONE_BONUSES[next_milestone])
            }
        
        return None
    
    def get_tier_benefits(self, tier: LoyaltyTier) -> Dict:
        """Get detailed benefits for a loyalty tier"""
        config = self.TIER_CONFIG[tier]
        
        return {
            "tier": tier.value,
            "tier_name": tier.value.title(),
            "cashback_percentage": float(config["cashback_percentage"]),
            "referral_bonus": float(config["referral_bonus"]),
            "perks": config["perks"],
            "transaction_range": f"{config['min_transactions']}-{config['max_transactions'] if config['max_transactions'] != float('inf') else '∞'}",
            "next_tier": self._get_next_tier(tier)
        }
    
    def _get_next_tier(self, current_tier: LoyaltyTier) -> Optional[Dict]:
        """Get information about next tier"""
        tier_order = [LoyaltyTier.BRONZE, LoyaltyTier.SILVER, LoyaltyTier.GOLD, LoyaltyTier.PLATINUM]
        
        try:
            current_index = tier_order.index(current_tier)
            if current_index < len(tier_order) - 1:
                next_tier = tier_order[current_index + 1]
                next_config = self.TIER_CONFIG[next_tier]
                
                return {
                    "tier": next_tier.value,
                    "required_transactions": next_config["min_transactions"],
                    "cashback_percentage": float(next_config["cashback_percentage"]),
                    "additional_perks": list(set(next_config["perks"]) - set(self.TIER_CONFIG[current_tier]["perks"]))
                }
        except ValueError as e:
            logging.warning(f"Invalid tier value for user {user_id}: {e}")
            return None
        
        return None
    
    def get_user_rewards_summary(self, user_id: str) -> Dict:
        """Get complete rewards summary for user"""
        tier = self.user_tiers.get(user_id, LoyaltyTier.BRONZE)
        referrals = self.referrals.get(user_id, [])
        rewards = self.rewards_history.get(user_id, [])
        
        # Calculate totals
        total_cashback = sum(
            r["amount"] for r in rewards 
            if r["type"] == RewardType.CASHBACK
        )
        total_referral_bonuses = sum(
            r["amount"] for r in rewards 
            if r["type"] == RewardType.REFERRAL_BONUS
        )
        total_milestone_bonuses = sum(
            r["amount"] for r in rewards 
            if r["type"] == RewardType.MILESTONE_BONUS
        )
        total_rewards = total_cashback + total_referral_bonuses + total_milestone_bonuses
        
        return {
            "user_id": user_id,
            "current_tier": tier.value,
            "tier_benefits": self.get_tier_benefits(tier),
            "total_rewards_earned": float(total_rewards),
            "cashback_earned": float(total_cashback),
            "referral_bonuses_earned": float(total_referral_bonuses),
            "milestone_bonuses_earned": float(total_milestone_bonuses),
            "total_referrals": len(referrals),
            "active_referral_multiplier": float(self._get_referral_multiplier(len(referrals))),
            "recent_rewards": [
                {
                    "type": r["type"],
                    "amount": float(r["amount"]),
                    "earned_at": r["earned_at"]
                }
                for r in sorted(rewards, key=lambda x: x["earned_at"], reverse=True)[:10]
            ]
        }
    
    def generate_referral_code(self, user_id: str) -> str:
        """Generate unique referral code for user"""
        # Simple referral code generation
        # In production, use more sophisticated method
        code = f"{user_id[:4].upper()}{uuid.uuid4().hex[:6].upper()}"
        return code
    
    def _record_reward(
        self,
        user_id: str,
        reward_type: RewardType,
        amount: Decimal
    ) -> None:
        """Record reward in history"""
        if user_id not in self.rewards_history:
            self.rewards_history[user_id] = []
        
        self.rewards_history[user_id].append({
            "type": reward_type.value,
            "amount": amount,
            "earned_at": datetime.utcnow().isoformat()
        })
    
    def get_leaderboard(self, limit: int = 10) -> List[Dict]:
        """Get top users by rewards earned"""
        user_totals = []
        
        for user_id, rewards in self.rewards_history.items():
            total = sum(r["amount"] for r in rewards)
            user_totals.append({
                "user_id": user_id,
                "total_rewards": float(total),
                "tier": self.user_tiers.get(user_id, LoyaltyTier.BRONZE).value
            })
        
        # Sort by total rewards
        leaderboard = sorted(user_totals, key=lambda x: x["total_rewards"], reverse=True)[:limit]
        
        # Add rank
        for i, entry in enumerate(leaderboard, 1):
            entry["rank"] = i
        
        return leaderboard


# Example usage
if __name__ == "__main__":
    # Initialize service
    service = LoyaltyService()
    
    # Example 1: Get user tier
    print("=== User Tier ===")
    tier = service.get_user_tier("user_123", 25)
    print(f"Tier: {tier.value}")
    print(f"Benefits: {service.get_tier_benefits(tier)}")
    
    # Example 2: Calculate cashback
    print("\n=== Cashback Calculation ===")
    cashback = service.calculate_cashback(
        "user_123",
        Decimal("1000.00"),
        Decimal("20.00"),
        tier
    )
    print(f"Transaction: ${cashback['transaction_amount']}")
    print(f"Fee: ${cashback['transaction_fee']}")
    print(f"Cashback: ${cashback['cashback_amount']} ({cashback['cashback_percentage']}%)")
    
    # Example 3: Process referral
    print("\n=== Referral Bonus ===")
    referral = service.process_referral(
        "user_123",
        "user_456",
        Decimal("100.00")
    )
    print(f"Success: {referral['success']}")
    print(f"Referrer bonus: ${referral['referrer_bonus']}")
    print(f"Referee bonus: ${referral['referee_bonus']}")
    print(f"Multiplier: {referral['multiplier']}x")
    
    # Example 4: Check milestone
    print("\n=== Milestone Bonus ===")
    milestone = service.check_milestone_bonus("user_123", 10)
    if milestone and "bonus_amount" in milestone:
        print(f"Milestone reached: {milestone['milestone']} transactions")
        print(f"Bonus: ${milestone['bonus_amount']}")
    
    # Example 5: Rewards summary
    print("\n=== Rewards Summary ===")
    summary = service.get_user_rewards_summary("user_123")
    print(f"Total rewards: ${summary['total_rewards_earned']}")
    print(f"Current tier: {summary['current_tier']}")
    print(f"Total referrals: {summary['total_referrals']}")

