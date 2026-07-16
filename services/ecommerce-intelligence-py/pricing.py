"""
Dynamic Pricing Engine
- Demand-based price adjustment
- Inventory-aware pricing (scarce = premium)
- Customer segment pricing
- Time-of-day/seasonal factors
- Offline price cache for agents
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("pricing")


@dataclass
class PricingRule:
    rule_id: str
    rule_type: str  # demand, inventory, segment, time, promo
    conditions: dict[str, Any] = field(default_factory=dict)
    adjustment: float = 0.0  # percentage or flat
    adjustment_type: str = "percentage"  # percentage | flat
    priority: int = 0
    active: bool = True


class DynamicPricingEngine:
    def __init__(self, db_url: str, redis_url: str):
        self.db_url = db_url
        self.redis_url = redis_url
        self.rules: list[PricingRule] = []
        self.base_prices: dict[int, float] = {}
        self.demand_scores: dict[int, float] = {}
        self.inventory_levels: dict[int, int] = {}
        self.offline_cache: list[dict] = []
        self._cache_time: str = ""
        self._rule_counter = 0

        # Initialize with default rules
        self._init_default_rules()

    def _init_default_rules(self):
        """Set up sensible default pricing rules."""
        self.rules = [
            PricingRule(
                rule_id="demand_surge",
                rule_type="demand",
                conditions={"demand_threshold": 2.0},
                adjustment=15.0,
                adjustment_type="percentage",
                priority=10,
            ),
            PricingRule(
                rule_id="low_inventory",
                rule_type="inventory",
                conditions={"inventory_threshold": 5},
                adjustment=10.0,
                adjustment_type="percentage",
                priority=20,
            ),
            PricingRule(
                rule_id="bulk_discount",
                rule_type="quantity",
                conditions={"min_quantity": 10},
                adjustment=-5.0,
                adjustment_type="percentage",
                priority=5,
            ),
            PricingRule(
                rule_id="loyal_customer",
                rule_type="segment",
                conditions={"segment": "loyal", "min_orders": 10},
                adjustment=-3.0,
                adjustment_type="percentage",
                priority=15,
            ),
        ]

    def calculate(self, product_id: int, customer_id: int, quantity: int) -> dict:
        """Calculate dynamic price for a product."""
        base_price = self.base_prices.get(product_id, 1000.0)  # Default ₦1000
        adjustments: list[dict] = []
        total_adjustment_pct = 0.0
        total_adjustment_flat = 0.0

        for rule in sorted(self.rules, key=lambda r: r.priority, reverse=True):
            if not rule.active:
                continue

            applies, reason = self._evaluate_rule(rule, product_id, customer_id, quantity)
            if not applies:
                continue

            if rule.adjustment_type == "percentage":
                total_adjustment_pct += rule.adjustment
                adjustments.append({
                    "ruleId": rule.rule_id,
                    "type": rule.rule_type,
                    "adjustment": f"{rule.adjustment:+.1f}%",
                    "reason": reason,
                })
            else:
                total_adjustment_flat += rule.adjustment
                adjustments.append({
                    "ruleId": rule.rule_id,
                    "type": rule.rule_type,
                    "adjustment": f"₦{rule.adjustment:+.0f}",
                    "reason": reason,
                })

        # Cap adjustments at ±30%
        total_adjustment_pct = max(-30.0, min(30.0, total_adjustment_pct))

        final_price = base_price * (1 + total_adjustment_pct / 100) + total_adjustment_flat
        final_price = max(final_price, base_price * 0.5)  # Floor at 50% of base

        unit_total = round(final_price, 2)
        line_total = round(final_price * quantity, 2)

        return {
            "productId": product_id,
            "basePrice": base_price,
            "dynamicPrice": unit_total,
            "lineTotal": line_total,
            "quantity": quantity,
            "currency": "NGN",
            "adjustments": adjustments,
            "totalAdjustmentPct": round(total_adjustment_pct, 2),
            "savings": round(max(0, (base_price - unit_total) * quantity), 2),
        }

    def _evaluate_rule(
        self, rule: PricingRule, product_id: int, customer_id: int, quantity: int
    ) -> tuple[bool, str]:
        """Evaluate if a pricing rule applies to this context."""
        if rule.rule_type == "demand":
            demand = self.demand_scores.get(product_id, 1.0)
            threshold = rule.conditions.get("demand_threshold", 2.0)
            if demand >= threshold:
                return True, f"High demand (score: {demand:.1f})"
            return False, ""

        elif rule.rule_type == "inventory":
            level = self.inventory_levels.get(product_id, 100)
            threshold = rule.conditions.get("inventory_threshold", 5)
            if level <= threshold:
                return True, f"Low stock ({level} remaining)"
            return False, ""

        elif rule.rule_type == "quantity":
            min_qty = rule.conditions.get("min_quantity", 10)
            if quantity >= min_qty:
                return True, f"Bulk order ({quantity} units)"
            return False, ""

        elif rule.rule_type == "segment":
            # In production, lookup customer segment from DB
            if customer_id > 0:
                min_orders = rule.conditions.get("min_orders", 10)
                # Simplified: customers with ID < 1000 are "loyal"
                if customer_id < 1000:
                    return True, f"Loyal customer discount"
            return False, ""

        return False, ""

    def add_rule(self, data: dict) -> str:
        """Add a new pricing rule."""
        self._rule_counter += 1
        rule_id = f"custom_{self._rule_counter}"
        rule = PricingRule(
            rule_id=rule_id,
            rule_type=data.get("type", "custom"),
            conditions=data.get("conditions", {}),
            adjustment=data.get("adjustment", 0.0),
            adjustment_type=data.get("adjustmentType", "percentage"),
            priority=data.get("priority", 0),
            active=True,
        )
        self.rules.append(rule)
        return rule_id

    def get_offline_cache(self, category_id: int, limit: int) -> list[dict]:
        """Generate price cache for offline agents."""
        cache = []
        for pid, base in list(self.base_prices.items())[:limit]:
            price_info = self.calculate(pid, 0, 1)
            cache.append({
                "productId": pid,
                "basePrice": base,
                "offlinePrice": price_info["dynamicPrice"],
                "currency": "NGN",
                "validUntil": "4h",
            })

        self._cache_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        return cache

    def last_cache_time(self) -> str:
        return self._cache_time or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
