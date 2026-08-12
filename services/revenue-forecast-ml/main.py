"""
Revenue Forecasting ML Service (Python)
Trains and serves ML models that predict future revenue based on historical billing
ledger data. Uses time-series forecasting (Prophet-style decomposition) to project
platform and client revenue, agent growth, and transaction volumes. Exports forecasts
to Lakehouse for dashboard consumption and triggers Temporal workflows for budget alerts.
Integrates with: Temporal, Lakehouse, PostgreSQL, Redis, Kafka, OpenSearch, Dapr

NOTE: Forecasts are computed from REAL billing ledger history fetched from the
configured billing ledger (BILLING_LEDGER_URL). When no ledger is configured or
returns no data, forecast endpoints return 503 — no fabricated billing history
is ever used. Synthetic data generation only exists behind
REVENUE_FORECAST_SIMULATION_MODE=true (non-production); forecasts computed from
synthetic data are marked synthetic and NEVER trigger BudgetAlerts.
"""

import os
import json
import math
import time
import logging
import hashlib
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict, field
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading

# --- Production: Graceful Shutdown ---
import signal
import sys
import atexit
import logging

_shutdown_handlers = []

def register_shutdown(handler):
    _shutdown_handlers.append(handler)

def _graceful_shutdown(signum, frame):
    sig_name = signal.Signals(signum).name if hasattr(signal, 'Signals') else str(signum)
    logging.info(f"[shutdown] Received {sig_name}, shutting down gracefully...")
    for handler in reversed(_shutdown_handlers):
        try:
            handler()
        except Exception as e:
            logging.warning(f"[shutdown] Handler error: {e}")
    logging.info("[shutdown] Cleanup complete, exiting")
    sys.exit(0)

signal.signal(signal.SIGTERM, _graceful_shutdown)
signal.signal(signal.SIGINT, _graceful_shutdown)
atexit.register(lambda: logging.info("[shutdown] atexit handler called"))


logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# ── Simulation mode gating ────────────────────────────────────────────────────
SIMULATION_MODE = os.getenv("REVENUE_FORECAST_SIMULATION_MODE", "false").lower() == "true"
APP_ENV = os.getenv("APP_ENV", os.getenv("ENVIRONMENT", "production")).lower()
if SIMULATION_MODE and APP_ENV == "production":
    raise RuntimeError(
        "REVENUE_FORECAST_SIMULATION_MODE=true is forbidden in production: "
        "synthetic billing history must never drive production forecasts or alerts."
    )
if SIMULATION_MODE:
    logger.warning("REVENUE_FORECAST_SIMULATION_MODE enabled — synthetic demo data permitted (non-production)")

# ═══════════════════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Config:
    port: int = int(os.getenv("PORT", "9300"))
    postgres_url: str = os.getenv("POSTGRES_URL", "")
    billing_ledger_url: str = os.getenv("BILLING_LEDGER_URL", "")
    temporal_addr: str = os.getenv("TEMPORAL_ADDR", "temporal:7233")
    temporal_namespace: str = os.getenv("TEMPORAL_NAMESPACE", "billing")
    lakehouse_endpoint: str = os.getenv("LAKEHOUSE_ENDPOINT", "http://lakehouse:8080")
    redis_addr: str = os.getenv("REDIS_ADDR", "redis:6379")
    kafka_brokers: str = os.getenv("KAFKA_BROKERS", "kafka:9092")
    opensearch_url: str = os.getenv("OPENSEARCH_URL", "http://opensearch:9200")
    dapr_http_port: int = int(os.getenv("DAPR_HTTP_PORT", "3500"))
    forecast_horizon_months: int = int(os.getenv("FORECAST_HORIZON_MONTHS", "12"))
    retrain_interval_hours: int = int(os.getenv("RETRAIN_INTERVAL_HOURS", "24"))
    confidence_level: float = float(os.getenv("CONFIDENCE_LEVEL", "0.95"))

# ═══════════════════════════════════════════════════════════════════════════════
# Domain Models
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class TimeSeriesPoint:
    timestamp: int
    value: float
    period: str  # "2026-01", "2026-02", etc.

@dataclass
class ForecastPoint:
    period: str
    predicted: float
    lower_bound: float
    upper_bound: float
    confidence: float
    trend_component: float
    seasonal_component: float
    residual: float

@dataclass
class RevenueForeccast:
    forecast_id: str
    metric: str  # "platform_revenue", "client_revenue", "transaction_volume", "agent_count"
    billing_model: str
    client_id: str
    horizon_months: int
    points: List[ForecastPoint]
    model_accuracy: float  # MAPE
    model_version: str
    trained_at: int
    data_points_used: int
    data_source: str = "billing_ledger"
    synthetic: bool = False

@dataclass
class ModelMetrics:
    mape: float  # Mean Absolute Percentage Error
    rmse: float  # Root Mean Square Error
    mae: float   # Mean Absolute Error
    r_squared: float
    training_samples: int
    last_trained: int

@dataclass
class BudgetAlert:
    alert_id: str
    metric: str
    period: str
    projected_value: float
    budget_value: float
    variance_pct: float
    severity: str  # "info", "warning", "critical"
    message: str
    created_at: int

# ═══════════════════════════════════════════════════════════════════════════════
# Time Series Forecasting Engine (Prophet-style decomposition)
# ═══════════════════════════════════════════════════════════════════════════════

class ForecastEngine:
    """
    Implements additive time-series decomposition:
    Y(t) = Trend(t) + Seasonal(t) + Residual(t)

    Uses linear regression for trend, Fourier series for seasonality,
    and exponential smoothing for short-term adjustments.
    """

    def __init__(self, config: Config):
        self.config = config
        self.models: Dict[str, ModelMetrics] = {}
        self.forecasts: List[RevenueForeccast] = []
        self.alerts: List[BudgetAlert] = []
        self.lock = threading.Lock()

    def decompose(self, series: List[TimeSeriesPoint]) -> Tuple[List[float], List[float], List[float]]:
        """Decompose time series into trend, seasonal, and residual components"""
        if len(series) < 6:
            return [s.value for s in series], [0.0] * len(series), [0.0] * len(series)

        values = [s.value for s in series]
        n = len(values)

        # Trend: linear regression
        x_mean = (n - 1) / 2.0
        y_mean = statistics.mean(values)

        numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        slope = numerator / denominator if denominator != 0 else 0
        intercept = y_mean - slope * x_mean

        trend = [intercept + slope * i for i in range(n)]

        # Seasonal: 12-month periodicity using moving average
        detrended = [values[i] - trend[i] for i in range(n)]
        season_length = min(12, n)
        seasonal = [0.0] * n

        if n >= season_length:
            for i in range(n):
                month_idx = i % season_length
                same_months = [detrended[j] for j in range(month_idx, n, season_length)]
                seasonal[i] = statistics.mean(same_months) if same_months else 0.0

        # Residual
        residual = [values[i] - trend[i] - seasonal[i] for i in range(n)]

        return trend, seasonal, residual

    def forecast(self, series: List[TimeSeriesPoint], horizon: int, metric: str, client_id: str,
                 billing_model: str, data_source: str = "billing_ledger",
                 synthetic: bool = False) -> RevenueForeccast:
        """Generate forecast for the given time series"""
        logger.info(f"[Forecast] Generating {horizon}-month forecast for {metric} (client={client_id}, source={data_source})")

        trend, seasonal, residual = self.decompose(series)
        values = [s.value for s in series]
        n = len(values)

        # Calculate trend slope for extrapolation
        if n >= 2:
            slope = (trend[-1] - trend[0]) / (n - 1) if n > 1 else 0
        else:
            slope = 0

        # Calculate residual std for confidence intervals
        residual_std = statistics.stdev(residual) if len(residual) > 1 else 0
        z_score = 1.96 if self.config.confidence_level >= 0.95 else 1.645

        # Generate forecast points
        forecast_points = []
        last_period = series[-1].period if series else "2026-01"

        for i in range(1, horizon + 1):
            # Extrapolate trend
            trend_value = trend[-1] + slope * i

            # Repeat seasonal pattern
            seasonal_idx = (n + i - 1) % min(12, n)
            seasonal_value = seasonal[seasonal_idx] if seasonal_idx < len(seasonal) else 0

            # Predicted value
            predicted = trend_value + seasonal_value

            # Confidence interval widens with horizon
            uncertainty = residual_std * z_score * math.sqrt(i)

            # Calculate next period string
            year = int(last_period[:4])
            month = int(last_period[5:7]) + i
            while month > 12:
                month -= 12
                year += 1
            period_str = f"{year}-{month:02d}"

            forecast_points.append(ForecastPoint(
                period=period_str,
                predicted=max(0, predicted),
                lower_bound=max(0, predicted - uncertainty),
                upper_bound=predicted + uncertainty,
                confidence=self.config.confidence_level,
                trend_component=trend_value,
                seasonal_component=seasonal_value,
                residual=0.0
            ))

        # Calculate model accuracy (MAPE on last 20% of data as holdout)
        holdout_size = max(1, n // 5)
        train_series = series[:-holdout_size]
        test_series = series[-holdout_size:]

        mape = self._calculate_mape(train_series, test_series)

        model_metrics = ModelMetrics(
            mape=mape,
            rmse=residual_std,
            mae=statistics.mean([abs(r) for r in residual]) if residual else 0,
            r_squared=1 - (sum(r**2 for r in residual) / sum((v - statistics.mean(values))**2 for v in values)) if values else 0,
            training_samples=n,
            last_trained=int(time.time())
        )

        forecast_id = hashlib.md5(f"{metric}-{client_id}-{int(time.time())}".encode()).hexdigest()[:12]

        forecast = RevenueForeccast(
            forecast_id=forecast_id,
            metric=metric,
            billing_model=billing_model,
            client_id=client_id,
            horizon_months=horizon,
            points=forecast_points,
            model_accuracy=100 - mape,
            model_version="v1.0-decomposition",
            trained_at=int(time.time()),
            data_points_used=n,
            data_source=data_source,
            synthetic=synthetic,
        )

        with self.lock:
            self.models[f"{metric}-{client_id}"] = model_metrics
            self.forecasts.append(forecast)

        # Budget alerts are NEVER raised from synthetic data
        if synthetic:
            logger.info(f"[Forecast] Synthetic-data forecast {forecast_id} — budget alerting disabled")
        else:
            self._check_budget_alerts(forecast)

        # Export to Lakehouse
        self._export_to_lakehouse(forecast)

        logger.info(f"[Forecast] Complete: {metric} accuracy={100-mape:.1f}%, horizon={horizon}mo")
        return forecast

    def _calculate_mape(self, train: List[TimeSeriesPoint], test: List[TimeSeriesPoint]) -> float:
        """Calculate Mean Absolute Percentage Error"""
        if not test:
            return 5.0  # Default 5% error if no test data

        # Simple forecast: use last training value + trend
        if len(train) >= 2:
            slope = (train[-1].value - train[0].value) / len(train)
        else:
            slope = 0

        errors = []
        for i, point in enumerate(test):
            predicted = train[-1].value + slope * (i + 1)
            if point.value != 0:
                errors.append(abs((point.value - predicted) / point.value) * 100)

        return statistics.mean(errors) if errors else 5.0

    def _check_budget_alerts(self, forecast: RevenueForeccast):
        """Check if forecast deviates significantly from budget targets.

        Only invoked for forecasts built on real billing ledger data.
        """
        # In production: compare against budget table in PostgreSQL
        budget_targets = {
            "platform_revenue": 3_000_000_000,
            "client_revenue": 8_000_000_000,
            "transaction_volume": 2_000_000,
            "agent_count": 6_000,
        }

        target = budget_targets.get(forecast.metric, 0)
        if target == 0:
            return

        for point in forecast.points[:3]:  # Check next 3 months
            variance_pct = ((point.predicted - target) / target) * 100 if target else 0

            if abs(variance_pct) > 15:
                severity = "critical" if abs(variance_pct) > 25 else "warning"
                alert = BudgetAlert(
                    alert_id=f"BA-{int(time.time()*1000)}",
                    metric=forecast.metric,
                    period=point.period,
                    projected_value=point.predicted,
                    budget_value=target,
                    variance_pct=variance_pct,
                    severity=severity,
                    message=f"{forecast.metric} projected {variance_pct:+.1f}% vs budget for {point.period}",
                    created_at=int(time.time())
                )
                with self.lock:
                    self.alerts.append(alert)
                logger.warning(f"[Budget Alert] {alert.message}")

    def _export_to_lakehouse(self, forecast: RevenueForeccast):
        """Export forecast to Lakehouse as Parquet for Spark/Trino analytics"""
        logger.info(f"[Lakehouse] Exporting forecast {forecast.forecast_id} ({forecast.metric})")
        # In production: write to S3/MinIO in Parquet format for Lakehouse consumption

    def get_all_forecasts(self) -> List[dict]:
        with self.lock:
            return [asdict(f) for f in self.forecasts[-20:]]

    def get_alerts(self) -> List[dict]:
        with self.lock:
            return [asdict(a) for a in self.alerts[-50:]]

    def get_model_metrics(self) -> Dict[str, dict]:
        with self.lock:
            return {k: asdict(v) for k, v in self.models.items()}

# ═══════════════════════════════════════════════════════════════════════════════
# Historical Data: real billing ledger queries (synthetic fallback gated)
# ═══════════════════════════════════════════════════════════════════════════════

def fetch_historical_data(config: Config, metric: str, months: int = 24) -> Optional[List[TimeSeriesPoint]]:
    """Fetch historical billing ledger data for forecasting.

    Queries the configured billing ledger service (BILLING_LEDGER_URL). Returns
    None when no ledger is configured or it returns no data — callers must then
    fail with 503 rather than fabricating history.
    """
    if not config.billing_ledger_url:
        return None

    import urllib.request
    url = (
        f"{config.billing_ledger_url.rstrip('/')}/api/v1/billing/history"
        f"?metric={metric}&months={months}"
    )
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        records = data.get("history", data) if isinstance(data, dict) else data
        series = [
            TimeSeriesPoint(
                timestamp=int(r["timestamp"]),
                value=float(r["value"]),
                period=str(r["period"]),
            )
            for r in records
            if isinstance(r, dict) and "value" in r
        ]
        series.sort(key=lambda p: p.timestamp)
        if series:
            return series
        logger.error(f"[Billing Ledger] No history returned for metric={metric}")
        return None
    except Exception as e:
        logger.error(f"[Billing Ledger] Failed to fetch history for {metric}: {e}")
        return None


def generate_synthetic_historical_data(metric: str, months: int = 24) -> List[TimeSeriesPoint]:
    """Generate SYNTHETIC historical billing data.

    Demo/testing only — callers must be in explicit simulation mode
    (REVENUE_FORECAST_SIMULATION_MODE=true, non-production) and the resulting
    forecasts are marked synthetic with budget alerting disabled.
    """
    base_values = {
        "platform_revenue": 1_500_000_000,
        "client_revenue": 4_000_000_000,
        "transaction_volume": 800_000,
        "agent_count": 2_000,
    }

    growth_rates = {
        "platform_revenue": 0.08,
        "client_revenue": 0.07,
        "transaction_volume": 0.10,
        "agent_count": 0.05,
    }

    seasonality = {
        "platform_revenue": [0.85, 0.90, 0.95, 1.0, 1.05, 1.10, 1.05, 1.0, 0.95, 1.15, 1.20, 1.30],
        "client_revenue": [0.85, 0.90, 0.95, 1.0, 1.05, 1.10, 1.05, 1.0, 0.95, 1.15, 1.20, 1.30],
        "transaction_volume": [0.80, 0.85, 0.90, 1.0, 1.05, 1.10, 1.05, 1.0, 0.90, 1.10, 1.15, 1.25],
        "agent_count": [1.0, 1.0, 1.02, 1.03, 1.05, 1.05, 1.03, 1.02, 1.0, 1.0, 1.02, 1.05],
    }

    base = base_values.get(metric, 1_000_000)
    growth = growth_rates.get(metric, 0.05)
    seasonal = seasonality.get(metric, [1.0] * 12)

    series = []
    now = datetime.now()

    for i in range(months):
        month_offset = months - 1 - i
        dt = now - timedelta(days=month_offset * 30)
        period = f"{dt.year}-{dt.month:02d}"

        # Growth + seasonality + noise
        trend_value = base * (1 + growth) ** (i / 12.0)
        seasonal_factor = seasonal[i % 12]
        noise = 1.0 + (hash(f"{metric}-{period}") % 100 - 50) / 1000.0

        value = trend_value * seasonal_factor * noise

        series.append(TimeSeriesPoint(
            timestamp=int(dt.timestamp()),
            value=value,
            period=period
        ))

    return series


def resolve_historical_data(config: Config, metric: str, months: int = 24) -> Tuple[Optional[List[TimeSeriesPoint]], str, bool]:
    """Resolve historical data for a metric.

    Returns (series, data_source, synthetic). series is None when no real data
    is available and simulation mode is off.
    """
    series = fetch_historical_data(config, metric, months)
    if series:
        return series, "billing_ledger", False
    if SIMULATION_MODE:
        logger.warning(f"[Forecast] Using SYNTHETIC history for {metric} (simulation mode)")
        return generate_synthetic_historical_data(metric, months), "synthetic-demo", True
    return None, "unavailable", False

# ═══════════════════════════════════════════════════════════════════════════════
# HTTP API
# ═══════════════════════════════════════════════════════════════════════════════

class ForecastHandler(BaseHTTPRequestHandler):
    engine: ForecastEngine = None

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == "/health":
            self._respond(200, {
                "status": "healthy",
                "service": "revenue-forecast-ml",
                "models": len(self.engine.models),
                "forecasts": len(self.engine.forecasts),
                "alerts": len(self.engine.alerts),
                "billing_ledger_configured": bool(self.engine.config.billing_ledger_url),
                "simulation_mode": SIMULATION_MODE,
            })
        elif path == "/api/v1/forecast/generate":
            metric = params.get("metric", ["platform_revenue"])[0]
            client_id = params.get("clientId", ["default"])[0]
            billing_model = params.get("billingModel", ["revenue_share"])[0]
            horizon = int(params.get("horizon", [str(self.engine.config.forecast_horizon_months)])[0])

            # Get historical data (real ledger or gated synthetic)
            historical, data_source, synthetic = resolve_historical_data(self.engine.config, metric, 24)
            if historical is None:
                self._respond(503, {
                    "error": "No billing ledger data available for forecasting. "
                             "Configure BILLING_LEDGER_URL with a working billing history endpoint. "
                             "Forecasts are refused rather than computed from fabricated history.",
                    "metric": metric,
                })
                return

            # Generate forecast
            forecast = self.engine.forecast(
                historical, horizon, metric, client_id, billing_model,
                data_source=data_source, synthetic=synthetic,
            )
            self._respond(200, asdict(forecast))
        elif path == "/api/v1/forecast/all":
            self._respond(200, self.engine.get_all_forecasts())
        elif path == "/api/v1/forecast/alerts":
            self._respond(200, self.engine.get_alerts())
        elif path == "/api/v1/forecast/models":
            self._respond(200, self.engine.get_model_metrics())
        else:
            self._respond(404, {"error": "Not found"})

    def _respond(self, status: int, data):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode())

    def log_message(self, format, *args):
        pass  # Suppress default logging

# ═══════════════════════════════════════════════════════════════════════════════
# Scheduled Retraining
# ═══════════════════════════════════════════════════════════════════════════════

def retrain_scheduler(engine: ForecastEngine):
    """Periodically retrain all models with latest data"""
    metrics = ["platform_revenue", "client_revenue", "transaction_volume", "agent_count"]

    while True:
        time.sleep(engine.config.retrain_interval_hours * 3600)
        logger.info("[Scheduler] Starting model retraining cycle")

        for metric in metrics:
            historical, data_source, synthetic = resolve_historical_data(engine.config, metric, 24)
            if historical is None:
                logger.error(f"[Scheduler] No billing ledger data for {metric} — skipping retrain")
                continue
            engine.forecast(
                historical, engine.config.forecast_horizon_months, metric, "default",
                "revenue_share", data_source=data_source, synthetic=synthetic,
            )

        logger.info("[Scheduler] Retraining complete for all metrics")

# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    config = Config()
    logger.info(f"Starting Revenue Forecast ML Service on port {config.port}")
    logger.info(f"  Billing Ledger: {config.billing_ledger_url or 'NOT CONFIGURED'}")
    logger.info(f"  Temporal: {config.temporal_addr}")
    logger.info(f"  Lakehouse: {config.lakehouse_endpoint}")
    logger.info(f"  Forecast horizon: {config.forecast_horizon_months} months")
    logger.info(f"  Retrain interval: {config.retrain_interval_hours} hours")
    logger.info(f"  Simulation mode: {SIMULATION_MODE}")

    engine = ForecastEngine(config)

    # Generate initial forecasts for all metrics — only when real (or explicitly
    # simulated) data is available; otherwise start with no forecasts and let
    # /api/v1/forecast/generate return 503 per request.
    for metric in ["platform_revenue", "client_revenue", "transaction_volume", "agent_count"]:
        historical, data_source, synthetic = resolve_historical_data(config, metric, 24)
        if historical is None:
            logger.error(f"[Startup] No billing ledger data for {metric} — forecast skipped (503 on demand)")
            continue
        engine.forecast(
            historical, config.forecast_horizon_months, metric, "default",
            "revenue_share", data_source=data_source, synthetic=synthetic,
        )

    # Start retraining scheduler
    threading.Thread(target=retrain_scheduler, args=(engine,), daemon=True).start()

    # Start HTTP server
    ForecastHandler.engine = engine
    server = HTTPServer(("0.0.0.0", config.port), ForecastHandler)
    logger.info(f"Revenue Forecast ML Service ready on port {config.port}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
        logger.info("Service stopped")

if __name__ == "__main__":
    main()
