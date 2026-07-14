from pydantic import BaseModel
from typing import Optional


class Announcement(BaseModel):
    id: str
    title: str
    message: str
    audience: str
    channels: list[str]
    sent_at: str
    opens: int
    reactions: dict


class CreateAnnouncement(BaseModel):
    title: str
    message: str
    audience: str
    channels: list[str]
    scheduled_at: Optional[str] = None
