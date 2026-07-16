from database import Base
from .mixins import TimestampMixin, SoftDeleteMixin
from utils import AccountStatus

from sqlalchemy import Integer, String, Enum
from sqlalchemy_serializer import SerializerMixin
from sqlalchemy.orm import Mapped, mapped_column

class Bank(Base, SerializerMixin, TimestampMixin, SoftDeleteMixin):
    """Bank Model Definition"""

    __tablename__ = "bank"

    code: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    ledger_id: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[AccountStatus] = mapped_column(Enum(AccountStatus), nullable=False, default=AccountStatus.ACTIVE)
    logo: Mapped[str] = mapped_column(String, nullable=True)

    def __repr__(self):
        return f"<Bank Name: {self.name}, Bank Code: {self.code}>"
    