from pydantic import BaseModel
from utils import CurrencyEnum

class GenerateQRSchema(BaseModel):
    recipient: str
    amount: str
    currency: CurrencyEnum
    note: str

class ValidateQRSchema(BaseModel):
    recipient: str
    amount: str
    currency: CurrencyEnum
    note: str
    expiry: str
    signature: str
