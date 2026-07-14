import random
import string
from typing import Any

from fastapi import APIRouter, Header, Body

from schemas.broadcast import CreateAnnouncement

router = APIRouter()

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

MOCK_ANNOUNCEMENTS = [
    {
        "id": "ANN-001",
        "title": "New Commission Structure Effective June 2026",
        "message": (
            "Dear Partners, please be informed that the revised agent commission structure "
            "takes effect on 1 June 2026. Cash-out commissions will increase from 0.4% to 0.5% "
            "and airtime/data commissions from 2% to 2.5%. Kindly review the attached schedule."
        ),
        "audience": "all_agents",
        "channels": ["sms", "email", "in_app"],
        "sent_at": "2026-04-25T10:00:00Z",
        "opens": 4821,
        "reactions": {"thumbs_up": 312, "heart": 97, "clap": 54},
    },
    {
        "id": "ANN-002",
        "title": "Scheduled Maintenance Window - 4 May 2026 01:00–04:00 WAT",
        "message": (
            "Our core banking infrastructure will undergo scheduled maintenance on Sunday 4 May 2026 "
            "between 01:00 and 04:00 WAT. All transaction channels including USSD, mobile app, and "
            "POS may be unavailable during this period. We apologise for any inconvenience."
        ),
        "audience": "all_users",
        "channels": ["sms", "email", "in_app", "whatsapp"],
        "sent_at": "2026-05-01T14:00:00Z",
        "opens": 12034,
        "reactions": {"thumbs_up": 89, "thumbs_down": 45, "ok": 203},
    },
    {
        "id": "ANN-003",
        "title": "Ramadan Special: Zero-Fee Transfers Until End of April",
        "message": (
            "In celebration of Ramadan, all intra-bank transfers are free of charge from "
            "1 April to 30 April 2026. Spread the word and help your customers move money "
            "with zero cost this blessed season."
        ),
        "audience": "retail_customers",
        "channels": ["sms", "in_app"],
        "sent_at": "2026-04-01T08:00:00Z",
        "opens": 28900,
        "reactions": {"heart": 1204, "thumbs_up": 892, "clap": 430},
    },
    {
        "id": "ANN-004",
        "title": "CBN Compliance Reminder: BVN Linkage Deadline",
        "message": (
            "In compliance with the Central Bank of Nigeria directive, all accounts must have "
            "valid BVN linkage by 31 May 2026. Accounts without BVN linkage will be restricted "
            "from debit transactions after this date. Please update your records immediately."
        ),
        "audience": "unlinked_bvn_customers",
        "channels": ["sms", "email"],
        "sent_at": "2026-04-20T09:00:00Z",
        "opens": 7410,
        "reactions": {"thumbs_up": 110, "ok": 320},
    },
    {
        "id": "ANN-005",
        "title": "Introducing 54agent NFC Tap-to-Pay for POS Agents",
        "message": (
            "We are excited to roll out NFC Tap-to-Pay capability to all POS agent terminals "
            "running firmware v3.8 and above. Customers can now tap any NFC-enabled card or "
            "phone to complete transactions instantly. Agent training materials are available "
            "in the Agent Academy portal."
        ),
        "audience": "pos_agents",
        "channels": ["email", "in_app", "whatsapp"],
        "sent_at": "2026-04-28T11:30:00Z",
        "opens": 3205,
        "reactions": {"thumbs_up": 284, "heart": 128, "clap": 97},
    },
]

MOCK_DRAFTS = [
    {
        "id": "ANN-DRAFT-001",
        "title": "Mid-Year Agent Performance Bonus Programme",
        "message": (
            "Top-performing agents in Q2 2026 will receive a cash bonus of up to ₦150,000 "
            "based on transaction volume and customer satisfaction scores. Full criteria TBD."
        ),
        "audience": "top_agents",
        "channels": ["email", "in_app"],
        "sent_at": None,
        "opens": 0,
        "reactions": {},
        "status": "draft",
    },
    {
        "id": "ANN-DRAFT-002",
        "title": "System Upgrade Notice - Payment Rails v2.4",
        "message": (
            "We will be upgrading our payment rails infrastructure to v2.4 in the coming weeks. "
            "Expected improvements include 30% faster NIP settlement and enhanced fraud detection. "
            "Further details to follow."
        ),
        "audience": "all_users",
        "channels": ["email"],
        "sent_at": None,
        "opens": 0,
        "reactions": {},
        "status": "draft",
    },
]


def _random_id(prefix: str, length: int = 6) -> str:
    suffix = "".join(random.choices(string.digits, k=length))
    return f"{prefix}-{suffix}"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/", tags=["Broadcast"])
async def list_announcements(
    tenant_id: str = Header(..., alias="x-tenant-id"),
) -> dict[str, Any]:
    return {"message": "success", "data": MOCK_ANNOUNCEMENTS, "tenant_id": tenant_id}


@router.post("/", tags=["Broadcast"])
async def create_announcement(
    payload: CreateAnnouncement,
    tenant_id: str = Header(..., alias="x-tenant-id"),
) -> dict[str, Any]:
    new_id = _random_id("ANN")
    return {"message": "Announcement queued", "data": {"id": new_id}, "tenant_id": tenant_id}


@router.get("/drafts", tags=["Broadcast"])
async def list_drafts(
    tenant_id: str = Header(..., alias="x-tenant-id"),
) -> dict[str, Any]:
    return {"message": "success", "data": MOCK_DRAFTS, "tenant_id": tenant_id}


@router.put("/{announcement_id}/cancel", tags=["Broadcast"])
async def cancel_announcement(
    announcement_id: str,
    tenant_id: str = Header(..., alias="x-tenant-id"),
) -> dict[str, Any]:
    return {"message": "Announcement cancelled", "data": {"id": announcement_id}, "tenant_id": tenant_id}
