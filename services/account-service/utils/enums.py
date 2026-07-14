import enum


class AccountStatus(enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class AccountType(enum.Enum):
    PRIMARY = "primary"
    SAVINGS = "savings"
    CURRENT = "current"
    MINT = "mint"


class AccountCurrency(enum.Enum):
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    JPY = "JPY"
    AUD = "AUD"
    NGN = "NGN"
    GHS = "GHS"


class CurrencyLedgerId(enum.IntEnum):
    NGN = 1
    USD = 2
    EUR = 3
    GBP = 4
    JPY = 5
    AUD = 6
    GHS = 7

    @classmethod
    def from_currency(cls, currency: AccountCurrency) -> "CurrencyLedgerId":
        return cls[currency.value]
