import random
import string
from typing import Any

from fastapi import APIRouter, Header, Body

router = APIRouter()

MOCK_TICKETS = [
    {"id": "TKT-001", "title": "USSD transactions failing for MTN subscribers", "requester": "Tunde Adebisi", "priority": "Critical", "category": "Technical", "status": "Open", "created": "2026-05-01", "slaDeadline": "2026-05-02", "assignee": "DevOps Team", "comments": [{"author": "Tunde Adebisi", "text": "Multiple agent complaints since 8am.", "time": "08:15"}]},
    {"id": "TKT-002", "title": "Commission payout discrepancy for April", "requester": "Amaka Okonkwo", "priority": "High", "category": "Billing", "status": "In Progress", "created": "2026-04-30", "slaDeadline": "2026-05-03", "assignee": "Finance Team", "comments": [{"author": "Finance Team", "text": "Investigating ledger entries.", "time": "14:00"}]},
    {"id": "TKT-003", "title": "New agent KYC training materials needed", "requester": "Seun Lawson", "priority": "Medium", "category": "Training", "status": "Open", "created": "2026-04-29", "slaDeadline": "2026-05-06", "assignee": "Training Team", "comments": []},
    {"id": "TKT-004", "title": "AML flag on agent TXN-992 incorrect", "requester": "Bayo Adeyemi", "priority": "High", "category": "Compliance", "status": "Escalated", "created": "2026-04-28", "slaDeadline": "2026-04-30", "assignee": "Compliance Team", "comments": [{"author": "Compliance Team", "text": "Escalated to CBN liaison for review.", "time": "09:30"}]},
    {"id": "TKT-005", "title": "POS terminal sync issue", "requester": "Ngozi Eze", "priority": "Low", "category": "Technical", "status": "Resolved", "created": "2026-04-25", "slaDeadline": "2026-04-28", "assignee": "Support Team", "comments": [{"author": "Support Team", "text": "Resolved after firmware update.", "time": "16:45"}]},
]

MOCK_SESSIONS = [
    {
        "id": "s1", "agentName": "Ade Okafor", "customer": "Mrs. Bello", "waitTime": "2m", "status": "active", "aiAssigned": False,
        "messages": [
            {"id": "m1", "sender": "customer", "text": "Hello, I'm having trouble with my cash-in transaction.", "time": "10:32"},
            {"id": "m2", "sender": "support", "text": "Hi Mrs. Bello, I'm here to help. Can you share your transaction reference?", "time": "10:33"},
            {"id": "m3", "sender": "customer", "text": "It's TXN-20240501-8821. I deposited ₦20,000 but my balance didn't update.", "time": "10:34"},
            {"id": "m4", "sender": "support", "text": "Thank you, I'm looking into that now. Please hold on for a moment.", "time": "10:35"},
        ],
    },
    {
        "id": "s2", "agentName": "Chike Eze", "customer": "Mr. Adeyemi", "waitTime": "5m", "status": "queued", "aiAssigned": False,
        "messages": [{"id": "m5", "sender": "customer", "text": "I need help resetting my agent PIN.", "time": "10:40"}],
    },
    {
        "id": "s3", "agentName": "Ngozi Uche", "customer": "Fatima Musa", "waitTime": "0m", "status": "resolved", "aiAssigned": True,
        "messages": [
            {"id": "m6", "sender": "customer", "text": "How do I register a new beneficiary?", "time": "09:15"},
            {"id": "m7", "sender": "support", "text": "Go to Transfers > Beneficiaries > Add New. Fill in the details and confirm with your PIN.", "time": "09:15"},
            {"id": "m8", "sender": "customer", "text": "Got it, thanks!", "time": "09:16"},
        ],
    },
    {
        "id": "s4", "agentName": "Emeka Nwosu", "customer": "Grace Obi", "waitTime": "8m", "status": "queued", "aiAssigned": False,
        "messages": [{"id": "m9", "sender": "customer", "text": "My KYC submission was rejected. What do I do?", "time": "10:45"}],
    },
]


def _rand_id(prefix: str) -> str:
    return f"{prefix}-{''.join(random.choices(string.digits, k=6))}"


@router.get("/helpdesk/tickets", tags=["HelpDesk v1"])
async def list_helpdesk_tickets(
    tenant_id: str = Header(..., alias="x-tenant-id"),
) -> dict[str, Any]:
    return {"tickets": MOCK_TICKETS}


@router.post("/helpdesk/tickets", tags=["HelpDesk v1"])
async def create_helpdesk_ticket(
    body: dict = Body(default={}),
    tenant_id: str = Header(..., alias="x-tenant-id"),
) -> dict[str, Any]:
    return {"message": "Ticket created", "id": _rand_id("TKT")}


@router.get("/chat-sessions", tags=["HelpDesk v1"])
async def list_chat_sessions_v1(
    tenant_id: str = Header(..., alias="x-tenant-id"),
) -> dict[str, Any]:
    return {"sessions": MOCK_SESSIONS}
