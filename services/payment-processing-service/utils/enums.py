import enum


class TransactionStatus(enum.Enum):
    INITIATED = "initiated"
    PENDING = "pending"
    FAILED = "failed"
    SUCCESS = "success"
    REVERSED = "reversed"
    FRAUD = "fraud"


class CurrencyEnum(enum.Enum):
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
    def from_currency(cls, currency: str) -> "CurrencyLedgerId":
        return cls[currency.upper()]


class PubsubTopics(enum.Enum):
    TRANSACTION_INITIATED = "transaction_initiated"
    TRANSACTION_FAILED = "transaction_failed"
    TRANSACTION_SUCCESS = "transaction_success"
