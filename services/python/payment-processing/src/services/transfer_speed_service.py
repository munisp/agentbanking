#!/usr/bin/env python3
"""
Tiered Transfer Speed Service
Implements Express, Standard, and Economy transfer options
"""

from enum import Enum
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class TransferSpeed(str, Enum):
    """Transfer speed tiers"""
    EXPRESS = "express"      # 0-15 minutes
    STANDARD = "standard"    # 1-4 hours
    ECONOMY = "economy"      # 1-3 days


class TransferSpeedService:
    """Service for managing tiered transfer speeds"""
    
    # Fee multipliers for each speed tier
    SPEED_FEE_MULTIPLIERS = {
        TransferSpeed.EXPRESS: Decimal("1.5"),   # 50% premium
        TransferSpeed.STANDARD: Decimal("1.0"),  # Base fee
        TransferSpeed.ECONOMY: Decimal("0.5"),   # 50% discount
    }
    
    # Estimated delivery times (in minutes)
    DELIVERY_TIMES = {
        TransferSpeed.EXPRESS: {
            "min": 0,
            "max": 15,
            "average": 5,
            "guaranteed": 15
        },
        TransferSpeed.STANDARD: {
            "min": 60,
            "max": 240,
            "average": 120,
            "guaranteed": 240
        },
        TransferSpeed.ECONOMY: {
            "min": 1440,    # 1 day
            "max": 4320,    # 3 days
            "average": 2880,  # 2 days
            "guaranteed": 4320
        }
    }
    
    # Payment corridors that support each speed tier
    SUPPORTED_CORRIDORS = {
        TransferSpeed.EXPRESS: [
            "NG-US",  # Nigeria to USA
            "NG-GB",  # Nigeria to UK
            "NG-KE",  # Nigeria to Kenya
            "NG-GH",  # Nigeria to Ghana
            "NG-BR",  # Nigeria to Brazil (PIX)
            "NG-IN",  # Nigeria to India (UPI)
        ],
        TransferSpeed.STANDARD: [
            # All corridors support standard
            "*"
        ],
        TransferSpeed.ECONOMY: [
            # All corridors support economy
            "*"
        ]
    }
    
    def __init__(self, config: Optional[Dict] = None) -> None:
        """Initialize transfer speed service"""
        self.config = config or {}
        self.base_fee_percentage = Decimal(self.config.get("base_fee_percentage", "2.0"))
        self.money_back_guarantee = self.config.get("money_back_guarantee", True)
    
    def calculate_fee(
        self,
        amount: Decimal,
        speed: TransferSpeed,
        corridor: str,
        currency: str = "NGN"
    ) -> Dict:
        """
        Calculate transfer fee based on speed tier
        
        Args:
            amount: Transfer amount
            speed: Transfer speed tier
            corridor: Payment corridor (e.g., "NG-US")
            currency: Source currency
            
        Returns:
            Dict with fee breakdown
        """
        # Get base fee
        base_fee = amount * (self.base_fee_percentage / 100)
        
        # Apply speed multiplier
        multiplier = self.SPEED_FEE_MULTIPLIERS[speed]
        final_fee = base_fee * multiplier
        
        # Minimum fee
        min_fee = Decimal("1.00")
        if final_fee < min_fee:
            final_fee = min_fee
        
        # Calculate total
        total_amount = amount + final_fee
        
        return {
            "amount": float(amount),
            "base_fee": float(base_fee),
            "speed_tier": speed.value,
            "speed_multiplier": float(multiplier),
            "final_fee": float(final_fee),
            "total_amount": float(total_amount),
            "currency": currency,
            "corridor": corridor,
            "savings_vs_express": float(
                (self.SPEED_FEE_MULTIPLIERS[TransferSpeed.EXPRESS] - multiplier) * base_fee
            ) if speed != TransferSpeed.EXPRESS else 0
        }
    
    def get_delivery_estimate(
        self,
        speed: TransferSpeed,
        corridor: str,
        current_time: Optional[datetime] = None
    ) -> Dict:
        """
        Get estimated delivery time for transfer
        
        Args:
            speed: Transfer speed tier
            corridor: Payment corridor
            current_time: Current timestamp (defaults to now)
            
        Returns:
            Dict with delivery estimates
        """
        if current_time is None:
            current_time = datetime.utcnow()
        
        times = self.DELIVERY_TIMES[speed]
        
        # Calculate estimated delivery time
        avg_minutes = times["average"]
        max_minutes = times["guaranteed"]
        
        estimated_delivery = current_time + timedelta(minutes=avg_minutes)
        guaranteed_delivery = current_time + timedelta(minutes=max_minutes)
        
        return {
            "speed_tier": speed.value,
            "corridor": corridor,
            "current_time": current_time.isoformat(),
            "estimated_delivery": estimated_delivery.isoformat(),
            "guaranteed_delivery": guaranteed_delivery.isoformat(),
            "min_minutes": times["min"],
            "max_minutes": times["max"],
            "average_minutes": times["average"],
            "guaranteed_minutes": times["guaranteed"],
            "money_back_guarantee": self.money_back_guarantee and speed == TransferSpeed.EXPRESS
        }
    
    def is_speed_supported(self, speed: TransferSpeed, corridor: str) -> bool:
        """
        Check if speed tier is supported for corridor
        
        Args:
            speed: Transfer speed tier
            corridor: Payment corridor
            
        Returns:
            True if supported, False otherwise
        """
        supported = self.SUPPORTED_CORRIDORS.get(speed, [])
        
        # Check if all corridors are supported
        if "*" in supported:
            return True
        
        # Check if specific corridor is supported
        return corridor in supported
    
    def get_available_speeds(self, corridor: str) -> List[Dict]:
        """
        Get all available speed tiers for a corridor
        
        Args:
            corridor: Payment corridor
            
        Returns:
            List of available speed tiers with details
        """
        available_speeds = []
        
        for speed in TransferSpeed:
            if self.is_speed_supported(speed, corridor):
                times = self.DELIVERY_TIMES[speed]
                multiplier = self.SPEED_FEE_MULTIPLIERS[speed]
                
                available_speeds.append({
                    "speed": speed.value,
                    "name": speed.value.title(),
                    "description": self._get_speed_description(speed),
                    "delivery_time": f"{times['min']}-{times['max']} minutes" if times['max'] < 1440 
                                   else f"{times['min']//1440}-{times['max']//1440} days",
                    "fee_multiplier": float(multiplier),
                    "discount_percentage": float((1 - multiplier) * 100) if multiplier < 1 else 0,
                    "premium_percentage": float((multiplier - 1) * 100) if multiplier > 1 else 0,
                    "guaranteed": times["guaranteed"],
                    "money_back_guarantee": self.money_back_guarantee and speed == TransferSpeed.EXPRESS
                })
        
        return available_speeds
    
    def _get_speed_description(self, speed: TransferSpeed) -> str:
        """Get user-friendly description for speed tier"""
        descriptions = {
            TransferSpeed.EXPRESS: "Lightning fast - arrives in minutes. Perfect for urgent transfers.",
            TransferSpeed.STANDARD: "Fast and reliable - arrives within hours. Our most popular option.",
            TransferSpeed.ECONOMY: "Save money - arrives in 1-3 days. Best for non-urgent transfers."
        }
        return descriptions.get(speed, "")
    
    def compare_speeds(
        self,
        amount: Decimal,
        corridor: str,
        currency: str = "NGN"
    ) -> List[Dict]:
        """
        Compare all available speed tiers for an amount
        
        Args:
            amount: Transfer amount
            corridor: Payment corridor
            currency: Source currency
            
        Returns:
            List of speed options with fees and delivery times
        """
        comparisons = []
        
        for speed in TransferSpeed:
            if self.is_speed_supported(speed, corridor):
                fee_info = self.calculate_fee(amount, speed, corridor, currency)
                delivery_info = self.get_delivery_estimate(speed, corridor)
                
                comparisons.append({
                    **fee_info,
                    **delivery_info,
                    "description": self._get_speed_description(speed),
                    "recommended": speed == TransferSpeed.STANDARD  # Standard is default recommendation
                })
        
        return comparisons
    
    def validate_transfer_speed(
        self,
        speed: TransferSpeed,
        corridor: str,
        amount: Decimal
    ) -> Dict:
        """
        Validate if a transfer can be processed at requested speed
        
        Args:
            speed: Requested transfer speed
            corridor: Payment corridor
            amount: Transfer amount
            
        Returns:
            Validation result with details
        """
        # Check if speed is supported for corridor
        if not self.is_speed_supported(speed, corridor):
            return {
                "valid": False,
                "reason": f"{speed.value} transfers not available for {corridor} corridor",
                "suggested_speed": TransferSpeed.STANDARD.value,
                "available_speeds": [s["speed"] for s in self.get_available_speeds(corridor)]
            }
        
        # Check amount limits for express transfers
        if speed == TransferSpeed.EXPRESS:
            max_express_amount = Decimal("50000.00")  # $50,000 max for express
            if amount > max_express_amount:
                return {
                    "valid": False,
                    "reason": f"Express transfers limited to {max_express_amount} {corridor.split('-')[0]}",
                    "suggested_speed": TransferSpeed.STANDARD.value,
                    "max_express_amount": float(max_express_amount)
                }
        
        return {
            "valid": True,
            "speed": speed.value,
            "corridor": corridor,
            "amount": float(amount)
        }
    
    def track_delivery_performance(
        self,
        transaction_id: str,
        speed: TransferSpeed,
        initiated_at: datetime,
        completed_at: datetime
    ) -> Dict:
        """
        Track actual delivery performance vs. promised
        
        Args:
            transaction_id: Transaction identifier
            speed: Transfer speed tier
            initiated_at: When transfer was initiated
            completed_at: When transfer completed
            
        Returns:
            Performance metrics
        """
        actual_duration = (completed_at - initiated_at).total_seconds() / 60  # minutes
        
        times = self.DELIVERY_TIMES[speed]
        guaranteed_minutes = times["guaranteed"]
        average_minutes = times["average"]
        
        # Check if delivery was on time
        on_time = actual_duration <= guaranteed_minutes
        faster_than_average = actual_duration < average_minutes
        
        # Calculate refund if applicable (money-back guarantee)
        refund_eligible = (
            not on_time and 
            speed == TransferSpeed.EXPRESS and 
            self.money_back_guarantee
        )
        
        return {
            "transaction_id": transaction_id,
            "speed_tier": speed.value,
            "initiated_at": initiated_at.isoformat(),
            "completed_at": completed_at.isoformat(),
            "actual_duration_minutes": actual_duration,
            "promised_duration_minutes": guaranteed_minutes,
            "average_duration_minutes": average_minutes,
            "on_time": on_time,
            "faster_than_average": faster_than_average,
            "delay_minutes": max(0, actual_duration - guaranteed_minutes),
            "refund_eligible": refund_eligible,
            "performance_rating": "excellent" if faster_than_average else "good" if on_time else "delayed"
        }


# Example usage
if __name__ == "__main__":
    # Initialize service
    service = TransferSpeedService()
    
    # Example 1: Compare speeds for $1000 transfer
    print("=== Speed Comparison for $1000 NG-US ===")
    amount = Decimal("1000.00")
    corridor = "NG-US"
    
    comparison = service.compare_speeds(amount, corridor, "USD")
    for option in comparison:
        print(f"\n{option['speed_tier'].upper()}:")
        print(f"  Fee: ${option['final_fee']:.2f}")
        print(f"  Total: ${option['total_amount']:.2f}")
        print(f"  Delivery: {option['average_minutes']} minutes avg")
        print(f"  {option['description']}")
    
    # Example 2: Calculate express fee
    print("\n=== Express Transfer Fee ===")
    express_fee = service.calculate_fee(amount, TransferSpeed.EXPRESS, corridor, "USD")
    print(f"Amount: ${express_fee['amount']:.2f}")
    print(f"Fee: ${express_fee['final_fee']:.2f}")
    print(f"Total: ${express_fee['total_amount']:.2f}")
    
    # Example 3: Get delivery estimate
    print("\n=== Delivery Estimate ===")
    estimate = service.get_delivery_estimate(TransferSpeed.EXPRESS, corridor)
    print(f"Estimated delivery: {estimate['estimated_delivery']}")
    print(f"Guaranteed by: {estimate['guaranteed_delivery']}")
    print(f"Money-back guarantee: {estimate['money_back_guarantee']}")

