"""
Advanced Analytics Dashboard Service

Provides real-time business intelligence and analytics

Features:
- Real-time metrics
- Transaction analytics
- User behavior analysis
- Revenue tracking
- Gateway performance
- Cohort analysis
- Predictive insights
"""

import asyncio
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

import httpx


class AnalyticsService:
    """
    Advanced Analytics Dashboard Service
    
    Provides comprehensive business intelligence
    
    Features:
    - Real-time dashboard metrics
    - Transaction analytics
    - User segmentation
    - Revenue tracking
    - Gateway performance
    - Cohort analysis
    - Trend analysis
    - Predictive insights
    """
    
    def __init__(
        self,
        database_url: str,
        cache_url: str
    ):
        """
        Initialize analytics service
        
        Args:
            database_url: Database connection URL
            cache_url: Redis cache URL
        """
        self.database_url = database_url
        self.cache_url = cache_url
        
        self.client: Optional[httpx.AsyncClient] = None
        
        # In-memory storage (would use database in production)
        self._transactions: List[Dict] = []
        self._users: Dict[str, Dict] = {}
    
    async def __aenter__(self):
        self.client = httpx.AsyncClient(timeout=30)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()
    
    async def get_realtime_metrics(self) -> Dict:
        """
        Get real-time dashboard metrics
        
        Returns:
            Real-time metrics
        """
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Calculate metrics
        today_txns = [t for t in self._transactions if datetime.fromisoformat(t["timestamp"]) >= today_start]
        
        total_volume_today = sum(t["amount"] for t in today_txns)
        total_transactions_today = len(today_txns)
        total_revenue_today = sum(t.get("fee", 0) for t in today_txns)
        
        # Active users (last 15 minutes)
        fifteen_min_ago = now - timedelta(minutes=15)
        active_users = len(set(
            t["user_id"] for t in self._transactions
            if datetime.fromisoformat(t["timestamp"]) >= fifteen_min_ago
        ))
        
        # Average transaction value
        avg_transaction_value = total_volume_today / total_transactions_today if total_transactions_today > 0 else 0
        
        # Success rate
        successful_txns = len([t for t in today_txns if t.get("status") == "COMPLETED"])
        success_rate = (successful_txns / total_transactions_today * 100) if total_transactions_today > 0 else 0
        
        # Transactions per minute (last hour)
        one_hour_ago = now - timedelta(hours=1)
        last_hour_txns = len([
            t for t in self._transactions
            if datetime.fromisoformat(t["timestamp"]) >= one_hour_ago
        ])
        txns_per_minute = last_hour_txns / 60
        
        return {
            "timestamp": now.isoformat(),
            "today": {
                "total_volume": total_volume_today,
                "total_transactions": total_transactions_today,
                "total_revenue": total_revenue_today,
                "average_transaction_value": avg_transaction_value,
                "success_rate": success_rate
            },
            "realtime": {
                "active_users_15min": active_users,
                "transactions_per_minute": txns_per_minute
            }
        }
    
    async def get_transaction_analytics(
        self,
        start_date: str,
        end_date: str,
        group_by: str = "day"  # "hour", "day", "week", "month"
    ) -> Dict:
        """
        Get transaction analytics for date range
        
        Args:
            start_date: Start date (ISO format)
            end_date: End date (ISO format)
            group_by: Grouping period
            
        Returns:
            Transaction analytics
        """
        start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        
        # Filter transactions
        filtered_txns = [
            t for t in self._transactions
            if start_dt <= datetime.fromisoformat(t["timestamp"]) <= end_dt
        ]
        
        # Group by period
        grouped = defaultdict(lambda: {
            "count": 0,
            "volume": 0,
            "revenue": 0,
            "successful": 0,
            "failed": 0
        })
        
        for txn in filtered_txns:
            txn_dt = datetime.fromisoformat(txn["timestamp"])
            
            if group_by == "hour":
                key = txn_dt.strftime("%Y-%m-%d %H:00")
            elif group_by == "day":
                key = txn_dt.strftime("%Y-%m-%d")
            elif group_by == "week":
                key = txn_dt.strftime("%Y-W%U")
            else:  # month
                key = txn_dt.strftime("%Y-%m")
            
            grouped[key]["count"] += 1
            grouped[key]["volume"] += txn["amount"]
            grouped[key]["revenue"] += txn.get("fee", 0)
            
            if txn.get("status") == "COMPLETED":
                grouped[key]["successful"] += 1
            else:
                grouped[key]["failed"] += 1
        
        # Convert to list
        time_series = [
            {
                "period": period,
                "count": data["count"],
                "volume": data["volume"],
                "revenue": data["revenue"],
                "success_rate": (data["successful"] / data["count"] * 100) if data["count"] > 0 else 0
            }
            for period, data in sorted(grouped.items())
        ]
        
        # Calculate totals
        total_count = sum(d["count"] for d in time_series)
        total_volume = sum(d["volume"] for d in time_series)
        total_revenue = sum(d["revenue"] for d in time_series)
        
        return {
            "period": {
                "start": start_date,
                "end": end_date,
                "group_by": group_by
            },
            "totals": {
                "transactions": total_count,
                "volume": total_volume,
                "revenue": total_revenue,
                "average_transaction_value": total_volume / total_count if total_count > 0 else 0
            },
            "time_series": time_series
        }
    
    async def get_gateway_performance(
        self,
        start_date: str,
        end_date: str
    ) -> Dict:
        """
        Get gateway performance analytics
        
        Args:
            start_date: Start date
            end_date: End date
            
        Returns:
            Gateway performance metrics
        """
        start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        
        # Filter transactions
        filtered_txns = [
            t for t in self._transactions
            if start_dt <= datetime.fromisoformat(t["timestamp"]) <= end_dt
        ]
        
        # Group by gateway
        gateway_stats = defaultdict(lambda: {
            "count": 0,
            "volume": 0,
            "revenue": 0,
            "successful": 0,
            "failed": 0,
            "avg_processing_time": []
        })
        
        for txn in filtered_txns:
            gateway = txn.get("gateway", "UNKNOWN")
            
            gateway_stats[gateway]["count"] += 1
            gateway_stats[gateway]["volume"] += txn["amount"]
            gateway_stats[gateway]["revenue"] += txn.get("fee", 0)
            
            if txn.get("status") == "COMPLETED":
                gateway_stats[gateway]["successful"] += 1
            else:
                gateway_stats[gateway]["failed"] += 1
            
            if "processing_time" in txn:
                gateway_stats[gateway]["avg_processing_time"].append(txn["processing_time"])
        
        # Calculate metrics
        gateway_metrics = []
        for gateway, stats in gateway_stats.items():
            success_rate = (stats["successful"] / stats["count"] * 100) if stats["count"] > 0 else 0
            avg_processing_time = sum(stats["avg_processing_time"]) / len(stats["avg_processing_time"]) if stats["avg_processing_time"] else 0
            
            gateway_metrics.append({
                "gateway": gateway,
                "transactions": stats["count"],
                "volume": stats["volume"],
                "revenue": stats["revenue"],
                "success_rate": success_rate,
                "average_processing_time_seconds": avg_processing_time,
                "market_share": 0  # Will calculate after
            })
        
        # Calculate market share
        total_txns = sum(g["transactions"] for g in gateway_metrics)
        for gateway in gateway_metrics:
            gateway["market_share"] = (gateway["transactions"] / total_txns * 100) if total_txns > 0 else 0
        
        # Sort by volume
        gateway_metrics.sort(key=lambda x: x["volume"], reverse=True)
        
        return {
            "period": {
                "start": start_date,
                "end": end_date
            },
            "gateways": gateway_metrics
        }
    
    async def get_user_segmentation(self) -> Dict:
        """
        Get user segmentation analysis
        
        Returns:
            User segments
        """
        # Calculate user metrics
        user_metrics = []
        
        for user_id, user in self._users.items():
            user_txns = [t for t in self._transactions if t["user_id"] == user_id]
            
            if not user_txns:
                continue
            
            total_volume = sum(t["amount"] for t in user_txns)
            total_txns = len(user_txns)
            avg_txn_value = total_volume / total_txns
            
            first_txn = min(datetime.fromisoformat(t["timestamp"]) for t in user_txns)
            last_txn = max(datetime.fromisoformat(t["timestamp"]) for t in user_txns)
            days_active = (last_txn - first_txn).days + 1
            
            user_metrics.append({
                "user_id": user_id,
                "total_volume": total_volume,
                "total_transactions": total_txns,
                "average_transaction_value": avg_txn_value,
                "days_active": days_active,
                "first_transaction": first_txn.isoformat(),
                "last_transaction": last_txn.isoformat()
            })
        
        # Segment users
        segments = {
            "whales": [],  # Top 10% by volume
            "high_value": [],  # 11-30% by volume
            "medium_value": [],  # 31-70% by volume
            "low_value": [],  # 71-100% by volume
            "at_risk": [],  # No transaction in 30 days
            "new_users": []  # First transaction < 7 days ago
        }
        
        # Sort by volume
        user_metrics.sort(key=lambda x: x["total_volume"], reverse=True)
        
        total_users = len(user_metrics)
        now = datetime.now(timezone.utc)
        
        for i, user in enumerate(user_metrics):
            percentile = (i + 1) / total_users * 100
            
            # Value segments
            if percentile <= 10:
                segments["whales"].append(user)
            elif percentile <= 30:
                segments["high_value"].append(user)
            elif percentile <= 70:
                segments["medium_value"].append(user)
            else:
                segments["low_value"].append(user)
            
            # Behavioral segments
            last_txn = datetime.fromisoformat(user["last_transaction"])
            days_since_last = (now - last_txn).days
            
            if days_since_last > 30:
                segments["at_risk"].append(user)
            
            first_txn = datetime.fromisoformat(user["first_transaction"])
            days_since_first = (now - first_txn).days
            
            if days_since_first < 7:
                segments["new_users"].append(user)
        
        # Calculate segment metrics
        segment_summary = {}
        for segment_name, users in segments.items():
            if users:
                total_volume = sum(u["total_volume"] for u in users)
                total_txns = sum(u["total_transactions"] for u in users)
                
                segment_summary[segment_name] = {
                    "user_count": len(users),
                    "total_volume": total_volume,
                    "total_transactions": total_txns,
                    "average_volume_per_user": total_volume / len(users),
                    "average_transactions_per_user": total_txns / len(users)
                }
            else:
                segment_summary[segment_name] = {
                    "user_count": 0,
                    "total_volume": 0,
                    "total_transactions": 0,
                    "average_volume_per_user": 0,
                    "average_transactions_per_user": 0
                }
        
        return {
            "total_users": total_users,
            "segments": segment_summary
        }
    
    async def get_cohort_analysis(
        self,
        cohort_by: str = "month"  # "week", "month"
    ) -> Dict:
        """
        Get cohort retention analysis
        
        Args:
            cohort_by: Cohort grouping period
            
        Returns:
            Cohort analysis
        """
        # Group users by first transaction date
        cohorts = defaultdict(list)
        
        for user_id, user in self._users.items():
            user_txns = [t for t in self._transactions if t["user_id"] == user_id]
            
            if not user_txns:
                continue
            
            first_txn = min(datetime.fromisoformat(t["timestamp"]) for t in user_txns)
            
            if cohort_by == "week":
                cohort_key = first_txn.strftime("%Y-W%U")
            else:  # month
                cohort_key = first_txn.strftime("%Y-%m")
            
            cohorts[cohort_key].append({
                "user_id": user_id,
                "first_transaction": first_txn
            })
        
        # Calculate retention
        cohort_retention = []
        
        for cohort_key, users in sorted(cohorts.items()):
            cohort_size = len(users)
            cohort_start = users[0]["first_transaction"]
            
            # Calculate retention for each period
            retention_periods = []
            
            for period in range(12):  # 12 periods
                period_start = cohort_start + timedelta(days=period * 30)
                period_end = period_start + timedelta(days=30)
                
                active_users = len(set(
                    t["user_id"] for t in self._transactions
                    if t["user_id"] in [u["user_id"] for u in users]
                    and period_start <= datetime.fromisoformat(t["timestamp"]) < period_end
                ))
                
                retention_rate = (active_users / cohort_size * 100) if cohort_size > 0 else 0
                
                retention_periods.append({
                    "period": period,
                    "active_users": active_users,
                    "retention_rate": retention_rate
                })
            
            cohort_retention.append({
                "cohort": cohort_key,
                "cohort_size": cohort_size,
                "retention": retention_periods
            })
        
        return {
            "cohort_by": cohort_by,
            "cohorts": cohort_retention
        }
    
    async def get_revenue_breakdown(
        self,
        start_date: str,
        end_date: str
    ) -> Dict:
        """
        Get revenue breakdown analysis
        
        Args:
            start_date: Start date
            end_date: End date
            
        Returns:
            Revenue breakdown
        """
        start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        
        # Filter transactions
        filtered_txns = [
            t for t in self._transactions
            if start_dt <= datetime.fromisoformat(t["timestamp"]) <= end_dt
        ]
        
        # Calculate revenue by source
        revenue_by_gateway = defaultdict(float)
        revenue_by_currency = defaultdict(float)
        revenue_by_user_segment = defaultdict(float)
        
        for txn in filtered_txns:
            fee = txn.get("fee", 0)
            
            revenue_by_gateway[txn.get("gateway", "UNKNOWN")] += fee
            revenue_by_currency[txn.get("currency", "USD")] += fee
        
        total_revenue = sum(revenue_by_gateway.values())
        
        return {
            "period": {
                "start": start_date,
                "end": end_date
            },
            "total_revenue": total_revenue,
            "by_gateway": dict(revenue_by_gateway),
            "by_currency": dict(revenue_by_currency)
        }
    
    async def get_predictive_insights(self) -> Dict:
        """
        Get predictive insights using historical data
        
        Returns:
            Predictive insights
        """
        # Simple trend analysis (would use ML models in production)
        
        # Get last 30 days data
        now = datetime.now(timezone.utc)
        thirty_days_ago = now - timedelta(days=30)
        
        recent_txns = [
            t for t in self._transactions
            if datetime.fromisoformat(t["timestamp"]) >= thirty_days_ago
        ]
        
        if len(recent_txns) < 7:
            return {
                "message": "Insufficient data for predictions",
                "predictions": {}
            }
        
        # Calculate daily averages
        daily_volume = defaultdict(float)
        daily_count = defaultdict(int)
        
        for txn in recent_txns:
            date = datetime.fromisoformat(txn["timestamp"]).date()
            daily_volume[date] += txn["amount"]
            daily_count[date] += 1
        
        avg_daily_volume = sum(daily_volume.values()) / len(daily_volume)
        avg_daily_count = sum(daily_count.values()) / len(daily_count)
        
        # Simple linear trend
        volumes = list(daily_volume.values())
        if len(volumes) >= 7:
            recent_avg = sum(volumes[-7:]) / 7
            older_avg = sum(volumes[:-7]) / len(volumes[:-7]) if len(volumes) > 7 else recent_avg
            
            growth_rate = ((recent_avg - older_avg) / older_avg * 100) if older_avg > 0 else 0
        else:
            growth_rate = 0
        
        # Predictions
        next_7_days_volume = avg_daily_volume * 7 * (1 + growth_rate / 100)
        next_30_days_volume = avg_daily_volume * 30 * (1 + growth_rate / 100)
        
        return {
            "current_metrics": {
                "average_daily_volume": avg_daily_volume,
                "average_daily_transactions": avg_daily_count,
                "growth_rate_percentage": growth_rate
            },
            "predictions": {
                "next_7_days": {
                    "expected_volume": next_7_days_volume,
                    "expected_transactions": avg_daily_count * 7
                },
                "next_30_days": {
                    "expected_volume": next_30_days_volume,
                    "expected_transactions": avg_daily_count * 30
                }
            },
            "confidence": "LOW" if len(recent_txns) < 30 else "MEDIUM" if len(recent_txns) < 100 else "HIGH"
        }
    
    def record_transaction(self, transaction: Dict):
        """Record transaction for analytics"""
        self._transactions.append(transaction)
    
    def register_user(self, user_id: str, user_data: Dict):
        """Register user for analytics"""
        self._users[user_id] = user_data
