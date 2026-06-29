from pydantic import BaseModel
from typing import Optional


class ForecastPoint(BaseModel):
    month: str
    actual: Optional[float] = None
    forecast: float


class SegmentForecast(BaseModel):
    segment: str
    current: float
    projected: float
    growth_pct: float


class ChannelPerformance(BaseModel):
    channel: str
    tx_today: int
    success_rate: float
    avg_processing_ms: int
    revenue_today: float
    status: str
