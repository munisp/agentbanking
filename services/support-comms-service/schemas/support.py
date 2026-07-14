from pydantic import BaseModel
from typing import Optional


class Ticket(BaseModel):
    id: str
    title: str
    requester: str
    priority: str
    category: str
    status: str
    created: str
    sla_deadline: str
    assignee: str


class CreateTicket(BaseModel):
    title: str
    requester: str
    priority: str
    category: str
    description: str


class ChatSession(BaseModel):
    id: str
    agent_name: str
    customer: str
    wait_time_mins: int
    status: str


class ChatMessage(BaseModel):
    session_id: str
    sender: str
    message: str
    timestamp: str
    is_support: bool
