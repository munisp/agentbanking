from typing import Any

from fastapi import APIRouter, Header

router = APIRouter()

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

MOCK_CHANNELS = [
    {
        "id": "whatsapp",
        "name": "WhatsApp Business",
        "status": "connected",
        "followers": 18420,
        "last_synced": "2026-05-02T07:00:00Z",
    },
    {
        "id": "facebook",
        "name": "Facebook",
        "status": "connected",
        "followers": 34100,
        "last_synced": "2026-05-02T06:55:00Z",
    },
    {
        "id": "instagram",
        "name": "Instagram",
        "status": "connected",
        "followers": 22850,
        "last_synced": "2026-05-02T06:50:00Z",
    },
    {
        "id": "tiktok",
        "name": "TikTok Shop",
        "status": "available",
        "followers": 0,
        "last_synced": None,
    },
]

MOCK_ORDERS = [
    {
        "id": "ORD-001",
        "channel": "WhatsApp Business",
        "customer": "Adunola Balogun",
        "product": "Airtime Bundle - ₦5,000",
        "amount_ngn": 5000,
        "status": "completed",
        "created_at": "2026-05-02T07:15:00Z",
    },
    {
        "id": "ORD-002",
        "channel": "Instagram",
        "customer": "Chukwudi Eze",
        "product": "Data Plan - 10GB Monthly",
        "amount_ngn": 3500,
        "status": "completed",
        "created_at": "2026-05-02T07:30:00Z",
    },
    {
        "id": "ORD-003",
        "channel": "Facebook",
        "customer": "Zainab Musa",
        "product": "Utility Bill Payment",
        "amount_ngn": 18000,
        "status": "processing",
        "created_at": "2026-05-02T08:00:00Z",
    },
    {
        "id": "ORD-004",
        "channel": "WhatsApp Business",
        "customer": "Taiwo Akinlade",
        "product": "Fund Transfer - ₦50,000",
        "amount_ngn": 50000,
        "status": "completed",
        "created_at": "2026-05-02T08:10:00Z",
    },
    {
        "id": "ORD-005",
        "channel": "Instagram",
        "customer": "Blessing Okorie",
        "product": "Savings Plan Subscription",
        "amount_ngn": 10000,
        "status": "completed",
        "created_at": "2026-05-02T08:20:00Z",
    },
    {
        "id": "ORD-006",
        "channel": "Facebook",
        "customer": "Musa Ibrahim",
        "product": "Airtime Bundle - ₦2,000",
        "amount_ngn": 2000,
        "status": "failed",
        "created_at": "2026-05-02T08:25:00Z",
    },
    {
        "id": "ORD-007",
        "channel": "WhatsApp Business",
        "customer": "Nneka Obi",
        "product": "Cable TV Renewal - DSTV Compact",
        "amount_ngn": 15800,
        "status": "completed",
        "created_at": "2026-05-02T08:40:00Z",
    },
    {
        "id": "ORD-008",
        "channel": "Instagram",
        "customer": "Damilola Adeyemi",
        "product": "Micro Loan Application - ₦100,000",
        "amount_ngn": 100000,
        "status": "processing",
        "created_at": "2026-05-02T08:45:00Z",
    },
    {
        "id": "ORD-009",
        "channel": "Facebook",
        "customer": "Usman Aliyu",
        "product": "Data Plan - 5GB Weekly",
        "amount_ngn": 1500,
        "status": "completed",
        "created_at": "2026-05-02T09:00:00Z",
    },
    {
        "id": "ORD-010",
        "channel": "WhatsApp Business",
        "customer": "Amara Nwosu",
        "product": "Fund Transfer - ₦25,000",
        "amount_ngn": 25000,
        "status": "completed",
        "created_at": "2026-05-02T09:10:00Z",
    },
]

MOCK_METRICS = {
    "impressions": 45000,
    "clicks": 3200,
    "orders": 287,
    "conversion_rate": 0.63,
    "commission_earned": 142500,
}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/channels", tags=["Social Commerce"])
async def list_channels(
    tenant_id: str = Header(..., alias="x-tenant-id"),
) -> dict[str, Any]:
    return {"message": "success", "data": MOCK_CHANNELS, "tenant_id": tenant_id}


@router.get("/orders", tags=["Social Commerce"])
async def list_orders(
    tenant_id: str = Header(..., alias="x-tenant-id"),
) -> dict[str, Any]:
    return {"message": "success", "data": MOCK_ORDERS, "tenant_id": tenant_id}


@router.get("/metrics", tags=["Social Commerce"])
async def get_metrics(
    tenant_id: str = Header(..., alias="x-tenant-id"),
) -> dict[str, Any]:
    return {"message": "success", "data": MOCK_METRICS, "tenant_id": tenant_id}
