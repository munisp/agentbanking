from database import Base
from .mixins import TimestampMixin, SoftDeleteMixin
from utils import UserRole

from sqlalchemy import Integer, String, Enum
from sqlalchemy_serializer import SerializerMixin
from sqlalchemy.orm import Mapped, mapped_column

class Auth(Base, SerializerMixin, TimestampMixin, SoftDeleteMixin):
    """Auth Model Definition"""

    __tablename__ = "auth"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    user_role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False, default=UserRole.USER)
    keycloak_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False)
    api_key: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    api_secret: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    
    
    def __repr__(self):
        return f"<Email: {self.email}, Tenant ID: {self.tenant_id}>"