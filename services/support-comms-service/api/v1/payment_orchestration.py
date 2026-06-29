from typing import Any

from fastapi import APIRouter, Header, Body

router = APIRouter()

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

MOCK_CHANNELS = [
    {
        "id": "ussd",
        "channel": "USSD",
        "tx_today": 24870,
        "success_rate": 98.4,
        "avg_processing_ms": 1200,
        "revenue_today": 1243500.0,
        "status": "active",
    },
    {
        "id": "mobile_app",
        "channel": "Mobile App",
        "tx_today": 18340,
        "success_rate": 99.1,
        "avg_processing_ms": 850,
        "revenue_today": 4180000.0,
        "status": "active",
    },
    {
        "id": "web",
        "channel": "Web",
        "tx_today": 9210,
        "success_rate": 97.8,
        "avg_processing_ms": 740,
        "revenue_today": 3620000.0,
        "status": "active",
    },
    {
        "id": "pos",
        "channel": "POS",
        "tx_today": 31450,
        "success_rate": 96.5,
        "avg_processing_ms": 2100,
        "revenue_today": 8750000.0,
        "status": "active",
    },
    {
        "id": "whatsapp",
        "channel": "WhatsApp",
        "tx_today": 4320,
        "success_rate": 99.5,
        "avg_processing_ms": 610,
        "revenue_today": 980000.0,
        "status": "active",
    },
    {
        "id": "nfc",
        "channel": "NFC",
        "tx_today": 1870,
        "success_rate": 94.2,
        "avg_processing_ms": 380,
        "revenue_today": 421000.0,
        "status": "degraded",
    },
]

MOCK_ROUTING_RULES = [
    {
        "id": "RULE-001",
        "name": "High-value transfers prefer Mobile App",
        "condition": "amount > 500000",
        "preferred_channel": "mobile_app",
        "fallback_channel": "web",
        "enabled": True,
    },
    {
        "id": "RULE-002",
        "name": "USSD for low-connectivity regions",
        "condition": "region IN ['Yobe', 'Borno', 'Zamfara'] AND amount < 50000",
        "preferred_channel": "ussd",
        "fallback_channel": "mobile_app",
        "enabled": True,
    },
    {
        "id": "RULE-003",
        "name": "POS for merchant category codes",
        "condition": "tx_type = 'merchant_payment'",
        "preferred_channel": "pos",
        "fallback_channel": "web",
        "enabled": True,
    },
    {
        "id": "RULE-004",
        "name": "WhatsApp for social commerce orders",
        "condition": "source = 'social_commerce'",
        "preferred_channel": "whatsapp",
        "fallback_channel": "mobile_app",
        "enabled": True,
    },
    {
        "id": "RULE-005",
        "name": "NFC disabled for amounts above ₦50,000",
        "condition": "channel = 'nfc' AND amount > 50000",
        "preferred_channel": "pos",
        "fallback_channel": "mobile_app",
        "enabled": True,
    },
]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/channels", tags=["Payment Orchestration"])
async def list_payment_channels(
    tenant_id: str = Header(..., alias="x-tenant-id"),
) -> dict[str, Any]:
    return {"message": "success", "data": MOCK_CHANNELS, "tenant_id": tenant_id}


@router.put("/channels/{channel_id}/status", tags=["Payment Orchestration"])
async def update_channel_status(
    channel_id: str,
    body: dict = Body(...),
    tenant_id: str = Header(..., alias="x-tenant-id"),
) -> dict[str, Any]:
    new_status = body.get("status", "")
    return {
        "message": "Channel status updated",
        "data": {"channel_id": channel_id, "status": new_status},
        "tenant_id": tenant_id,
    }


@router.get("/routing-rules", tags=["Payment Orchestration"])
async def list_routing_rules(
    tenant_id: str = Header(..., alias="x-tenant-id"),
) -> dict[str, Any]:
    return {"message": "success", "data": MOCK_ROUTING_RULES, "tenant_id": tenant_id}
