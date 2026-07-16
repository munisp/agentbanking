from typing import Any

from fastapi import APIRouter, Header, Body

router = APIRouter()

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

MOCK_CATEGORIES = [
    {"category": "Data Centres & IT Infrastructure", "co2_tonnes": 28.4, "pct": 38.9},
    {"category": "Agent Network Operations", "co2_tonnes": 17.2, "pct": 23.6},
    {"category": "Office & Facilities", "co2_tonnes": 12.5, "pct": 17.1},
    {"category": "Business Travel", "co2_tonnes": 8.1, "pct": 11.1},
    {"category": "Supply Chain & Procurement", "co2_tonnes": 6.8, "pct": 9.3},
]

MOCK_MONTHLY = [
    {"month": "Nov 25", "co2": 7.2, "energy_kwh": 18500},
    {"month": "Dec 25", "co2": 7.8, "energy_kwh": 20100},
    {"month": "Jan 26", "co2": 6.5, "energy_kwh": 16800},
    {"month": "Feb 26", "co2": 6.1, "energy_kwh": 15700},
    {"month": "Mar 26", "co2": 6.8, "energy_kwh": 17500},
    {"month": "Apr 26", "co2": 7.0, "energy_kwh": 18000},
    {"month": "May 26", "co2": 5.4, "energy_kwh": 13900},
]

MOCK_RECOMMENDATIONS = [
    {
        "id": "REC-001",
        "title": "Switch data centre cooling to free-air economisation",
        "potential_saving_tonnes": 4.2,
        "cost_ngn": 2400000,
        "status": "available",
    },
    {
        "id": "REC-002",
        "title": "Transition agent network vehicles to CNG",
        "potential_saving_tonnes": 3.1,
        "cost_ngn": 5800000,
        "status": "available",
    },
    {
        "id": "REC-003",
        "title": "Purchase RECs for renewable energy equivalent",
        "potential_saving_tonnes": 6.0,
        "cost_ngn": 1200000,
        "status": "available",
    },
]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/carbon", tags=["ESG"])
async def get_carbon_data(
    tenant_id: str = Header(..., alias="x-tenant-id"),
) -> dict[str, Any]:
    data = {
        "categories": MOCK_CATEGORIES,
        "monthly": MOCK_MONTHLY,
        "recommendations": MOCK_RECOMMENDATIONS,
        "total_co2": 73.0,
        "green_pct": 34,
        "grade": "B",
    }
    return {"message": "success", "data": data, "tenant_id": tenant_id}


@router.post("/carbon/offset", tags=["ESG"])
async def apply_offset(
    body: dict = Body(...),
    tenant_id: str = Header(..., alias="x-tenant-id"),
) -> dict[str, Any]:
    recommendation_id = body.get("recommendation_id", "")
    return {
        "message": "Offset recommendation applied",
        "data": {"recommendation_id": recommendation_id},
        "tenant_id": tenant_id,
    }
