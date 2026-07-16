from pydantic import BaseModel
from typing import Optional
from utils import AccountType, AccountCurrency


class CreateAccountSchema(BaseModel):
    name: str
    account_type: Optional[AccountType] = None
    account_currency: Optional[AccountCurrency] = AccountCurrency.NGN
    account_number: Optional[str] = None


class SetupPinSchema(BaseModel):
    pin: str


class VerifyPinSchema(BaseModel):
    pin: str


class CheckAccountSchema(BaseModel):
    account_id: str
    pin: str
