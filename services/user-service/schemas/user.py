from pydantic import BaseModel
from typing import Optional
from utils import UserRole

class CreateUserSchema(BaseModel):
    first_name: str
    last_name: str
    email: str
    phone: str
    uin: str
    address: str
    city: str
    state: str
    postal_code: str

class UserSchema(BaseModel):
    name: Optional[str]
    email: Optional[str]
    user_role: Optional[UserRole]
    phone_number: Optional[str]
    