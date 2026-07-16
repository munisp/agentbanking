from pydantic import BaseModel
from typing import Optional

class CreateKeycloakUser(BaseModel):
    email: str
    user_name: str
    password: Optional[str] = None

class GetKeycloakUserResponse(BaseModel):
    id: str
    username: str
    enabled: bool
    emailVerified: bool
    access: dict
    totp: bool

    class Config:
        extra = "allow"
