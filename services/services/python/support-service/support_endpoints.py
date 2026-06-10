"""
Support API Endpoints
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

router = APIRouter(prefix="/api/support", tags=["support"])

class Ticket(BaseModel):
    id: int
    subject: str
    description: str
    status: str
    priority: str
    created_at: datetime
    updated_at: datetime
    assigned_to: Optional[str]
    messages_count: int

class TicketListResponse(BaseModel):
    tickets: List[Ticket]
    total: int
    open: int
    closed: int

class TicketCreateRequest(BaseModel):
    subject: str
    description: str
    priority: str
    category: str
    transaction_id: Optional[str] = None

class TicketCreateResponse(BaseModel):
    success: bool
    ticket_id: int
    ticket_number: str
    status: str
    estimated_response_time: str

@router.get("/tickets", response_model=TicketListResponse)
async def list_tickets():
    """List user support tickets."""
    tickets = [
        {
            "id": 1001,
            "subject": "Failed transfer",
            "description": "My transfer failed but money was deducted",
            "status": "open",
            "priority": "high",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "assigned_to": "Agent John",
            "messages_count": 3
        }
    ]
    
    return {
        "tickets": tickets,
        "total": 5,
        "open": 2,
        "closed": 3
    }

@router.post("/tickets", response_model=TicketCreateResponse, status_code=201)
async def create_ticket(data: TicketCreateRequest):
    """Create new support ticket."""
    ticket_id = 1001
    ticket_number = f"TKT-{datetime.utcnow().strftime('%Y%m%d')}-{ticket_id}"
    
    return {
        "success": True,
        "ticket_id": ticket_id,
        "ticket_number": ticket_number,
        "status": "open",
        "estimated_response_time": "2 hours"
    }
