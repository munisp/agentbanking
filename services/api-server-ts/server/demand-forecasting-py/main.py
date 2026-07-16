"""
Supply Chain Demand Forecasting Service
AI-powered demand prediction with multiple algorithms:
- Moving Average
- Exponential Smoothing (Holt-Winters)
- Seasonal Decomposition
- Anomaly Detection
- Forecast Accuracy Tracking
"""

from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from forecasting import DemandForecaster, ForecastResult
from anomaly import AnomalyDetector


forecaster: Optional[DemandForecaster] = None
anomaly_detector: Optional[AnomalyDetector] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global forecaster, anomaly_detector
    forecaster = DemandForecaster()
    anomaly_detector = AnomalyDetector()
    yield
    forecaster = None
    anomaly_detector = None


app = FastAPI(
    title="Demand Forecasting Service",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "demand-forecasting",
        "version": "1.0.0",
        "algorithms": ["moving_average", "exponential_smoothing", "seasonal", "arima_lite"],
    }


class HistoricalData(BaseModel):
    sku: str
    warehouse_id: Optional[int] = None
    data_points: list[dict]  # [{"date": "2024-01-01", "quantity": 150}, ...]


class ForecastRequest(BaseModel):
    sku: str
    warehouse_id: Optional[int] = None
    horizon_days: int = 30
    method: str = "exponential_smoothing"
    historical: list[dict] = []


@app.post("/api/v1/forecast")
async def generate_forecast(req: ForecastRequest) -> dict:
    """Generate demand forecast for a SKU."""
    if not forecaster:
        raise HTTPException(503, "Forecaster not initialized")

    result = forecaster.forecast(
        sku=req.sku,
        warehouse_id=req.warehouse_id,
        historical=req.historical,
        horizon_days=req.horizon_days,
        method=req.method,
    )
    return result.to_dict()


@app.post("/api/v1/forecast/batch")
async def batch_forecast(items: list[ForecastRequest]) -> dict:
    """Generate forecasts for multiple SKUs."""
    if not forecaster:
        raise HTTPException(503, "Forecaster not initialized")

    results = []
    for item in items:
        result = forecaster.forecast(
            sku=item.sku,
            warehouse_id=item.warehouse_id,
            historical=item.historical,
            horizon_days=item.horizon_days,
            method=item.method,
        )
        results.append(result.to_dict())
    return {"forecasts": results, "count": len(results)}


@app.get("/api/v1/forecast/accuracy/{sku}")
async def forecast_accuracy(sku: str, days: int = Query(default=30)) -> dict:
    """Get forecast accuracy metrics for a SKU."""
    if not forecaster:
        raise HTTPException(503, "Forecaster not initialized")

    return forecaster.get_accuracy(sku, days)


@app.post("/api/v1/anomaly/detect")
async def detect_anomalies(data: HistoricalData) -> dict:
    """Detect demand anomalies in historical data."""
    if not anomaly_detector:
        raise HTTPException(503, "Anomaly detector not initialized")

    anomalies = anomaly_detector.detect(data.data_points)
    return {
        "sku": data.sku,
        "anomalies": anomalies,
        "total_points": len(data.data_points),
        "anomaly_count": len(anomalies),
    }


@app.get("/api/v1/seasonal/factors/{sku}")
async def seasonal_factors(
    sku: str,
    periods: int = Query(default=12),
) -> dict:
    """Get seasonal adjustment factors for a SKU."""
    if not forecaster:
        raise HTTPException(503, "Forecaster not initialized")

    factors = forecaster.get_seasonal_factors(sku, periods)
    return {"sku": sku, "periods": periods, "factors": factors}


@app.post("/api/v1/reorder/calculate")
async def calculate_reorder_point(req: dict) -> dict:
    """Calculate optimal reorder point based on demand forecast and lead time."""
    sku = req.get("sku", "")
    lead_time_days = req.get("leadTimeDays", 7)
    service_level = req.get("serviceLevel", 0.95)
    avg_daily_demand = req.get("avgDailyDemand", 10)
    demand_std_dev = req.get("demandStdDev", 3)

    # Safety stock = Z * σ * √(lead time)
    import math
    z_scores = {0.90: 1.28, 0.95: 1.65, 0.97: 1.88, 0.99: 2.33}
    z = z_scores.get(service_level, 1.65)
    safety_stock = z * demand_std_dev * math.sqrt(lead_time_days)
    reorder_point = (avg_daily_demand * lead_time_days) + safety_stock
    eoq = math.sqrt((2 * avg_daily_demand * 365 * 500) / (avg_daily_demand * 0.25))

    return {
        "sku": sku,
        "reorderPoint": round(reorder_point),
        "safetyStock": round(safety_stock),
        "economicOrderQuantity": round(eoq),
        "avgDailyDemand": avg_daily_demand,
        "leadTimeDays": lead_time_days,
        "serviceLevel": service_level,
    }


@app.get("/api/v1/trends/{sku}")
async def demand_trends(sku: str, lookback_days: int = Query(default=90)) -> dict:
    """Analyze demand trends for a SKU."""
    if not forecaster:
        raise HTTPException(503, "Forecaster not initialized")

    return forecaster.analyze_trends(sku, lookback_days)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8202)
