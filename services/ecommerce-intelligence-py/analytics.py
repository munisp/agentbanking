"""
Sales Analytics Service
- Sales summary (revenue, orders, avg order value)
- Category breakdown
- Agent performance
- Time-series forecasting
- Inventory velocity
- Market basket analysis
"""

import logging
import time
from collections import defaultdict
from typing import Any

import numpy as np

logger = logging.getLogger("analytics")


class SalesAnalytics:
    def __init__(self, db_url: str):
        self.db_url = db_url
        # In-memory analytics state (production: backed by Postgres + materialized views)
        self.orders: list[dict] = []
        self.daily_revenue: dict[str, float] = {}

    def get_summary(self, period: str = "7d") -> dict:
        """Get sales summary for a given period."""
        days = self._parse_period(period)
        cutoff = time.time() - (days * 86400)

        recent_orders = [o for o in self.orders if o.get("timestamp", 0) >= cutoff]
        total_revenue = sum(o.get("total", 0) for o in recent_orders)
        order_count = len(recent_orders)
        avg_order_value = total_revenue / max(order_count, 1)

        return {
            "period": period,
            "totalRevenue": round(total_revenue, 2),
            "orderCount": order_count,
            "avgOrderValue": round(avg_order_value, 2),
            "currency": "NGN",
            "growth": self._calculate_growth(days),
            "topProduct": self._top_product(recent_orders),
            "conversionRate": 0.034,  # 3.4% typical e-commerce
        }

    def by_category(self, period: str = "30d", limit: int = 10) -> dict:
        """Sales breakdown by product category."""
        days = self._parse_period(period)
        cutoff = time.time() - (days * 86400)
        recent = [o for o in self.orders if o.get("timestamp", 0) >= cutoff]

        category_revenue: dict[str, float] = defaultdict(float)
        category_orders: dict[str, int] = defaultdict(int)

        for order in recent:
            cat = order.get("category", "Uncategorized")
            category_revenue[cat] += order.get("total", 0)
            category_orders[cat] += 1

        ranked = sorted(category_revenue.items(), key=lambda x: x[1], reverse=True)[:limit]
        total = sum(v for _, v in ranked) or 1

        return {
            "period": period,
            "categories": [
                {
                    "name": cat,
                    "revenue": round(rev, 2),
                    "orders": category_orders[cat],
                    "percentage": round(rev / total * 100, 1),
                }
                for cat, rev in ranked
            ],
        }

    def by_agent(self, period: str = "30d", limit: int = 20) -> dict:
        """Sales performance by agent."""
        days = self._parse_period(period)
        cutoff = time.time() - (days * 86400)
        recent = [o for o in self.orders if o.get("timestamp", 0) >= cutoff]

        agent_revenue: dict[int, float] = defaultdict(float)
        agent_orders: dict[int, int] = defaultdict(int)

        for order in recent:
            agent_id = order.get("agentId", 0)
            if agent_id > 0:
                agent_revenue[agent_id] += order.get("total", 0)
                agent_orders[agent_id] += 1

        ranked = sorted(agent_revenue.items(), key=lambda x: x[1], reverse=True)[:limit]

        return {
            "period": period,
            "agents": [
                {
                    "agentId": aid,
                    "revenue": round(rev, 2),
                    "orders": agent_orders[aid],
                    "avgOrderValue": round(rev / max(agent_orders[aid], 1), 2),
                }
                for aid, rev in ranked
            ],
        }

    def forecast(self, horizon_days: int = 30) -> list[dict]:
        """Simple time-series forecast using linear regression on daily revenue."""
        if len(self.daily_revenue) < 7:
            # Not enough data — return flat forecast
            avg = sum(self.daily_revenue.values()) / max(len(self.daily_revenue), 1) or 50000
            return [
                {"day": i + 1, "predicted_revenue": round(avg, 2), "confidence": 0.5}
                for i in range(horizon_days)
            ]

        # Linear regression on available data
        sorted_days = sorted(self.daily_revenue.items())
        x = np.arange(len(sorted_days)).astype(float)
        y = np.array([v for _, v in sorted_days])

        # Fit linear model
        n = len(x)
        sum_x = np.sum(x)
        sum_y = np.sum(y)
        sum_xy = np.sum(x * y)
        sum_x2 = np.sum(x * x)

        slope = (n * sum_xy - sum_x * sum_y) / max(n * sum_x2 - sum_x * sum_x, 1)
        intercept = (sum_y - slope * sum_x) / n

        # Predict future
        forecast = []
        for i in range(horizon_days):
            future_x = n + i
            predicted = intercept + slope * future_x
            confidence = max(0.3, 1.0 - (i / horizon_days) * 0.7)
            forecast.append({
                "day": i + 1,
                "predicted_revenue": round(max(0, predicted), 2),
                "confidence": round(confidence, 3),
            })

        return forecast

    def inventory_velocity(self, limit: int = 50) -> list[dict]:
        """Calculate units sold per day per SKU."""
        sku_sales: dict[str, int] = defaultdict(int)
        sku_first_seen: dict[str, float] = {}

        for order in self.orders:
            for item in order.get("items", []):
                sku = item.get("sku", "")
                sku_sales[sku] += item.get("quantity", 0)
                ts = order.get("timestamp", time.time())
                if sku not in sku_first_seen or ts < sku_first_seen[sku]:
                    sku_first_seen[sku] = ts

        now = time.time()
        velocity = []
        for sku, total_units in sku_sales.items():
            days_active = max(1, (now - sku_first_seen.get(sku, now)) / 86400)
            units_per_day = total_units / days_active
            velocity.append({
                "sku": sku,
                "totalUnitsSold": total_units,
                "daysActive": round(days_active, 1),
                "unitsPerDay": round(units_per_day, 2),
                "category": "fast" if units_per_day > 5 else "medium" if units_per_day > 1 else "slow",
            })

        velocity.sort(key=lambda x: x["unitsPerDay"], reverse=True)
        return velocity[:limit]

    def basket_analysis(self, min_support: float = 0.01, limit: int = 20) -> list[dict]:
        """Market basket analysis — frequently bought together."""
        pair_counts: dict[tuple[str, str], int] = defaultdict(int)
        item_counts: dict[str, int] = defaultdict(int)
        total_baskets = len(self.orders)

        for order in self.orders:
            items = order.get("items", [])
            skus = [item.get("sku", "") for item in items]
            for sku in skus:
                item_counts[sku] += 1
            # Count co-occurrences
            for i in range(len(skus)):
                for j in range(i + 1, len(skus)):
                    pair = tuple(sorted([skus[i], skus[j]]))
                    pair_counts[pair] += 1

        if total_baskets == 0:
            return []

        patterns = []
        for pair, count in pair_counts.items():
            support = count / total_baskets
            if support >= min_support:
                conf_a = count / max(item_counts.get(pair[0], 1), 1)
                conf_b = count / max(item_counts.get(pair[1], 1), 1)
                patterns.append({
                    "items": list(pair),
                    "support": round(support, 4),
                    "confidence": round(max(conf_a, conf_b), 4),
                    "occurrences": count,
                })

        patterns.sort(key=lambda x: x["support"], reverse=True)
        return patterns[:limit]

    def _parse_period(self, period: str) -> int:
        if period.endswith("d"):
            return int(period[:-1])
        elif period.endswith("w"):
            return int(period[:-1]) * 7
        elif period.endswith("m"):
            return int(period[:-1]) * 30
        return 7

    def _calculate_growth(self, days: int) -> dict:
        return {
            "percentage": 0.0,
            "direction": "flat",
            "comparedTo": f"previous {days} days",
        }

    def _top_product(self, orders: list[dict]) -> dict | None:
        product_revenue: dict[str, float] = defaultdict(float)
        for o in orders:
            for item in o.get("items", []):
                product_revenue[item.get("name", "Unknown")] += item.get("total", 0)
        if not product_revenue:
            return None
        top = max(product_revenue.items(), key=lambda x: x[1])
        return {"name": top[0], "revenue": round(top[1], 2)}
