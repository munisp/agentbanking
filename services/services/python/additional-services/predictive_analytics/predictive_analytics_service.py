"""
Predictive Analytics Service
ML-powered transaction pattern analysis and forecasting

Features:
- Transaction volume forecasting
- Revenue prediction
- User behavior prediction
- Churn risk analysis
- Seasonal pattern detection
- Anomaly detection
"""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import json

import httpx
import numpy as np


class PredictionType(Enum):
    """Types of predictions"""
    VOLUME_FORECAST = "VOLUME_FORECAST"
    REVENUE_FORECAST = "REVENUE_FORECAST"
    USER_BEHAVIOR = "USER_BEHAVIOR"
    CHURN_RISK = "CHURN_RISK"
    SEASONAL_PATTERN = "SEASONAL_PATTERN"
    GATEWAY_DEMAND = "GATEWAY_DEMAND"


class TimeHorizon(Enum):
    """Prediction time horizon"""
    HOUR = "HOUR"
    DAY = "DAY"
    WEEK = "WEEK"
    MONTH = "MONTH"
    QUARTER = "QUARTER"
    YEAR = "YEAR"


@dataclass
class Prediction:
    """Prediction result"""
    prediction_id: str
    prediction_type: str
    time_horizon: str
    predicted_value: float
    confidence_interval_lower: float
    confidence_interval_upper: float
    confidence_level: float
    features_used: List[str]
    model_version: str
    predicted_at: datetime
    valid_until: datetime


@dataclass
class UserBehaviorPrediction:
    """User behavior prediction"""
    user_id: str
    next_transaction_probability: float
    expected_transaction_amount: Decimal
    expected_transaction_date: datetime
    preferred_destination_countries: List[str]
    churn_probability: float
    lifetime_value_estimate: Decimal
    confidence: float


@dataclass
class SeasonalPattern:
    """Seasonal pattern detection"""
    pattern_id: str
    pattern_type: str  # daily, weekly, monthly, yearly
    peak_periods: List[Dict]
    trough_periods: List[Dict]
    amplitude: float
    confidence: float
    detected_at: datetime


class PredictiveAnalyticsService:
    """
    Predictive Analytics Service
    
    Provides ML-powered predictions for:
    - Transaction volume forecasting
    - Revenue prediction
    - User behavior analysis
    - Churn risk assessment
    - Seasonal pattern detection
    - Gateway demand forecasting
    
    Enables proactive decision-making and resource optimization
    """
    
    def __init__(
        self,
        ml_api_url: str,
        ml_api_key: str,
        history_window_days: int = 90
    ):
        """
        Initialize predictive analytics service
        
        Args:
            ml_api_url: ML model API URL
            ml_api_key: ML API key
            history_window_days: Historical data window
        """
        self.ml_api_url = ml_api_url
        self.ml_api_key = ml_api_key
        self.history_window_days = history_window_days
        
        # HTTP client
        self.client: Optional[httpx.AsyncClient] = None
        
        # Data storage
        self._transaction_history: List[Dict] = []
        self._predictions: Dict[str, Prediction] = {}
        self._user_predictions: Dict[str, UserBehaviorPrediction] = {}
        self._seasonal_patterns: Dict[str, SeasonalPattern] = {}
        
        # Model version
        self.model_version = "v1.5.0"
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.client = httpx.AsyncClient(timeout=30)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.client:
            await self.client.aclose()
    
    async def forecast_transaction_volume(
        self,
        time_horizon: TimeHorizon,
        periods_ahead: int = 1,
        confidence_level: float = 0.95
    ) -> List[Prediction]:
        """
        Forecast transaction volume
        
        Args:
            time_horizon: Time unit for forecast
            periods_ahead: Number of periods to forecast
            confidence_level: Confidence level for intervals
            
        Returns:
            List of volume predictions
        """
        # Get historical data
        historical_volumes = await self._get_historical_volumes(time_horizon)
        
        if len(historical_volumes) < 10:
            raise ValueError("Insufficient historical data for forecasting")
        
        predictions = []
        
        for period in range(1, periods_ahead + 1):
            # Simple time series forecasting (would use ARIMA/Prophet in production)
            predicted_value = await self._forecast_value(
                historical_volumes,
                period,
                time_horizon
            )
            
            # Calculate confidence interval
            std_dev = np.std(historical_volumes)
            z_score = 1.96 if confidence_level == 0.95 else 2.58  # 95% or 99%
            margin = z_score * std_dev
            
            # Create prediction
            now = datetime.now(timezone.utc)
            valid_until = self._calculate_valid_until(now, time_horizon, period)
            
            prediction = Prediction(
                prediction_id=str(uuid.uuid4()),
                prediction_type=PredictionType.VOLUME_FORECAST.value,
                time_horizon=time_horizon.value,
                predicted_value=predicted_value,
                confidence_interval_lower=max(0, predicted_value - margin),
                confidence_interval_upper=predicted_value + margin,
                confidence_level=confidence_level,
                features_used=["historical_volume", "trend", "seasonality"],
                model_version=self.model_version,
                predicted_at=now,
                valid_until=valid_until
            )
            
            self._predictions[prediction.prediction_id] = prediction
            predictions.append(prediction)
        
        return predictions
    
    async def forecast_revenue(
        self,
        time_horizon: TimeHorizon,
        periods_ahead: int = 1,
        confidence_level: float = 0.95
    ) -> List[Prediction]:
        """
        Forecast revenue
        
        Args:
            time_horizon: Time unit for forecast
            periods_ahead: Number of periods to forecast
            confidence_level: Confidence level for intervals
            
        Returns:
            List of revenue predictions
        """
        # Get historical revenue
        historical_revenue = await self._get_historical_revenue(time_horizon)
        
        if len(historical_revenue) < 10:
            raise ValueError("Insufficient historical data for forecasting")
        
        predictions = []
        
        for period in range(1, periods_ahead + 1):
            # Forecast revenue
            predicted_value = await self._forecast_value(
                historical_revenue,
                period,
                time_horizon
            )
            
            # Calculate confidence interval
            std_dev = np.std(historical_revenue)
            z_score = 1.96 if confidence_level == 0.95 else 2.58
            margin = z_score * std_dev
            
            now = datetime.now(timezone.utc)
            valid_until = self._calculate_valid_until(now, time_horizon, period)
            
            prediction = Prediction(
                prediction_id=str(uuid.uuid4()),
                prediction_type=PredictionType.REVENUE_FORECAST.value,
                time_horizon=time_horizon.value,
                predicted_value=predicted_value,
                confidence_interval_lower=max(0, predicted_value - margin),
                confidence_interval_upper=predicted_value + margin,
                confidence_level=confidence_level,
                features_used=["historical_revenue", "volume", "avg_transaction_value"],
                model_version=self.model_version,
                predicted_at=now,
                valid_until=valid_until
            )
            
            self._predictions[prediction.prediction_id] = prediction
            predictions.append(prediction)
        
        return predictions
    
    async def predict_user_behavior(
        self,
        user_id: str
    ) -> UserBehaviorPrediction:
        """
        Predict user behavior
        
        Args:
            user_id: User identifier
            
        Returns:
            UserBehaviorPrediction with expected behavior
        """
        # Get user transaction history
        user_transactions = await self._get_user_transactions(user_id)
        
        if not user_transactions:
            raise ValueError(f"No transaction history for user: {user_id}")
        
        # Calculate statistics
        transaction_amounts = [float(txn["amount"]) for txn in user_transactions]
        avg_amount = np.mean(transaction_amounts)
        
        # Calculate transaction frequency
        if len(user_transactions) >= 2:
            first_txn = datetime.fromisoformat(user_transactions[0]["timestamp"])
            last_txn = datetime.fromisoformat(user_transactions[-1]["timestamp"])
            days_active = (last_txn - first_txn).days or 1
            frequency = len(user_transactions) / days_active
        else:
            frequency = 0.1  # Default
        
        # Predict next transaction
        days_until_next = 1 / frequency if frequency > 0 else 30
        next_transaction_date = datetime.now(timezone.utc) + timedelta(days=days_until_next)
        next_transaction_probability = min(frequency * 7, 1.0)  # Probability in next 7 days
        
        # Predict churn
        days_since_last = (datetime.now(timezone.utc) - last_txn).days
        churn_probability = min(days_since_last / 90, 1.0)  # Churn if inactive > 90 days
        
        # Estimate lifetime value
        lifetime_value = Decimal(str(avg_amount * frequency * 365 * 3))  # 3 years
        
        # Get preferred destinations
        destinations = [txn["destination_country"] for txn in user_transactions]
        destination_counts = {}
        for dest in destinations:
            destination_counts[dest] = destination_counts.get(dest, 0) + 1
        preferred_destinations = sorted(
            destination_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:3]
        preferred_destination_countries = [dest for dest, _ in preferred_destinations]
        
        # Calculate confidence
        confidence = min(len(user_transactions) / 10, 1.0)
        
        prediction = UserBehaviorPrediction(
            user_id=user_id,
            next_transaction_probability=next_transaction_probability,
            expected_transaction_amount=Decimal(str(avg_amount)),
            expected_transaction_date=next_transaction_date,
            preferred_destination_countries=preferred_destination_countries,
            churn_probability=churn_probability,
            lifetime_value_estimate=lifetime_value,
            confidence=confidence
        )
        
        self._user_predictions[user_id] = prediction
        
        return prediction
    
    async def detect_seasonal_patterns(
        self,
        time_horizon: TimeHorizon = TimeHorizon.DAY
    ) -> List[SeasonalPattern]:
        """
        Detect seasonal patterns in transaction data
        
        Args:
            time_horizon: Time unit for pattern detection
            
        Returns:
            List of detected seasonal patterns
        """
        # Get historical data
        historical_data = await self._get_historical_volumes(time_horizon)
        
        if len(historical_data) < 30:
            raise ValueError("Insufficient data for seasonal pattern detection")
        
        patterns = []
        
        # Detect daily pattern (if hourly data available)
        if time_horizon == TimeHorizon.HOUR:
            daily_pattern = await self._detect_daily_pattern(historical_data)
            if daily_pattern:
                patterns.append(daily_pattern)
        
        # Detect weekly pattern
        if time_horizon in [TimeHorizon.HOUR, TimeHorizon.DAY]:
            weekly_pattern = await self._detect_weekly_pattern(historical_data)
            if weekly_pattern:
                patterns.append(weekly_pattern)
        
        # Detect monthly pattern
        if time_horizon in [TimeHorizon.DAY, TimeHorizon.WEEK]:
            monthly_pattern = await self._detect_monthly_pattern(historical_data)
            if monthly_pattern:
                patterns.append(monthly_pattern)
        
        return patterns
    
    async def _forecast_value(
        self,
        historical_data: List[float],
        periods_ahead: int,
        time_horizon: TimeHorizon
    ) -> float:
        """Forecast future value using simple exponential smoothing"""
        if not self.client:
            # Fallback: simple moving average
            return np.mean(historical_data[-10:])
        
        try:
            # Call ML API for sophisticated forecasting
            response = await self.client.post(
                f"{self.ml_api_url}/forecast",
                json={
                    "historical_data": historical_data,
                    "periods_ahead": periods_ahead,
                    "time_horizon": time_horizon.value
                },
                headers={"Authorization": f"Bearer {self.ml_api_key}"}
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("forecast", np.mean(historical_data[-10:]))
            else:
                return np.mean(historical_data[-10:])
                
        except Exception as e:
            print(f"ML forecast error: {e}")
            return np.mean(historical_data[-10:])
    
    def _calculate_valid_until(
        self,
        base_time: datetime,
        time_horizon: TimeHorizon,
        periods_ahead: int
    ) -> datetime:
        """Calculate when prediction expires"""
        if time_horizon == TimeHorizon.HOUR:
            return base_time + timedelta(hours=periods_ahead)
        elif time_horizon == TimeHorizon.DAY:
            return base_time + timedelta(days=periods_ahead)
        elif time_horizon == TimeHorizon.WEEK:
            return base_time + timedelta(weeks=periods_ahead)
        elif time_horizon == TimeHorizon.MONTH:
            return base_time + timedelta(days=30 * periods_ahead)
        elif time_horizon == TimeHorizon.QUARTER:
            return base_time + timedelta(days=90 * periods_ahead)
        else:  # YEAR
            return base_time + timedelta(days=365 * periods_ahead)
    
    async def _get_historical_volumes(self, time_horizon: TimeHorizon) -> List[float]:
        """Get historical transaction volumes"""
        # Simulate historical data (would query database in production)
        base_volume = 1000
        trend = 1.02  # 2% growth
        noise = 0.1
        
        periods = 90 if time_horizon == TimeHorizon.DAY else 30
        
        volumes = []
        for i in range(periods):
            volume = base_volume * (trend ** i) * (1 + np.random.uniform(-noise, noise))
            volumes.append(volume)
        
        return volumes
    
    async def _get_historical_revenue(self, time_horizon: TimeHorizon) -> List[float]:
        """Get historical revenue"""
        # Simulate historical data
        volumes = await self._get_historical_volumes(time_horizon)
        avg_transaction_value = 150  # $150 average
        avg_fee_rate = 0.014  # 1.4%
        
        revenues = [vol * avg_transaction_value * avg_fee_rate for vol in volumes]
        return revenues
    
    async def _get_user_transactions(self, user_id: str) -> List[Dict]:
        """Get user transaction history"""
        # Filter transactions for user
        return [
            txn for txn in self._transaction_history
            if txn.get("user_id") == user_id
        ]
    
    async def _detect_daily_pattern(self, data: List[float]) -> Optional[SeasonalPattern]:
        """Detect daily pattern (24-hour cycle)"""
        if len(data) < 24:
            return None
        
        # Group by hour
        hourly_avg = []
        for hour in range(24):
            hour_data = [data[i] for i in range(hour, len(data), 24)]
            hourly_avg.append(np.mean(hour_data))
        
        # Find peaks and troughs
        mean_value = np.mean(hourly_avg)
        peaks = [
            {"hour": i, "value": v}
            for i, v in enumerate(hourly_avg)
            if v > mean_value * 1.2
        ]
        troughs = [
            {"hour": i, "value": v}
            for i, v in enumerate(hourly_avg)
            if v < mean_value * 0.8
        ]
        
        if not peaks:
            return None
        
        amplitude = (max(hourly_avg) - min(hourly_avg)) / mean_value
        
        return SeasonalPattern(
            pattern_id=str(uuid.uuid4()),
            pattern_type="daily",
            peak_periods=peaks,
            trough_periods=troughs,
            amplitude=amplitude,
            confidence=0.85,
            detected_at=datetime.now(timezone.utc)
        )
    
    async def _detect_weekly_pattern(self, data: List[float]) -> Optional[SeasonalPattern]:
        """Detect weekly pattern (7-day cycle)"""
        if len(data) < 14:  # Need at least 2 weeks
            return None
        
        # Group by day of week
        weekly_avg = []
        for day in range(7):
            day_data = [data[i] for i in range(day, len(data), 7)]
            weekly_avg.append(np.mean(day_data))
        
        mean_value = np.mean(weekly_avg)
        peaks = [
            {"day": i, "value": v}
            for i, v in enumerate(weekly_avg)
            if v > mean_value * 1.2
        ]
        troughs = [
            {"day": i, "value": v}
            for i, v in enumerate(weekly_avg)
            if v < mean_value * 0.8
        ]
        
        if not peaks:
            return None
        
        amplitude = (max(weekly_avg) - min(weekly_avg)) / mean_value
        
        return SeasonalPattern(
            pattern_id=str(uuid.uuid4()),
            pattern_type="weekly",
            peak_periods=peaks,
            trough_periods=troughs,
            amplitude=amplitude,
            confidence=0.80,
            detected_at=datetime.now(timezone.utc)
        )
    
    async def _detect_monthly_pattern(self, data: List[float]) -> Optional[SeasonalPattern]:
        """Detect monthly pattern"""
        if len(data) < 60:  # Need at least 2 months
            return None
        
        # Simplified monthly pattern detection
        first_half = np.mean(data[:len(data)//2])
        second_half = np.mean(data[len(data)//2:])
        
        if abs(first_half - second_half) / np.mean(data) < 0.1:
            return None  # No significant pattern
        
        peaks = [{"period": "mid-month", "value": max(first_half, second_half)}]
        troughs = [{"period": "month-end", "value": min(first_half, second_half)}]
        
        amplitude = abs(first_half - second_half) / np.mean(data)
        
        return SeasonalPattern(
            pattern_id=str(uuid.uuid4()),
            pattern_type="monthly",
            peak_periods=peaks,
            trough_periods=troughs,
            amplitude=amplitude,
            confidence=0.70,
            detected_at=datetime.now(timezone.utc)
        )
    
    async def get_prediction(self, prediction_id: str) -> Prediction:
        """Get prediction by ID"""
        if prediction_id not in self._predictions:
            raise ValueError(f"Prediction not found: {prediction_id}")
        return self._predictions[prediction_id]
    
    async def get_user_prediction(self, user_id: str) -> Optional[UserBehaviorPrediction]:
        """Get user behavior prediction"""
        return self._user_predictions.get(user_id)
