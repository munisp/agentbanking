import random
import string
from typing import Any

from fastapi import APIRouter, Header, Body

from schemas.support import CreateTicket, ChatMessage

router = APIRouter()

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

MOCK_TICKETS = [
    {
        "id": "TKT-001",
        "title": "Agent cash-out failure in Kano",
        "requester": "Aminu Bello",
        "priority": "high",
        "category": "Agent Operations",
        "status": "open",
        "created": "2026-05-01T08:15:00Z",
        "sla_deadline": "2026-05-01T20:15:00Z",
        "assignee": "Chukwuemeka Obi",
    },
    {
        "id": "TKT-002",
        "title": "KYC document processing delay - Lagos Island branch",
        "requester": "Fatima Yusuf",
        "priority": "medium",
        "category": "Compliance / KYC",
        "status": "in_progress",
        "created": "2026-04-30T11:42:00Z",
        "sla_deadline": "2026-05-02T11:42:00Z",
        "assignee": "Ngozi Adeyemi",
    },
    {
        "id": "TKT-003",
        "title": "POS terminal offline - Ife branch",
        "requester": "Oluwaseun Adeleke",
        "priority": "high",
        "category": "POS Hardware",
        "status": "open",
        "created": "2026-05-01T13:00:00Z",
        "sla_deadline": "2026-05-02T01:00:00Z",
        "assignee": "Tunde Fashola",
    },
    {
        "id": "TKT-004",
        "title": "USSD session timeout during airtime purchase",
        "requester": "Ibrahim Musa",
        "priority": "low",
        "category": "USSD / Mobile",
        "status": "resolved",
        "created": "2026-04-28T09:05:00Z",
        "sla_deadline": "2026-04-30T09:05:00Z",
        "assignee": "Adaeze Nwosu",
    },
    {
        "id": "TKT-005",
        "title": "Float balance discrepancy - Abuja super-agent",
        "requester": "Chioma Okafor",
        "priority": "critical",
        "category": "Float Management",
        "status": "escalated",
        "created": "2026-05-01T07:30:00Z",
        "sla_deadline": "2026-05-01T13:30:00Z",
        "assignee": "Emeka Nzekwe",
        "escalation_reason": "Breach of SLA threshold",
    },
    {
        "id": "TKT-006",
        "title": "Customer unable to complete BVN linkage on mobile app",
        "requester": "Aisha Mohammed",
        "priority": "medium",
        "category": "Mobile App",
        "status": "in_progress",
        "created": "2026-04-29T15:20:00Z",
        "sla_deadline": "2026-05-01T15:20:00Z",
        "assignee": "Chukwuemeka Obi",
    },
    {
        "id": "TKT-007",
        "title": "Bulk disbursement stuck in pending state - payroll run",
        "requester": "Babatunde Olawale",
        "priority": "high",
        "category": "Bulk Payments",
        "status": "open",
        "created": "2026-05-02T06:45:00Z",
        "sla_deadline": "2026-05-02T18:45:00Z",
        "assignee": "Ngozi Adeyemi",
    },
    {
        "id": "TKT-008",
        "title": "NIP transfer reversal not credited after 72 hours",
        "requester": "Seun Akinwande",
        "priority": "high",
        "category": "Transfers / NIP",
        "status": "resolved",
        "created": "2026-04-27T10:10:00Z",
        "sla_deadline": "2026-04-28T10:10:00Z",
        "assignee": "Tunde Fashola",
    },
]

MOCK_SESSIONS = [
    {
        "id": "CHAT-001",
        "agent_name": "Adaeze Nwosu",
        "customer": "Emeka Eze",
        "wait_time_mins": 2,
        "status": "active",
    },
    {
        "id": "CHAT-002",
        "agent_name": "Ngozi Adeyemi",
        "customer": "Halima Abdullahi",
        "wait_time_mins": 5,
        "status": "active",
    },
    {
        "id": "CHAT-003",
        "agent_name": "Chukwuemeka Obi",
        "customer": "Suleiman Garba",
        "wait_time_mins": 1,
        "status": "active",
    },
    {
        "id": "CHAT-004",
        "agent_name": "Unassigned",
        "customer": "Biodun Afolabi",
        "wait_time_mins": 8,
        "status": "queued",
    },
    {
        "id": "CHAT-005",
        "agent_name": "Tunde Fashola",
        "customer": "Amara Okonkwo",
        "wait_time_mins": 0,
        "status": "resolved",
    },
]

MOCK_MESSAGES = [
    {
        "session_id": "CHAT-001",
        "sender": "Emeka Eze",
        "message": "Good morning, I tried to withdraw ₦20,000 at an agent in Surulere but the transaction failed and my account was debited.",
        "timestamp": "2026-05-02T08:01:00Z",
        "is_support": False,
    },
    {
        "session_id": "CHAT-001",
        "sender": "Adaeze Nwosu",
        "message": "Good morning Emeka, I'm sorry to hear that. Please provide your account number so I can look into this.",
        "timestamp": "2026-05-02T08:02:30Z",
        "is_support": True,
    },
    {
        "session_id": "CHAT-001",
        "sender": "Emeka Eze",
        "message": "My account number is 0123456789 and it happened around 7:45 AM today.",
        "timestamp": "2026-05-02T08:03:45Z",
        "is_support": False,
    },
    {
        "session_id": "CHAT-001",
        "sender": "Adaeze Nwosu",
        "message": "Thank you. I can see the transaction TXN-20260502-00412 in our system with status 'reversal pending'. The reversal will be processed within 24 hours.",
        "timestamp": "2026-05-02T08:05:10Z",
        "is_support": True,
    },
    {
        "session_id": "CHAT-001",
        "sender": "Emeka Eze",
        "message": "Okay, is there anything I need to do on my end?",
        "timestamp": "2026-05-02T08:06:00Z",
        "is_support": False,
    },
    {
        "session_id": "CHAT-001",
        "sender": "Adaeze Nwosu",
        "message": "No action needed from you. I have escalated the reversal to our settlement desk for priority processing. You will receive an SMS confirmation once the credit lands. Is there anything else I can help you with?",
        "timestamp": "2026-05-02T08:07:20Z",
        "is_support": True,
    },
]


def _random_id(prefix: str, length: int = 6) -> str:
    suffix = "".join(random.choices(string.digits, k=length))
    return f"{prefix}-{suffix}"


# ---------------------------------------------------------------------------
# Ticket routes
# ---------------------------------------------------------------------------


@router.get("/tickets", tags=["Support"])
async def list_tickets(
    status: str = "all",
    tenant_id: str = Header(..., alias="x-tenant-id"),
) -> dict[str, Any]:
    tickets = MOCK_TICKETS if status == "all" else [t for t in MOCK_TICKETS if t["status"] == status]
    return {"message": "success", "data": tickets, "tenant_id": tenant_id}


@router.post("/tickets", tags=["Support"])
async def create_ticket(
    payload: CreateTicket,
    tenant_id: str = Header(..., alias="x-tenant-id"),
) -> dict[str, Any]:
    new_id = _random_id("TKT")
    return {"message": "Ticket created", "data": {"id": new_id}, "tenant_id": tenant_id}


@router.get("/tickets/{ticket_id}", tags=["Support"])
async def get_ticket(
    ticket_id: str,
    tenant_id: str = Header(..., alias="x-tenant-id"),
) -> dict[str, Any]:
    ticket = next((t for t in MOCK_TICKETS if t["id"] == ticket_id), MOCK_TICKETS[0])
    comments = [
        {
            "author": "Chukwuemeka Obi",
            "message": "Investigating with the agent network ops team in Kano.",
            "timestamp": "2026-05-01T09:00:00Z",
        },
        {
            "author": "Ngozi Adeyemi",
            "message": "Confirmed switch downtime between 07:50 and 08:20. Reversal initiated.",
            "timestamp": "2026-05-01T10:30:00Z",
        },
        {
            "author": ticket.get("requester", "Customer"),
            "message": "Thank you for the update. Waiting for confirmation.",
            "timestamp": "2026-05-01T11:00:00Z",
        },
    ]
    return {"message": "success", "data": {"ticket": ticket, "comments": comments}, "tenant_id": tenant_id}


@router.put("/tickets/{ticket_id}/assign", tags=["Support"])
async def assign_ticket(
    ticket_id: str,
    body: dict = Body(default={}),
    tenant_id: str = Header(..., alias="x-tenant-id"),
) -> dict[str, Any]:
    return {"message": "Ticket assigned", "data": {"id": ticket_id}, "tenant_id": tenant_id}


@router.put("/tickets/{ticket_id}/resolve", tags=["Support"])
async def resolve_ticket(
    ticket_id: str,
    body: dict = Body(default={}),
    tenant_id: str = Header(..., alias="x-tenant-id"),
) -> dict[str, Any]:
    return {"message": "Ticket resolved", "data": {"id": ticket_id}, "tenant_id": tenant_id}


# ---------------------------------------------------------------------------
# Chat routes
# ---------------------------------------------------------------------------


@router.get("/chat/sessions", tags=["Live Chat"])
async def list_chat_sessions(
    tenant_id: str = Header(..., alias="x-tenant-id"),
) -> dict[str, Any]:
    return {"message": "success", "data": MOCK_SESSIONS, "tenant_id": tenant_id}


@router.get("/chat/sessions/{session_id}/messages", tags=["Live Chat"])
async def get_chat_messages(
    session_id: str,
    tenant_id: str = Header(..., alias="x-tenant-id"),
) -> dict[str, Any]:
    messages = [m for m in MOCK_MESSAGES if m["session_id"] == session_id] or MOCK_MESSAGES
    return {"message": "success", "data": messages, "tenant_id": tenant_id}


@router.post("/chat/sessions/{session_id}/send", tags=["Live Chat"])
async def send_chat_message(
    session_id: str,
    body: dict = Body(...),
    tenant_id: str = Header(..., alias="x-tenant-id"),
) -> dict[str, Any]:
    return {"message": "Message sent", "data": {"session_id": session_id}, "tenant_id": tenant_id}


@router.get("/chat/stats", tags=["Live Chat"])
async def chat_stats(
    tenant_id: str = Header(..., alias="x-tenant-id"),
) -> dict[str, Any]:
    stats = {
        "total_queued": 3,
        "avg_wait_mins": 4.2,
        "sla_breaches": 1,
        "active_sessions": 5,
    }
    return {"message": "success", "data": stats, "tenant_id": tenant_id}
