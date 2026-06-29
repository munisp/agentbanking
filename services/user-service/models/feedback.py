import uuid
import datetime

from database import Base
from utils import FeedbackStatus, FeedbackCategory
from .mixins import TimestampMixin, SoftDeleteMixin

from sqlalchemy import String, Enum, Integer, Text, ForeignKey, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy_serializer import SerializerMixin
from sqlalchemy.orm import Mapped, mapped_column, relationship


class Feedback(Base, SerializerMixin, TimestampMixin, SoftDeleteMixin):
    """Customer Feedback Model"""

    __tablename__ = "feedback"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=False
    )
    tenant_id: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[FeedbackCategory] = mapped_column(
        Enum(FeedbackCategory), nullable=False, default=FeedbackCategory.GENERAL
    )
    subject: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[FeedbackStatus] = mapped_column(
        Enum(FeedbackStatus), nullable=False, default=FeedbackStatus.OPEN
    )
    response: Mapped[str | None] = mapped_column(Text, nullable=True)
    responded_by: Mapped[str | None] = mapped_column(String, nullable=True)
    responded_at: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP, nullable=True
    )

    # Relationship
    user = relationship("User", backref="feedbacks")

    def __repr__(self):
        return f"<Feedback(id={self.id}, user_id={self.user_id}, status={self.status})>"

    def to_dict(self):
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "tenant_id": self.tenant_id,
            "category": self.category.value if self.category else None,
            "subject": self.subject,
            "message": self.message,
            "rating": self.rating,
            "status": self.status.value if self.status else None,
            "response": self.response,
            "responded_by": self.responded_by,
            "responded_at": (
                self.responded_at.isoformat() if self.responded_at else None
            ),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
