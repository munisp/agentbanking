from pydantic import BaseModel, Field
from typing import Optional
from utils import FeedbackCategory


class CreateFeedbackSchema(BaseModel):
    category: FeedbackCategory = FeedbackCategory.GENERAL
    subject: str
    message: str
    rating: Optional[int] = Field(None, ge=1, le=5, description="Rating from 1 to 5")


class RespondToFeedbackSchema(BaseModel):
    response: str
    status: Optional[str] = "resolved"
