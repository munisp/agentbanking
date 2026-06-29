from database import Base
from .mixins import TimestampMixin, SoftDeleteMixin
from utils import AccountStatus, AccountType, AccountCurrency

from sqlalchemy import Integer, String, Enum
from sqlalchemy_serializer import SerializerMixin
from sqlalchemy.orm import Mapped, mapped_column


class Account(Base, SerializerMixin, TimestampMixin, SoftDeleteMixin):
    """Account Model Definition"""

    __tablename__ = "account"

    serialize_rules = (
        "-pin",
        "-balance",
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )  # Tigerbeetle account identifier
    name: Mapped[str] = mapped_column(String, nullable=False)
    keycloak_id: Mapped[str] = mapped_column(String, nullable=False)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False)
    ledger_id: Mapped[str] = mapped_column(String, nullable=False)
    account_number: Mapped[str] = mapped_column(
        String, unique=True, nullable=False
    )  # 10 digit account number
    balance: Mapped[str] = mapped_column(
        String, nullable=False
    )  # A point in time balance - Not trust-worthy
    pin: Mapped[str] = mapped_column(String, nullable=True)
    status: Mapped[AccountStatus] = mapped_column(
        Enum(AccountStatus), nullable=False, default=AccountStatus.ACTIVE
    )
    account_type: Mapped[AccountType] = mapped_column(
        Enum(
            AccountType,
            values_callable=lambda x: [e.value for e in x],
            name="accounttype",
        ),
        nullable=False,
        default=AccountType.PRIMARY,
    )
    account_currency: Mapped[AccountCurrency] = mapped_column(
        Enum(
            AccountCurrency,
            values_callable=lambda x: [e.value for e in x],
            name="accountcurrency",
        ),
        nullable=False,
        default=AccountCurrency.NGN,
    )

    def __repr__(self):
        return (
            f"<Account Number: {self.account_number}, Keycloak ID: {self.keycloak_id}>"
        )
