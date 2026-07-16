from pydantic import BaseModel


class CategoryEmission(BaseModel):
    category: str
    co2_tonnes: float
    pct: float


class MonthlyEmission(BaseModel):
    month: str
    co2: float
    energy_kwh: float
