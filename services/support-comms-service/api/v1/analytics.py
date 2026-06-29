from typing import Any

from fastapi import APIRouter, Header

router = APIRouter()

# ---------------------------------------------------------------------------
# Mock data  (Nov 2025 – Oct 2026; May 2026 is current partial month)
# ---------------------------------------------------------------------------

MOCK_FORECAST_POINTS = [
    # Completed months – both actual and forecast
    {"month": "Nov 25", "actual": 12800000.0, "forecast": 12500000.0},
    {"month": "Dec 25", "actual": 14200000.0, "forecast": 13900000.0},
    {"month": "Jan 26", "actual": 11500000.0, "forecast": 11800000.0},
    {"month": "Feb 26", "actual": 12100000.0, "forecast": 12000000.0},
    {"month": "Mar 26", "actual": 13400000.0, "forecast": 13200000.0},
    {"month": "Apr 26", "actual": 15600000.0, "forecast": 15000000.0},
    # Current partial month – actual is MTD figure
    {"month": "May 26", "actual": 16200000.0, "forecast": 26000000.0},
    # Future months – forecast only
    {"month": "Jun 26", "actual": None, "forecast": 27500000.0},
    {"month": "Jul 26", "actual": None, "forecast": 28800000.0},
    {"month": "Aug 26", "actual": None, "forecast": 30100000.0},
    {"month": "Sep 26", "actual": None, "forecast": 31400000.0},
    {"month": "Oct 26", "actual": None, "forecast": 33000000.0},
]

MOCK_SEGMENTS = [
    {
        "segment": "Agent Cash-Out",
        "current": 8400000.0,
        "projected": 11200000.0,
        "growth_pct": 33.3,
    },
    {
        "segment": "Mobile Transfers",
        "current": 3900000.0,
        "projected": 5800000.0,
        "growth_pct": 48.7,
    },
    {
        "segment": "Bill Payments",
        "current": 2100000.0,
        "projected": 3500000.0,
        "growth_pct": 66.7,
    },
    {
        "segment": "Merchant POS",
        "current": 1200000.0,
        "projected": 2600000.0,
        "growth_pct": 116.7,
    },
    {
        "segment": "Social Commerce",
        "current": 600000.0,
        "projected": 2900000.0,
        "growth_pct": 383.3,
    },
]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/revenue-forecast", tags=["Analytics"])
async def revenue_forecast(
    range: str = "12m",
    tenant_id: str = Header(..., alias="x-tenant-id"),
) -> dict[str, Any]:
    data = {
        "forecast": MOCK_FORECAST_POINTS,
        "segments": MOCK_SEGMENTS,
        "accuracy_pct": 97.2,
        "current_month": 16200000,
        "projected_month_end": 26000000,
        "ytd": 144500000,
        "range": range,
    }
    return {"message": "success", "data": data, "tenant_id": tenant_id}
