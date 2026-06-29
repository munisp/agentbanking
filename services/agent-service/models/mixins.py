import datetime

from sqlalchemy import TIMESTAMP
from sqlalchemy.orm import object_session, Mapped, mapped_column


class SoftDeleteMixin:
    """Mixin for adding soft-delete functionality."""

    deleted_at: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP, nullable=True
    )

    def soft_delete(self, commit=True, flush=False):
        self.deleted_at = datetime.datetime.now(datetime.timezone.utc)
        if flush:
            object_session(self).flush()
        if commit:
            object_session(self).commit()

    def restore(self, commit=True, flush=False):
        self.deleted_at = None
        if flush:
            object_session(self).flush()
        if commit:
            object_session(self).commit()


class TimestampMixin:
    """Mixin for default timestamp columns."""

    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP, default=datetime.datetime.now(datetime.timezone.utc)
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP,
        default=datetime.datetime.now(datetime.timezone.utc),
        onupdate=datetime.datetime.now(datetime.timezone.utc),
    )
