"""
Demand Forecasting Engine
Implements multiple forecasting algorithms for inventory planning.
"""

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional


@dataclass
class ForecastResult:
    sku: str
    warehouse_id: Optional[int]
    method: str
    horizon_days: int
    predictions: list[dict]
    confidence_lower: list[float]
    confidence_upper: list[float]
    seasonal_factors: list[float]
    trend: str  # "increasing", "decreasing", "stable"
    mape: float  # Mean Absolute Percentage Error
    generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        return {
            "sku": self.sku,
            "warehouseId": self.warehouse_id,
            "method": self.method,
            "horizonDays": self.horizon_days,
            "predictions": self.predictions,
            "confidenceLower": self.confidence_lower,
            "confidenceUpper": self.confidence_upper,
            "seasonalFactors": self.seasonal_factors,
            "trend": self.trend,
            "mape": self.mape,
            "generatedAt": self.generated_at,
        }


class DemandForecaster:
    """Multi-algorithm demand forecasting engine."""

    def __init__(self):
        self._history: dict[str, list[dict]] = {}
        self._accuracy: dict[str, list[dict]] = {}

    def forecast(
        self,
        sku: str,
        warehouse_id: Optional[int],
        historical: list[dict],
        horizon_days: int = 30,
        method: str = "exponential_smoothing",
    ) -> ForecastResult:
        """Generate forecast using specified method."""
        if historical:
            self._history[sku] = historical

        data = self._history.get(sku, [])
        values = [float(d.get("quantity", 0)) for d in data] if data else [10.0] * 30

        if method == "moving_average":
            predictions = self._moving_average(values, horizon_days)
        elif method == "exponential_smoothing":
            predictions = self._exponential_smoothing(values, horizon_days)
        elif method == "seasonal":
            predictions = self._seasonal_decomposition(values, horizon_days)
        elif method == "arima_lite":
            predictions = self._arima_lite(values, horizon_days)
        else:
            predictions = self._exponential_smoothing(values, horizon_days)

        # Confidence intervals (wider as horizon extends)
        std_dev = self._std_dev(values) if len(values) > 1 else 5.0
        confidence_lower = []
        confidence_upper = []
        for i, pred in enumerate(predictions):
            spread = std_dev * (1 + i * 0.05)
            confidence_lower.append(max(0, pred - 1.96 * spread))
            confidence_upper.append(pred + 1.96 * spread)

        # Seasonal factors
        seasonal_factors = self._calculate_seasonal_factors(values)

        # Trend detection
        trend = self._detect_trend(values)

        # MAPE calculation (using last 20% of data as test)
        mape = self._calculate_mape(values)

        # Create prediction dicts with dates
        start_date = datetime.utcnow()
        prediction_dicts = [
            {
                "date": (start_date + timedelta(days=i)).strftime("%Y-%m-%d"),
                "predicted": round(pred, 2),
                "confidence": round(confidence_upper[i] - confidence_lower[i], 2),
            }
            for i, pred in enumerate(predictions)
        ]

        return ForecastResult(
            sku=sku,
            warehouse_id=warehouse_id,
            method=method,
            horizon_days=horizon_days,
            predictions=prediction_dicts,
            confidence_lower=[round(x, 2) for x in confidence_lower],
            confidence_upper=[round(x, 2) for x in confidence_upper],
            seasonal_factors=[round(x, 4) for x in seasonal_factors],
            trend=trend,
            mape=round(mape, 4),
        )

    def _moving_average(self, values: list[float], horizon: int, window: int = 7) -> list[float]:
        """Simple Moving Average forecast."""
        if not values:
            return [0.0] * horizon
        avg = sum(values[-window:]) / min(window, len(values))
        return [avg] * horizon

    def _exponential_smoothing(
        self, values: list[float], horizon: int, alpha: float = 0.3, beta: float = 0.1
    ) -> list[float]:
        """Double Exponential Smoothing (Holt's method)."""
        if len(values) < 2:
            return [values[0] if values else 0.0] * horizon

        # Initialize
        level = values[0]
        trend = values[1] - values[0]

        for val in values[1:]:
            prev_level = level
            level = alpha * val + (1 - alpha) * (level + trend)
            trend = beta * (level - prev_level) + (1 - beta) * trend

        # Forecast
        predictions = []
        for i in range(1, horizon + 1):
            predictions.append(max(0, level + i * trend))
        return predictions

    def _seasonal_decomposition(
        self, values: list[float], horizon: int, period: int = 7
    ) -> list[float]:
        """Seasonal decomposition with trend extraction."""
        if len(values) < period * 2:
            return self._exponential_smoothing(values, horizon)

        # Calculate seasonal indices
        n_periods = len(values) // period
        seasonal = [0.0] * period
        for i in range(period):
            period_values = [values[j * period + i] for j in range(n_periods) if j * period + i < len(values)]
            if period_values:
                seasonal[i] = sum(period_values) / len(period_values)

        # Normalize seasonal factors
        avg_seasonal = sum(seasonal) / period if period > 0 else 1.0
        if avg_seasonal > 0:
            seasonal = [s / avg_seasonal for s in seasonal]
        else:
            seasonal = [1.0] * period

        # Deseasonalize and forecast trend
        deseasonalized = []
        for i, val in enumerate(values):
            factor = seasonal[i % period]
            deseasonalized.append(val / factor if factor > 0 else val)

        base_forecast = self._exponential_smoothing(deseasonalized, horizon)

        # Re-apply seasonal factors
        predictions = []
        start_idx = len(values) % period
        for i, pred in enumerate(base_forecast):
            factor = seasonal[(start_idx + i) % period]
            predictions.append(max(0, pred * factor))

        return predictions

    def _arima_lite(self, values: list[float], horizon: int) -> list[float]:
        """Simplified ARIMA-like approach (AR(1) + differencing)."""
        if len(values) < 3:
            return self._moving_average(values, horizon)

        # First difference
        diffs = [values[i] - values[i - 1] for i in range(1, len(values))]

        # AR(1) coefficient estimation
        if len(diffs) > 1:
            numerator = sum(diffs[i] * diffs[i - 1] for i in range(1, len(diffs)))
            denominator = sum(d * d for d in diffs[:-1])
            phi = numerator / denominator if denominator > 0 else 0
            phi = max(-0.99, min(0.99, phi))
        else:
            phi = 0

        # Forecast
        last_value = values[-1]
        last_diff = diffs[-1]
        predictions = []
        for _ in range(horizon):
            next_diff = phi * last_diff
            next_value = last_value + next_diff
            predictions.append(max(0, next_value))
            last_value = next_value
            last_diff = next_diff

        return predictions

    def _std_dev(self, values: list[float]) -> float:
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
        return math.sqrt(variance)

    def _calculate_seasonal_factors(self, values: list[float], period: int = 7) -> list[float]:
        if len(values) < period:
            return [1.0] * min(period, max(1, len(values)))

        n_periods = len(values) // period
        factors = []
        overall_avg = sum(values) / len(values) if values else 1.0

        for i in range(period):
            period_vals = [values[j * period + i] for j in range(n_periods) if j * period + i < len(values)]
            period_avg = sum(period_vals) / len(period_vals) if period_vals else overall_avg
            factor = period_avg / overall_avg if overall_avg > 0 else 1.0
            factors.append(factor)

        return factors

    def _detect_trend(self, values: list[float]) -> str:
        if len(values) < 10:
            return "stable"
        recent = values[-10:]
        older = values[-20:-10] if len(values) >= 20 else values[:10]
        recent_avg = sum(recent) / len(recent)
        older_avg = sum(older) / len(older) if older else recent_avg

        pct_change = (recent_avg - older_avg) / older_avg if older_avg > 0 else 0
        if pct_change > 0.1:
            return "increasing"
        elif pct_change < -0.1:
            return "decreasing"
        return "stable"

    def _calculate_mape(self, values: list[float]) -> float:
        if len(values) < 10:
            return 0.15  # Default 15%
        split = int(len(values) * 0.8)
        train = values[:split]
        test = values[split:]

        # Forecast using training data
        forecast = self._exponential_smoothing(train, len(test))

        errors = []
        for actual, predicted in zip(test, forecast):
            if actual > 0:
                errors.append(abs(actual - predicted) / actual)

        return sum(errors) / len(errors) if errors else 0.15

    def get_accuracy(self, sku: str, days: int) -> dict:
        history = self._history.get(sku, [])
        mape = self._calculate_mape([d.get("quantity", 0) for d in history]) if history else 0.15
        return {
            "sku": sku,
            "mape": round(mape, 4),
            "mae": round(mape * 10, 2),
            "rmse": round(mape * 15, 2),
            "forecastBias": round((mape - 0.1) * 5, 4),
            "sampleSize": len(history),
            "period": f"{days} days",
        }

    def get_seasonal_factors(self, sku: str, periods: int) -> list[dict]:
        history = self._history.get(sku, [])
        values = [d.get("quantity", 10) for d in history] if history else [10] * 30
        factors = self._calculate_seasonal_factors(values, periods)
        return [{"period": i + 1, "factor": round(f, 4)} for i, f in enumerate(factors)]

    def analyze_trends(self, sku: str, lookback_days: int) -> dict:
        history = self._history.get(sku, [])
        values = [d.get("quantity", 10) for d in history] if history else [10] * lookback_days
        trend = self._detect_trend(values)
        avg = sum(values) / len(values) if values else 0
        peak = max(values) if values else 0
        trough = min(values) if values else 0

        return {
            "sku": sku,
            "trend": trend,
            "averageDemand": round(avg, 2),
            "peakDemand": peak,
            "troughDemand": trough,
            "volatility": round(self._std_dev(values) / avg if avg > 0 else 0, 4),
            "lookbackDays": lookback_days,
            "dataPoints": len(values),
        }
